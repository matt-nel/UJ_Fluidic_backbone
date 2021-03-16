import networkx as nx
from networkx.readwrite.json_graph import node_link_graph
import json
import os


def load_graph(graph_path):
    script_dir = os.path.dirname(__file__)
    fp = os.path.join(script_dir, graph_path)
    try:
        with open(fp) as file:
            json_graph_dict = json.load(file)
    except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
        print(f'The JSON provided {fp} is invalid. \n {e}')

    graph = node_link_graph(json_graph_dict, directed=True, multigraph=True)
    return graph


def filter_invalid_paths(paths):
    valid_paths = []
    for path in paths:
        for step in path:
            if 'syringe' in step:
                valid_paths.append(path)
                break
    return valid_paths


gp = "module_connections.json"
graph = load_graph(gp)
print(graph.nodes)
path_gen = nx.algorithms.all_simple_paths(graph, "flask1", "flask2")
glist = [p for p in path_gen]
glist = filter_invalid_paths(glist)
print(list)
print(graph.nodes['syringe1']['class'])
print(graph.adj['syringe1'])
print(graph.adj['syringe1']['port'])
print(graph.edges['valve1'])



