"""
PromSec RL Training Script
使用 Policy Gradient (REINFORCE) 訓練 Generator
"""

import os
import ast
import time
import random
import json
import subprocess
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torch_geometric.nn as pyg_nn
from torch_geometric.data import Data
from tqdm import tqdm
from openai import OpenAI

from utils_new import (
    generate_cfg_from_code, get_node_features, cfg_to_pyg_data,
    extract_graph_from_pyg_data, create_cfg_diff_prompt, calculate_similarity
)

# ============================================================
# 設定
# ============================================================
import sys
random.seed(42)
torch.manual_seed(42)

# 強制刷新 stdout，避免輸出延遲
sys.stdout.reconfigure(line_buffering=True)

# OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ============================================================
# Model 定義
# ============================================================
# 特徵維度說明:
#   [0:7]   - 結構相關 Flags (contains_function, loop, if, etc.) - 不可修改
#   [7:20]  - 安全相關 Flags (is_sensitive_call, is_sql_query, etc.) - 可修改
#   [20:22] - 結構特徵 (in_degree, out_degree) - 不可修改
#   [22:67] - AST Type One-Hot (45 types) - 不可修改
NUM_FIXED_PREFIX = 7      # 前 7 個結構 flags 不動
NUM_SECURITY_FLAGS = 13   # 只改 13 個安全特徵 (index 7-19)
SECURITY_FLAG_START = 7
SECURITY_FLAG_END = 20

class Generator(nn.Module):
    def __init__(self, in_feats, hidden_feats, out_feats):
        """
        in_feats: 67 (完整特徵輸入)
        out_feats: 13 (只輸出安全相關 flags)
        """
        super(Generator, self).__init__()
        self.conv1 = pyg_nn.GraphConv(in_feats, hidden_feats)
        self.conv2 = pyg_nn.GraphConv(hidden_feats, out_feats)  # 只輸出 13 維
        self.relu = nn.ReLU()

    def forward(self, x, edge_index):
        h = self.conv1(x, edge_index)
        h = self.relu(h)
        security_logits = self.conv2(h, edge_index)  # 只輸出安全 flags 的 logits
        return security_logits

    def get_action_and_log_prob(self, x, edge_index):
        """
        只對 index 7-19 (安全相關 flags) 進行預測
        其他維度 (結構 flags, degrees, AST type) 保持原值不修改
        """
        security_logits = self.forward(x, edge_index)  # shape: (num_nodes, 13)
        
        # 用 sigmoid 轉成機率，再用 Bernoulli 採樣
        security_probs = torch.sigmoid(security_logits)
        dist = torch.distributions.Bernoulli(security_probs)
        security_action = dist.sample()  # 0 或 1
        log_prob = dist.log_prob(security_action).sum()
        
        # 前 7 維 (結構 flags) 從原始 input 複製
        prefix_flags = x[:, :SECURITY_FLAG_START]  # shape: (num_nodes, 7)
        
        # 後 47 維 (degrees + AST type) 從原始 input 複製
        suffix_features = x[:, SECURITY_FLAG_END:]  # shape: (num_nodes, 47)
        
        # 組合: [前7維] + [13維安全flags] + [後47維]
        action = torch.cat([prefix_flags, security_action, suffix_features], dim=1)
        
        return action, log_prob, security_probs


# ============================================================
# Helper Functions
# ============================================================
def get_completion(prompt, model="gpt-4o-mini", timeout=30, max_retries=2):
    """LLM API call with timeout and retry"""
    messages = [{"role": "user", "content": prompt}]
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                timeout=timeout,  # 30 秒 timeout
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  [WARN] LLM retry {attempt+1}/{max_retries}: {e}")
                time.sleep(2)
            else:
                raise e


def graph_to_code(original_code, original_cfg, updated_cfg, model="gpt-4o-mini"):
    prompt = create_cfg_diff_prompt(original_code, original_cfg, updated_cfg, format="dot")
    try:
        return get_completion(prompt, model=model, timeout=30).strip()
    except Exception as e:
        print(f"  [ERROR] LLM failed: {e}")
        return original_code  # fallback to original


def calculate_vcs(code, code_filename="temp_code.py"):
    """計算 code 中的漏洞數 (使用 Bandit)"""
    try:
        with open(code_filename, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        print(f"  [WARN] Failed to write {code_filename}: {e}")
        return 0, []
    
    command = f"bandit -f json {code_filename}"
    try:
        # 使用 Popen + communicate 來處理 timeout (Windows 相容性更好)
        proc = subprocess.Popen(
            command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()  # 清理
        print(f"  [WARN] Bandit timeout on {code_filename}")
        return 0, []
    except Exception as e:
        print(f"  [WARN] Bandit error: {e}")
        return 0, []
    
    try:
        result_json = json.loads(stdout)
        cwe_set = set()
        if "results" in result_json:
            for issue in result_json["results"]:
                if "issue_cwe" in issue and "id" in issue["issue_cwe"]:
                    cwe_set.add(issue["issue_cwe"]["id"])
        return len(cwe_set), list(cwe_set)
    except json.JSONDecodeError:
        return 0, []


def create_pyg_data(x, edge_index, edge_attr=None):
    return Data(x=x, edge_index=edge_index, edge_attr=edge_attr)


def load_original_code(file_path):
    with open(file_path, 'r') as f:
        return f.read()


def remove_markdown(code):
    """移除 LLM 回傳的 markdown 包裝"""
    code = code.strip()
    
    # 移除開頭的 ```python 或 ```
    if code.startswith("```python"):
        code = code[len("```python"):].lstrip("\n")
    elif code.startswith("```"):
        code = code[3:].lstrip("\n")
    
    # 移除結尾的 ```
    if code.endswith("```"):
        code = code[:-3].rstrip("\n")
    
    return code


# ============================================================
# RL Trainer
# ============================================================
class RLTrainer:
    def __init__(self, generator, lr=1e-4, baseline_decay=0.99):
        self.generator = generator
        self.optimizer = optim.Adam(generator.parameters(), lr=lr)
        self.baseline = 0  # moving average baseline for variance reduction
        self.baseline_decay = baseline_decay
    
    def compute_reward(self, ci, ci_hat):
        """
        計算 reward:
        - 漏洞減少 → 正 reward
        - 功能相似度 → 正 reward
        """
        # 使用不同的暫存檔案避免衝突
        print("abc")
        vuln_before = calculate_vcs(ci, "temp_code_before.py")[0]
        vuln_after = calculate_vcs(ci_hat, "temp_code_after.py")[0]
        print("cdf")
        # Security reward: 漏洞減少越多越好
        security_reward = float(vuln_before - vuln_after)
        
        # Functionality reward: 保持功能相似度
        try:
            similarity = calculate_similarity(ci, ci_hat)
        except:
            similarity = 0.0
        
        # 總 reward
        reward = security_reward + 0.3 * similarity
        return reward, vuln_before, vuln_after
    
    def train_epoch(self, pyg_data_list, file_paths, batch_size=8):
        """
        使用 REINFORCE 算法訓練一個 epoch
        累積 batch_size 個 samples 後再更新
        """
        self.generator.train()
        
        log_probs = []
        rewards = []
        vuln_changes = []
        
        total_samples = len(pyg_data_list)
        pbar = tqdm(enumerate(pyg_data_list), total=total_samples, desc="Training")
        
        for i, pyg_data in pbar:
            x, edge_index = pyg_data.x, pyg_data.edge_index
            
            # 1. Generator 產生 action (updated features)
            t0 = time.time()
            action, log_prob, mu = self.generator.get_action_and_log_prob(x, edge_index)
            log_probs.append(log_prob)
            t1 = time.time()
            
            # 2. 與 Environment 互動 (LLM + Bandit)
            g_before = extract_graph_from_pyg_data(pyg_data)
            updated_pyg_data = create_pyg_data(action.detach().cpu(), edge_index.cpu())
            updated_pyg_data.node_names = pyg_data.node_names
            g_after = extract_graph_from_pyg_data(updated_pyg_data)
            t2 = time.time()
            
            ci = load_original_code(file_paths[i])
            ci = remove_markdown(ci)
            print(f"  [DEBUG] Sample {i}: Generator={t1-t0:.2f}s, Graph={t2-t1:.2f}s, calling LLM...")
            
            ci_hat = graph_to_code(ci, g_before, g_after, model="gpt-4o-mini")
            t3 = time.time()
            print(f"  [DEBUG] LLM done in {t3-t2:.2f}s, running Bandit...")
            
            ci_hat = remove_markdown(ci_hat)
            
            # 3. 計算 reward
            reward, vuln_before, vuln_after = self.compute_reward(ci, ci_hat)
            t4 = time.time()
            print(f"  [DEBUG] Bandit done in {t4-t3:.2f}s, total={t4-t0:.2f}s")
            rewards.append(reward)
            vuln_changes.append(vuln_after - vuln_before)
            
            pbar.set_postfix({
                'reward': f'{reward:.2f}',
                'vuln': f'{vuln_before}→{vuln_after}'
            })
            
            # 4. 累積到 batch_size 後更新
            if (i + 1) % batch_size == 0 or i == total_samples - 1:
                self._update_policy(log_probs, rewards)
                log_probs = []
                rewards = []
        
        avg_vuln_change = np.mean(vuln_changes)
        return avg_vuln_change
    
    def _update_policy(self, log_probs, rewards):
        """
        Policy Gradient 更新
        Loss = -sum(log_prob * (reward - baseline))
        """
        if not rewards:
            return
        
        rewards_tensor = torch.tensor(rewards, dtype=torch.float32)
        
        # 更新 baseline (moving average)
        batch_mean = rewards_tensor.mean().item()
        self.baseline = self.baseline_decay * self.baseline + (1 - self.baseline_decay) * batch_mean
        
        # 標準化 rewards (減少 variance)
        advantages = rewards_tensor - self.baseline
        if len(advantages) > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # 計算 policy loss
        policy_loss = 0
        for log_prob, advantage in zip(log_probs, advantages):
            policy_loss -= log_prob * advantage
        
        # Backprop
        self.optimizer.zero_grad()
        policy_loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(self.generator.parameters(), max_norm=1.0)
        
        self.optimizer.step()


# ============================================================
# Main Training
# ============================================================
def main():
    # 載入訓練資料 (按 CWE 平衡採樣)
    folder_path = "Training_DS"
    files = sorted([f for f in os.listdir(folder_path) if f.endswith('.py')])
    
    # 按 CWE 分組
    cwe_groups = {}
    for f in files:
        for p in f.split('_'):
            if p.startswith('cwe-'):
                cwe_groups.setdefault(p, []).append(f)
                break
    
    # 每個 CWE 取 10 筆
    samples_per_cwe = 15
    sampled_files = []
    for cwe, cwe_files in cwe_groups.items():
        sampled = random.sample(cwe_files, min(samples_per_cwe, len(cwe_files)))
        sampled_files.extend(sampled)
        print(f"{cwe}: 取 {len(sampled)} 筆")
    
    random.shuffle(sampled_files)
    file_paths = [os.path.join(folder_path, f) for f in sampled_files]
    print(f"\n總共: {len(file_paths)} 筆訓練資料")
    
    # 建立 CFG 和 PyG Data
    print("\n建立 CFG...")
    pyg_data_list = []
    valid_file_paths = []
    for fp in tqdm(file_paths):
        cfg = generate_cfg_from_code(fp)
        if cfg is not None and len(cfg.nodes()) > 0:
            pyg_data = cfg_to_pyg_data(cfg)
            pyg_data_list.append(pyg_data)
            valid_file_paths.append(fp)
    
    file_paths = valid_file_paths
    print(f"有效資料: {len(pyg_data_list)} 筆")
    
    # Model 參數
    in_feats = 67   # 完整輸入: 7 結構flags + 13 安全flags + 2 degrees + 45 AST
    hidden_feats = 64
    out_feats = NUM_SECURITY_FLAGS  # 只輸出 13 個安全 flags
    
    # 初始化
    generator = Generator(in_feats, hidden_feats, out_feats)
    trainer = RLTrainer(generator, lr=1e-4)
    
    # 訓練設定
    num_epochs = 20
    training_log = []
    
    print(f"\n開始訓練 ({num_epochs} epochs)...")
    total_start_time = time.time()
    
    for epoch in range(num_epochs):
        epoch_start = time.time()
        avg_vuln_change = trainer.train_epoch(pyg_data_list, file_paths, batch_size=4)
        epoch_time = time.time() - epoch_start
        
        # 記錄這個 epoch 的數據
        epoch_data = {
            "epoch": epoch + 1,
            "time_seconds": round(epoch_time, 1),
            "avg_vuln_change": round(avg_vuln_change, 4),
            "baseline": round(trainer.baseline, 4)
        }
        training_log.append(epoch_data)
        
        print(f"\n[Epoch {epoch+1}/{num_epochs}] "
              f"Time: {epoch_time:.1f}s | "
              f"Avg Vuln Change: {avg_vuln_change:+.2f} | "
              f"Baseline: {trainer.baseline:.2f}")
    
    # 計算總時間
    total_time = time.time() - total_start_time
    total_minutes = total_time / 60
    
    # 儲存訓練日誌
    log_data = {
        "total_epochs": num_epochs,
        "total_time_seconds": round(total_time, 1),
        "total_time_minutes": round(total_minutes, 2),
        "epochs": training_log
    }
    
    with open("training_log.json", "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    # 儲存模型
    torch.save(generator.state_dict(), "trained_generator_rl.pt")
    
    print(f"\n{'='*50}")
    print(f"訓練完成！")
    print(f"總時間: {total_minutes:.1f} 分鐘 ({total_time:.0f} 秒)")
    print(f"模型已儲存為: trained_generator_rl.pt")
    print(f"訓練日誌已儲存為: training_log.json")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
