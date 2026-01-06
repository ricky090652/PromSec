import ast
import networkx as nx
import torch
import difflib
import tokenize
from io import BytesIO
import subprocess
import json
from prettytable import PrettyTable
import matplotlib.pyplot as plt


AST_TYPES = [
    "FunctionDef", "AsyncFunctionDef", "ClassDef", "Return", "Delete",
    "Assign", "AugAssign", "AnnAssign", "For", "AsyncFor", "While", "If",
    "With", "AsyncWith", "Raise", "Try", "Assert", "Import", "ImportFrom",
    "Global", "Nonlocal", "Expr", "Pass", "Break", "Continue", "Call",
    "Name", "Attribute", "Constant", "BinOp", "UnaryOp", "Lambda", "IfExp",
    "Dict", "Set", "ListComp", "SetComp", "DictComp", "GeneratorExp",
    "Await", "Yield", "YieldFrom", "Compare", "BoolOp", "Module"
]


def generate_graph_from_ast(node):
    """
    Generate a graph from an Abstract Syntax Tree (AST).

    Parameters:
        node (ast.AST): The root node of the AST.

    Returns:
        nx.Graph: Graph representation of the AST.
    """
    G = nx.Graph()

    def traverse_tree(curr_node, parent_id=None):
        nonlocal node_id
        curr_id = node_id
        G.add_node(curr_id, features=get_node_features(curr_node))

        if parent_id is not None:
            G.add_edge(parent_id, curr_id)

        parent_id = curr_id
        node_id += 1

        for child in ast.iter_child_nodes(curr_node):
            traverse_tree(child, parent_id)

    node_id = 0
    traverse_tree(node)
    return G


# def get_node_features(graph, node):
#     """
#     Extract binary features from CFG nodes.

#     Parameters:
#         graph (DiGraph): The graph containing the node.
#         node: The node from which to extract features.

#     Returns:
#         list: List of binary features extracted from the node.
#     """
#     features = []

#     # Get node attributes from the graph
#     node_data = graph.nodes[node]

#     # Extract binary features from node attributes.
#     has_function_def = node_data.get('contains_function', False)
#     features.append(int(has_function_def))

#     has_loop = node_data.get('contains_loop', False)
#     features.append(int(has_loop))

#     has_conditional = node_data.get('contains_if', False)
#     features.append(int(has_conditional))

#     has_comment = node_data.get('contains_comment', False)
#     features.append(int(has_comment))

#     return features

def extract_semantic_features(node):
    """
    分析 AST 節點中的語義特徵，用於安全分析。
    """
    features = {
        "is_sensitive_call": False,
        "is_input_source": False,
        "has_string_concat": False,
        "has_constant_str": False,
        "is_sql_query": False,
        "is_file_operation": False,
        "is_network_call": False,
        "is_crypto_operation": False,
        "is_serialization": False,
        "uses_format_string": False,
    }

    
    sensitive_apis = {'system', 'popen', 'call', 'run', 'eval', 'exec'}
    input_apis = {'input', 'argv', 'environ', 'form', 'args', 'get', 'getlist'}
    sql_apis = {'execute', 'executemany', 'executescript', 'raw', 'rawSQL'}
    file_apis = {'open', 'read', 'write', 'readlines', 'writelines', 'remove', 'unlink', 'rmdir', 'makedirs'}
    network_apis = {'get', 'post', 'put', 'delete', 'request', 'urlopen', 'urlretrieve', 'socket', 'connect', 'send', 'recv'}
    crypto_apis = {'md5', 'sha1', 'random', 'randint', 'choice', 'DES', 'Blowfish'}  # 弱加密
    serialization_apis = {'load', 'loads', 'dump', 'dumps', 'pickle', 'unpickle', 'safe_load'}

    for sub_node in ast.walk(node):
        # function call
        if isinstance(sub_node, ast.Call):
            func_name = ""
            full_name = ""  
            
            if isinstance(sub_node.func, ast.Name):
                func_name = sub_node.func.id
                full_name = func_name
            elif isinstance(sub_node.func, ast.Attribute):
                func_name = sub_node.func.attr
                
                if isinstance(sub_node.func.value, ast.Name):
                    full_name = f"{sub_node.func.value.id}.{func_name}"
                else:
                    full_name = func_name
            
            # 1. sensitive call
            if func_name in sensitive_apis:
                features["is_sensitive_call"] = True
            
            # 2. input source
            if func_name in input_apis or 'request' in full_name.lower():
                features["is_input_source"] = True
            
            # 3. sql query
            if func_name in sql_apis or 'execute' in func_name.lower():
                features["is_sql_query"] = True
            
            # 4. file operation
            if func_name in file_apis:
                features["is_file_operation"] = True
            
            # 5. network call
            if func_name in network_apis or 'http' in full_name.lower() or 'requests' in full_name.lower():
                features["is_network_call"] = True
            
            # 6. crypto operation
            if func_name in crypto_apis or 'hashlib' in full_name.lower():
                features["is_crypto_operation"] = True
            
            # 7. serialization/deserialization (pickle, yaml, json)
            if func_name in serialization_apis or 'pickle' in full_name.lower() or 'yaml' in full_name.lower():
                features["is_serialization"] = True

        # string concat
        if isinstance(sub_node, ast.BinOp) and isinstance(sub_node.op, ast.Add):
            if isinstance(sub_node.left, (ast.Str, ast.JoinedStr)) or isinstance(sub_node.right, (ast.Str, ast.JoinedStr)):
                features["has_string_concat"] = True
        
        # string constant
        if isinstance(sub_node, (ast.Str, ast.Constant)):
            if isinstance(sub_node, ast.Str) or (isinstance(sub_node, ast.Constant) and isinstance(sub_node.value, str)):
                features["has_constant_str"] = True
        
        
        if isinstance(sub_node, ast.JoinedStr):
            features["uses_format_string"] = True
        if isinstance(sub_node, ast.Call):
            if isinstance(sub_node.func, ast.Attribute) and sub_node.func.attr == 'format':
                features["uses_format_string"] = True

    return features

def get_node_features(graph, node):
    """
    Extract features for a single CFG node.
    - Binary flags come from node attributes populated by build_cfg_from_ast.
    - Adds simple structural features (in/out degree) and a small normalized AST-type id.
    Returns a list of numeric features (ints/floats).
    """
    node_data = graph.nodes[node]

    # binary flags (ensure deterministic order)
    flags = [
        "contains_function",
        "contains_loop",
        "contains_if",
        "contains_comment",
        "is_return",
        "is_break",
        "is_continue",
        
        "is_sensitive_call",
        "is_input_source",
        "has_string_concat",
        "has_constant_str",
        
        "is_sql_query",
        "is_file_operation",
        "is_network_call",
        "is_crypto_operation",
        "is_serialization",
        "uses_format_string",
        # Bandit-based features (from static analysis)
        "bandit_high_severity",
        "bandit_medium_severity",
        "bandit_low_severity",
    ]
    features = [int(bool(node_data.get(f, False))) for f in flags]

    # structural features
    try:
        # directed graph: use in/out degree; otherwise use degree for both
        if graph.is_directed():
            in_deg = graph.in_degree(node)
            out_deg = graph.out_degree(node)
        else:
            deg = graph.degree(node)
            in_deg = deg
            out_deg = deg
    except Exception:
        in_deg = 0
        out_deg = 0

    features.append(float(in_deg))
    features.append(float(out_deg))

    # One-Hot Encoding for AST node type (deterministic, no ordering)
    ast_node = node_data.get("ast_node", None)
    current_type = type(ast_node).__name__ if ast_node is not None else "None"
    
    # generate One-Hot vector
    one_hot = [0] * len(AST_TYPES)
    if current_type in AST_TYPES:
        index = AST_TYPES.index(current_type)
        one_hot[index] = 1
    # 若類型不在列表內，全為 0 (表示 'Other' 或未知類型)
    
    features.extend(one_hot)  # One-Hot接在原本特徵後面

    return features



def adjacency_matrix_to_edge_index(adj_matrix):
    """
    Convert an adjacency matrix to edge indices.

    Parameters:
        adj_matrix (scipy.sparse.csr_matrix): Adjacency matrix.

    Returns:
        torch.Tensor: Edge indices in the form of a tensor.
    """
    edge_index = torch.tensor(adj_matrix.nonzero(), dtype=torch.long)
    return edge_index


def calculate_similarity1(c1, c2):
    tokens1 = get_tokens(c1)
    tokens2 = get_tokens(c2)

    matcher = difflib.SequenceMatcher(None, tokens1, tokens2)
    return matcher.ratio()


def get_tokens(code):
    tokens = []
    for token in tokenize.tokenize(BytesIO(code.encode('utf-8')).readline):
        tokens.append(token.string)
    return tokens


class NormalizeNames(ast.NodeTransformer):
    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id='_VAR_', ctx=node.ctx), node)
    
    def visit_FunctionDef(self, node):
        node.name = "_FUNC_"
        return self.generic_visit(node)


def get_normalized_ast(code):
    tree = ast.parse(code)
    normalizer = NormalizeNames()
    normalized_tree = normalizer.visit(tree)
    return normalized_tree


def ast_structure(node):
    if isinstance(node, ast.AST):
        node_tag = type(node).__name__
        children = [ast_structure(child) for child in ast.iter_child_nodes(node)]
        if children:
            return {node_tag: children}
        else:
            return node_tag
    else:
        return str(node)


def calculate_similarity2(tree1, tree2):
    matcher = difflib.SequenceMatcher(None, str(tree1), str(tree2))
    return matcher.ratio()


def calculate_similarity(c1, c2):
    tokens1 = get_tokens(c1)
    tokens2 = get_tokens(c2)

    matcher = difflib.SequenceMatcher(None, tokens1, tokens2)
    return matcher.ratio()


def extract_graph_from_pyg_data(pyg_data, show_plot=False):
    """
    Extract a NetworkX DiGraph from a PyG Data object, preserving node features.
    If pyg_data has 'node_names' attribute, use those as node IDs instead of indices.
    """
    edge_index = pyg_data.edge_index
    x = pyg_data.x
    num_nodes = x.size(0)

    # Check if we have original node names
    has_names = hasattr(pyg_data, 'node_names') and pyg_data.node_names is not None
    node_names = pyg_data.node_names if has_names else list(range(num_nodes))

    # Create a NetworkX DiGraph (CFGs are directed)
    graph = nx.DiGraph()
    for i in range(num_nodes):
        node_id = node_names[i]
        feat_list = x[i].tolist() if hasattr(x[i], 'tolist') else x[i]
        graph.add_node(node_id, features=feat_list)

    # Add edges using node names
    if edge_index.numel() > 0:
        edges = edge_index.t().tolist()
        for u_idx, v_idx in edges:
            graph.add_edge(node_names[u_idx], node_names[v_idx])

    if show_plot:
        nx.draw(graph, with_labels=True)
        plt.show()
    return graph


def cfg_to_pyg_data(cfg):
    """
    Convert a NetworkX CFG to PyG Data, preserving node names.
    Returns a PyG Data object with 'node_names' attribute.
    """
    node_list = list(cfg.nodes())
    node_to_idx = {n: i for i, n in enumerate(node_list)}
    
    # Extract features
    x_list = []
    for node in node_list:
        feats = cfg.nodes[node].get('features', get_node_features(cfg, node))
        x_list.append(feats)
    
    x = torch.tensor(x_list, dtype=torch.float)
    
    # Build edge index
    edges = list(cfg.edges())
    if edges:
        edge_index = torch.tensor(
            [[node_to_idx[u], node_to_idx[v]] for u, v in edges],
            dtype=torch.long
        ).t().contiguous()
    else:
        edge_index = torch.empty((2, 0), dtype=torch.long)
    
    from torch_geometric.data import Data
    data = Data(x=x, edge_index=edge_index)
    data.node_names = node_list  # Preserve original node names
    return data


def cfg_to_dot(G, include_features=True):
    """
    Convert a CFG (NetworkX DiGraph) to DOT format string.
    LLMs like GPT-4 can understand DOT/GraphViz format well.
    
    Parameters:
        G: NetworkX DiGraph (CFG)
        include_features: If True, include active semantic features in node labels
    
    Returns:
        str: DOT format representation of the CFG
    """
    feature_names = [
        "contains_function", "contains_loop", "contains_if", "contains_comment",
        "is_return", "is_break", "is_continue",
        "is_sensitive_call", "is_input_source", "has_string_concat", "has_constant_str",
        "is_sql_query", "is_file_operation", "is_network_call",
        "is_crypto_operation", "is_serialization", "uses_format_string",
        "in_degree", "out_degree"
    ]
    
    lines = ["digraph CFG {"]
    lines.append('    rankdir=TB;')
    lines.append('    node [shape=box];')
    
    for node in G.nodes():
        data = G.nodes[node]
        label_parts = [str(node)]
        
        if include_features:
            feats = data.get('features', [])
            active_flags = []
            # Check semantic flags (indices 0-16 are binary flags)
            for i in range(min(len(feats), 17)):
                if i < len(feature_names) and feats[i] > 0.5:
                    active_flags.append(feature_names[i])
            if active_flags:
                label_parts.append(f"[{', '.join(active_flags)}]")
        
        label = '\\n'.join(label_parts)
        lines.append(f'    "{node}" [label="{label}"];')
    
    for u, v in G.edges():
        lines.append(f'    "{u}" -> "{v}";')
    
    lines.append("}")
    return "\n".join(lines)


def cfg_to_json(G, include_features=True):
    """
    Convert a CFG (NetworkX DiGraph) to JSON format string.
    Structured format that LLMs can parse easily.
    
    Parameters:
        G: NetworkX DiGraph (CFG)
        include_features: If True, include feature vectors in output
    
    Returns:
        str: JSON representation of the CFG
    """
    feature_names = [
        "contains_function", "contains_loop", "contains_if", "contains_comment",
        "is_return", "is_break", "is_continue",
        "is_sensitive_call", "is_input_source", "has_string_concat", "has_constant_str",
        "is_sql_query", "is_file_operation", "is_network_call",
        "is_crypto_operation", "is_serialization", "uses_format_string"
    ]
    
    nodes_dict = {}
    for node in G.nodes():
        data = G.nodes[node]
        feats = data.get('features', [])
        
        node_info = {"id": str(node)}
        if include_features and feats:
            # Convert to named dict for readability
            active_flags = {}
            for i, name in enumerate(feature_names):
                if i < len(feats) and feats[i] > 0.5:
                    active_flags[name] = True
            if active_flags:
                node_info["flags"] = active_flags
            # Include degree info
            if len(feats) > 17:
                node_info["in_degree"] = feats[17]
                node_info["out_degree"] = feats[18]
        
        nodes_dict[str(node)] = node_info
    
    edges_list = [[str(u), str(v)] for u, v in G.edges()]
    
    result = {
        "num_nodes": len(G.nodes()),
        "num_edges": len(G.edges()),
        "nodes": nodes_dict,
        "edges": edges_list
    }
    
    return json.dumps(result, indent=2)


def create_cfg_diff_prompt(original_code, original_cfg, updated_cfg, format="dot"):
    """
    Create a prompt for LLM to generate updated code based on CFG changes.
    Instead of manually translating feature changes, directly show CFG structure to LLM.
    
    Parameters:
        original_code: str, the original Python source code
        original_cfg: NetworkX DiGraph, the original CFG
        updated_cfg: NetworkX DiGraph, the GAN-optimized CFG
        format: "dot" or "json" - which format to use for CFG representation
    
    Returns:
        str: The prompt to send to LLM
    """
    if format == "dot":
        original_repr = cfg_to_dot(original_cfg)
        updated_repr = cfg_to_dot(updated_cfg)
        format_name = "DOT/GraphViz"
    else:
        original_repr = cfg_to_json(original_cfg)
        updated_repr = cfg_to_json(updated_cfg)
        format_name = "JSON"
    
    prompt = f"""You are a security-focused Python code refactoring assistant.

## Original Code:
```python
{original_code}
```

## Original Control Flow Graph ({format_name} format):
```
{original_repr}
```

## Updated Control Flow Graph (after security optimization):
```
{updated_repr}
```

## Task:
Analyze the structural and semantic changes between the two CFGs, then generate updated Python code that:

1. **Maintains original functionality** - The code should do the same thing
2. **Reflects CFG structural changes** - If nodes were added/removed, reflect that in code structure
3. **Addresses security improvements** - Focus on nodes where security flags changed:
   - `is_sensitive_call`: dangerous function calls (eval, exec, system, etc.)
   - `is_input_source`: user input handling
   - `has_string_concat`: string concatenation (potential injection)
   - `is_sql_query`: SQL operations
   - `is_file_operation`: file I/O
   - `is_serialization`: pickle/yaml operations

## Security Transformation Guidelines:
- If `is_sensitive_call` decreased: Replace dangerous calls with safer alternatives
- If `is_input_source` handling improved: Add input validation/sanitization
- If `has_string_concat` for queries reduced: Use parameterized queries instead
- If `is_serialization` flags changed: Use safe deserialization methods

Provide ONLY the updated Python code, properly formatted and ready to run.
"""
    return prompt


def describe_graph(graph, original_graph=None):
    """
    Generate a human-readable description of the CFG and its semantic features for the LLM.
    If original_graph is provided, highlights significant feature changes (GNN optimizations).
    """
    # 特徵名稱：前 19 個語義特徵 + 2 個結構特徵 + One-Hot (AST types)
    feature_names = [
        "contains_function", "contains_loop", "contains_if", "contains_comment",
        "is_return", "is_break", "is_continue", 
        "is_sensitive_call", "is_input_source", "has_string_concat", "has_constant_str",
        
        "is_sql_query", "is_file_operation", "is_network_call",
        "is_crypto_operation", "is_serialization", "uses_format_string",
        "in_degree", "out_degree"
    ] + [f"type_{t}" for t in AST_TYPES]

    description = []
    description.append(f"CFG Structure: {len(graph.nodes)} nodes, {len(graph.edges)} edges.")
    
    for node in sorted(graph.nodes):
        feats = graph.nodes[node].get('features', [])
        if not feats:
            continue
            
        node_desc = [f"Node {node}:"]
        
        # Add semantic flags that are 'active' (threshold > 0.5 for GNN outputs)
        active_flags = []
        for i in range(min(len(feats), 11)): # First 11 are binary-ish flags
            if feats[i] > 0.5:
                active_flags.append(feature_names[i])
        
        if active_flags:
            node_desc.append(f"  Flags: {', '.join(active_flags)}")
        
        # Check for optimization shifts if original_graph is provided
        if original_graph and node in original_graph.nodes:
            orig_feats = original_graph.nodes[node].get('features', [])
            if orig_feats:
                shifts = []
                for i in [7, 8, 9]: # Focus on security features: sensitive_call, input_source, string_concat
                    if feats[i] > orig_feats[i] + 0.1:
                        shifts.append(f"More attention to {feature_names[i]}")
                    elif feats[i] < orig_feats[i] - 0.1:
                        shifts.append(f"Less {feature_names[i]} risk")
                if shifts:
                    node_desc.append(f"  GNN Optimization Hints: {', '.join(shifts)}")
        
        description.append("\n".join(node_desc))
    
    return "\n".join(description)


def load_original_code(file_path):
    """
    Load the original code from a file.
    """
    with open(file_path, 'r') as file:
        return file.read()


def compare_asts(tree1, tree2):
    """
    Compare two ASTs and return a similarity measure.
    """
    nodes1 = list(ast.walk(tree1))
    nodes2 = list(ast.walk(tree2))

    common_nodes = len([node for node in nodes1 if any(isinstance(node, type(other)) for other in nodes2)])

    return common_nodes / max(len(nodes1), len(nodes2))


def calc_diff(code1, code2):
    """
    Calculate the difference between two pieces of code based on their AST structures.
    """
    try:
        tree1 = ast.parse(code1)
        tree2 = ast.parse(code2)
        return compare_asts(tree1, tree2)
    except SyntaxError:
        print("Syntax error encountered while calculating AST difference.")
        return float('inf')  # Return a large value to indicate a "large difference" due to the syntax error.


def VCS(generated_graph):
    """
    Perform the VCS (Vulnerability Check System) analysis on a graph.
    """
    adjacency_matrix = (generated_graph > 0).int()
    # Convert adjacency matrix to an edge list
    edges = torch.nonzero(adjacency_matrix, as_tuple=False)
    # Generate a code representation from the edge list
    code_lines = []
    for edge in edges:
        code_line = f"add_edge({edge[0]}, {edge[1]})"
        code_lines.append(code_line)
    code_representation = "\n".join(code_lines)
    # Now, pass the code representation to the calculate_vcs function
    cwe_count = calculate_vcs(code_representation)
    return cwe_count


def run_bandit(filename):
    """
    Run the Bandit static code analyzer on a Python file.
    Returns a list of dictionaries, each representing a vulnerability.
    Each issue contains: line_number, severity, confidence, issue_text, test_id, etc.
    """
    import sys
    import os
    
    # Try to find bandit in the same directory as the Python executable
    python_dir = os.path.dirname(sys.executable)
    bandit_path = os.path.join(python_dir, 'bandit.exe') if os.name == 'nt' else os.path.join(python_dir, 'bandit')
    
    if not os.path.exists(bandit_path):
        bandit_path = 'bandit'  # Fallback to PATH
    
    command = f'"{bandit_path}" -f json "{filename}"'
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            json_output = json.loads(result.stdout)
            return json_output.get('results', [])
        return []
    except Exception as e:
        print(f"Error running bandit: {e}")
        return []


def enrich_cfg_with_bandit(cfg, bandit_results):
    """
    Enrich CFG nodes with Bandit scan results.
    Maps Bandit findings to CFG nodes based on line numbers.
    
    Parameters:
        cfg: NetworkX DiGraph (CFG)
        bandit_results: list of Bandit issue dicts from run_bandit()
    """
    from collections import defaultdict
    
    # Build line -> issues mapping
    issues_by_line = defaultdict(list)
    for issue in bandit_results:
        line_no = issue.get('line_number')
        if line_no:
            issues_by_line[line_no].append(issue)
    
    # Enrich each node
    for node_id in cfg.nodes:
        node_data = cfg.nodes[node_id]
        ast_node = node_data.get('ast_node')
        
        # Get line number from AST node
        line_no = None
        if ast_node and hasattr(ast_node, 'lineno'):
            line_no = ast_node.lineno
        
        # Initialize bandit flags
        node_data['bandit_high_severity'] = False
        node_data['bandit_medium_severity'] = False
        node_data['bandit_low_severity'] = False
        node_data['bandit_issues'] = []  # Store full issue details
        
        if line_no and line_no in issues_by_line:
            node_data['bandit_issues'] = issues_by_line[line_no]
            for issue in issues_by_line[line_no]:
                severity = issue.get('issue_severity', '').upper()
                if severity == 'HIGH':
                    node_data['bandit_high_severity'] = True
                elif severity == 'MEDIUM':
                    node_data['bandit_medium_severity'] = True
                elif severity == 'LOW':
                    node_data['bandit_low_severity'] = True


def generate_cfg_from_code(file_path, run_bandit_scan=True):
    """
    Generate a Control Flow Graph (CFG) from a Python source file.
    
    Parameters:
        file_path: path to the Python file
        run_bandit_scan: if True, run Bandit and enrich nodes with vulnerability info
    
    Returns:
        cfg: NetworkX DiGraph with enriched node features
    """
    with open(file_path, 'r') as f:
        code = f.read()

    # Parse the Python source code into an AST
    tree = ast.parse(code)
    
    # Start generating the CFG
    cfg = nx.DiGraph()
    build_cfg_from_ast(tree, cfg)
    
    # Run Bandit and enrich nodes with vulnerability information
    if run_bandit_scan:
        bandit_results = run_bandit(file_path)
        if bandit_results:
            enrich_cfg_with_bandit(cfg, bandit_results)
            #print(f"[Bandit] Found {len(bandit_results)} issues in {file_path}")

    return cfg


# def build_cfg_from_ast(node, graph, prev_node=None):
#     """
#     Build a Control Flow Graph (CFG) from an AST node.
#     """
#     if isinstance(node, ast.stmt):
#         current_node = str(node.lineno)
#         graph.add_node(current_node, ast_node=node)

#         if prev_node is not None:
#             graph.add_edge(prev_node, current_node)

#         # Special handling for control structures
#         if isinstance(node, ast.If):
#             build_cfg_from_ast(node.body, graph, current_node)
#             build_cfg_from_ast(node.orelse, graph, current_node)
#             return
#         elif isinstance(node, (ast.For, ast.While)):
#             build_cfg_from_ast(node.body, graph, current_node)
#             return

#         prev_node = current_node

#     elif isinstance(node, list):
#         for child in node:
#             prev_node = build_cfg_from_ast(child, graph, prev_node)

#     return prev_node

def build_cfg_from_ast(node, graph, prev_node=None):
    """
    Build a more robust Control Flow Graph (CFG) from an AST node.

    - 每個加入的節點會用唯一 id（type_counter 或 lineno）標識。
    - node attributes 會包含:
        - ast_node: 原始 AST 節點
        - contains_function/contains_loop/contains_if/contains_comment (bool)
        - is_return/is_break/is_continue (bool)
    - 回傳值: 最後一個應當作為後續連接點的節點 id，或 None（表示該片段不會自然連回序列，例如 return/break）
    - 支援: Module, list, If, For, While, FunctionDef, Return, Break, Continue, With, Try 基本處理
    """
    # 初始化 counter（第一次呼叫時建立）
    if not hasattr(build_cfg_from_ast, "_counter"):
        build_cfg_from_ast._counter = 0

    def new_id(prefix=None):
        i = build_cfg_from_ast._counter
        build_cfg_from_ast._counter += 1
        if prefix:
            return f"{prefix}_{i}"
        return f"N_{i}"

    # Helper: add node with attributes
    def add_node_for(ast_node, node_id=None):
        nid = node_id if node_id is not None else new_id(type(ast_node).__name__)
        semantic_attrs = extract_semantic_features(ast_node)
        attrs = {
            "ast_node": ast_node,
            "contains_function": isinstance(ast_node, ast.FunctionDef),
            "contains_loop": isinstance(ast_node, (ast.For, ast.While)),
            "contains_if": isinstance(ast_node, ast.If),
            "contains_comment": False,  # 註解需額外用 tokenize 判斷行號才能標記
            "is_return": isinstance(ast_node, ast.Return),
            "is_break": isinstance(ast_node, ast.Break),
            "is_continue": isinstance(ast_node, ast.Continue),
        }
        attrs.update(semantic_attrs)
        graph.add_node(nid, **attrs)
        return nid


    # If the node is a Module (top-level), iterate its body sequentially
    if isinstance(node, ast.Module):
        last = prev_node
        for child in node.body:
            last = build_cfg_from_ast(child, graph, last)
        return last

    # If we got a list of statements, process sequentially
    if isinstance(node, list):
        last = prev_node
        for child in node:
            last_child = build_cfg_from_ast(child, graph, last)
            # If child returned None (e.g., return), we stop sequence continuation
            if last_child is None:
                last = None
            else:
                last = last_child
        return last

    # Only handle statements for CFG nodes
    if isinstance(node, ast.stmt):
        # prefer lineno for readability when present
        if hasattr(node, "lineno"):
            node_id = f"LN{getattr(node, 'lineno')}_{type(node).__name__}"
        else:
            node_id = new_id(type(node).__name__)

        curr = add_node_for(node, node_id)

        # connect from prev sequential node
        if prev_node is not None:
            try:
                graph.add_edge(prev_node, curr)
            except Exception:
                pass

        # handle statement kinds
        # 1) If: create condition node (curr) -> body & orelse -> join
        if isinstance(node, ast.If):
            # body and orelse are lists
            body_end = build_cfg_from_ast(node.body, graph, curr)
            orelse_end = build_cfg_from_ast(node.orelse, graph, curr)

            # create an explicit join node so subsequent statements have a single predecessor
            join_id = new_id("JOIN")
            graph.add_node(join_id, join=True)

            # connect branch ends to join (if branch empty, connect condition directly)
            if body_end is not None:
                graph.add_edge(body_end, join_id)
            else:
                graph.add_edge(curr, join_id)

            if orelse_end is not None:
                graph.add_edge(orelse_end, join_id)
            else:
                graph.add_edge(curr, join_id)

            return join_id

        # 2) For / While: create loop header (curr), body, back-edge, and provide an after-loop node
        elif isinstance(node, (ast.For, ast.While)):
            # body: entry from curr
            body_end = build_cfg_from_ast(node.body, graph, curr)

            # add back-edge from body_end to header if body_end exists
            if body_end is not None and body_end != curr:
                graph.add_edge(body_end, curr)

            # create a node representing the point after the loop (so subsequent statements connect here)
            after_loop = new_id("AFTER_LOOP")
            graph.add_node(after_loop, synthetic=True)
            # header can go to after_loop (loop exit)
            graph.add_edge(curr, after_loop)
            return after_loop

        # 3) FunctionDef: create function node; optionally build body as separate subgraph (not connected to caller flow)
        elif isinstance(node, ast.FunctionDef):
            # create function node already as curr; build body but don't connect its exit to sequential flow
            # we still add the body subgraph to allow intra-function CFG
            _ = build_cfg_from_ast(node.body, graph, curr)
            # function def acts as a single top-level statement for caller flow
            return curr

        # 4) Return / Break / Continue: mark and stop sequential continuation
        elif isinstance(node, (ast.Return, ast.Break, ast.Continue)):
            # these statements typically end control flow in the current block
            return None

        # 5) Try / With: best-effort: traverse contained bodies and create join
        elif isinstance(node, ast.Try):
            try_ends = []
            # main body
            body_end = build_cfg_from_ast(node.body, graph, curr)
            if body_end is not None:
                try_ends.append(body_end)
            # handlers
            for handler in node.handlers:
                h_end = build_cfg_from_ast(handler.body, graph, curr)
                if h_end is not None:
                    try_ends.append(h_end)
            # orelse and finalbody
            orelse_end = build_cfg_from_ast(node.orelse, graph, curr)
            if orelse_end is not None:
                try_ends.append(orelse_end)
            final_end = build_cfg_from_ast(node.finalbody, graph, curr)
            if final_end is not None:
                try_ends.append(final_end)

            # join
            join_id = new_id("JOIN")
            graph.add_node(join_id, join=True)
            if try_ends:
                for e in try_ends:
                    graph.add_edge(e, join_id)
            else:
                graph.add_edge(curr, join_id)
            return join_id

        # 6) With and other simple statements: if they have inner 'body'-like fields, traverse them
        else:
            last = curr
            for field in ("body", "orelse", "finalbody"):
                if hasattr(node, field):
                    sub = getattr(node, field)
                    if sub:
                        sub_end = build_cfg_from_ast(sub, graph, last)
                        if sub_end is not None:
                            last = sub_end
            # return the last node as continuation point
            return last

    # Non-statement nodes: do not change prev_node
    return prev_node