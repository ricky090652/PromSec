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


def get_node_features(graph, node):
    """
    Extract binary features from CFG nodes.

    Parameters:
        graph (DiGraph): The graph containing the node.
        node: The node from which to extract features.

    Returns:
        list: List of binary features extracted from the node.
    """
    features = []

    # Get node attributes from the graph
    node_data = graph.nodes[node]

    # Extract binary features from node attributes.
    has_function_def = node_data.get('contains_function', False)
    features.append(int(has_function_def))

    has_loop = node_data.get('contains_loop', False)
    features.append(int(has_loop))

    has_conditional = node_data.get('contains_if', False)
    features.append(int(has_conditional))

    has_comment = node_data.get('contains_comment', False)
    features.append(int(has_comment))

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


def extract_graph_from_pyg_data(pyg_data):
    """
    Extract a NetworkX graph from a PyG Data object.
    """
    edge_index = pyg_data.edge_index
    num_nodes = pyg_data.x.size(0)

    # Create a NetworkX graph
    graph = nx.Graph()
    graph.add_nodes_from(range(num_nodes))
    graph.add_edges_from(edge_index.t().tolist())

    return graph


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
    """
    command = f"bandit -f json {filename}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout


def generate_cfg_from_code(file_path):
    """
    Generate a Control Flow Graph (CFG) from a Python source file.
    """
    with open(file_path, 'r') as f:
        code = f.read()

    # Parse the Python source code into an AST
    tree = ast.parse(code)

    # Start generating the CFG
    cfg = nx.DiGraph()
    build_cfg_from_ast(tree, cfg)

    return cfg


def build_cfg_from_ast(node, graph, prev_node=None):
    """
    Build a Control Flow Graph (CFG) from an AST node.
    """
    if not hasattr(build_cfg_from_ast, "_counter"):
        build_cfg_from_ast._counter = 0

    def new_id(prefix=None):
        i = build_cfg_from_ast._counter
        build_cfg_from_ast._counter += 1
        if prefix:
            return f"{prefix}_{i}"
        return f"N_{i}"

    def add_node_for(ast_node, node_id=None):
        nid = node_id if node_id is not None else new_id(type(ast_node).__name__)
        #semantic_attrs = extract_semantic_features(ast_node)
        attrs = {
                "ast_node": ast_node,
                "contains_function": isinstance(ast_node, ast.FunctionDef),
                "contains_loop": isinstance(ast_node, (ast.For, ast.While)),
                "contains_if": isinstance(ast_node, ast.If),
                "contains_comment": False,
            }
        #attrs.update(semantic_attrs)
        graph.add_node(nid, **attrs)
        return nid

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


    print("before node isinstance stmt")
    # Only handle statements for CFG nodes
    if isinstance(node, ast.stmt):
        # prefer lineno for readability when present
        print("node isinstance stmt")
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
            print("node isinstance If")
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
            print("node isinstance For/While")
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
            print("node isinstance FunctionDef")    
            # create function node already as curr; build body but don't connect its exit to sequential flow
            # we still add the body subgraph to allow intra-function CFG
            _ = build_cfg_from_ast(node.body, graph, curr)
            # function def acts as a single top-level statement for caller flow
            return curr

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

