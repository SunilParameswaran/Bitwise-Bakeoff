"""Run weighted Leiden and export both graphs for Gephi."""

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

import igraph as ig


ROOT = Path(__file__).resolve().parent.parent
SEED = 42
RESOLUTION = 1.0
MIN_COMMUNITY_SIZE = 8
MAX_COMMUNITY_SIZE = 35


def detect_communities(graph, min_size=MIN_COMMUNITY_SIZE, max_size=MAX_COMMUNITY_SIZE):
    """Split large groups locally; merge small, linked groups when feasible."""
    if min_size < 1 or max_size < min_size:
        raise ValueError("Community sizes must satisfy 1 <= min_size <= max_size")
    working = graph.copy()
    working.vs["original_index"] = list(range(graph.vcount()))
    pending = list(working.connected_components())
    groups = []
    ig.set_random_number_generator(random.Random(SEED))

    while pending:
        vertices = pending.pop(0)
        if len(vertices) <= max_size:
            groups.append(vertices)
            continue
        subgraph = working.induced_subgraph(vertices)
        # Restart at the base resolution within each oversized community.
        for factor in (1, 1.5, 2, 3, 4, 8, 16):
            parts = subgraph.community_leiden(
                objective_function="modularity", weights="weight",
                resolution=RESOLUTION * factor, n_iterations=-1,
            )
            if len(parts) > 1:
                break
        if len(parts) == 1:
            groups.append(vertices)
            continue
        pending.extend([
            [subgraph.vs[index]["original_index"] for index in part]
            for part in parts
        ])

    while True:
        owners = {vertex: index for index, group in enumerate(groups) for vertex in group}
        links = defaultdict(float)
        for edge in graph.es:
            a, b = owners[edge.source], owners[edge.target]
            if a != b:
                links[tuple(sorted((a, b)))] += edge["weight"]
        candidates = []
        for i, group in enumerate(groups):
            if len(group) >= min_size:
                continue
            for j, target in enumerate(groups):
                if i == j or len(group) + len(target) > max_size:
                    continue
                weight = links.get(tuple(sorted((i, j))), 0)
                if weight > 0:
                    candidates.append((weight / (len(group) * len(target)), i, j))
        if not candidates:
            break
        _, i, j = max(candidates)
        groups[i].extend(groups[j])
        groups.pop(j)

    membership = [None] * graph.vcount()
    for community, group in enumerate(sorted(groups, key=min)):
        for vertex in group:
            membership[vertex] = community
    return membership


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                for key, value in row.items()
            })


def export_graph(graph, directory):
    directory.mkdir(parents=True, exist_ok=True)
    attributes = [a for a in graph.vs.attributes() if a not in ("name", "label")]
    write_csv(directory / "nodes.csv", ["Id", "Label"] + attributes, (
        {"Id": vertex["name"], "Label": vertex["label"], **{a: vertex[a] for a in attributes}}
        for vertex in graph.vs
    ))
    attributes = [a for a in graph.es.attributes() if a != "weight"]
    write_csv(directory / "edges.csv", ["Source", "Target", "Type", "Weight"] + attributes, (
        {"Source": graph.vs[edge.source]["name"], "Target": graph.vs[edge.target]["name"],
         "Type": "Undirected", "Weight": edge["weight"], **{a: edge[a] for a in attributes}}
        for edge in graph.es
    ))
    graph.write_pickle(str(directory / "graph.pickle"))


def main():
    ingredients = ig.Graph.Read_Pickle(str(ROOT / "output/ingredients/graph.pickle"))
    bipartite = ig.Graph.Read_Pickle(str(ROOT / "output/recipe_ingredients/graph.pickle"))
    communities = detect_communities(ingredients)
    ingredients.vs["community"] = communities
    membership = dict(zip(ingredients.vs["name"], communities))
    bipartite.vs["community"] = [membership.get(v["name"]) for v in bipartite.vs]
    for graph in (ingredients, bipartite):
        graph["community_method"] = "recursive_leiden_with_size_controls"
        graph["community_resolution"] = RESOLUTION
        graph["community_seed"] = SEED
        graph["community_min_size"] = MIN_COMMUNITY_SIZE
        graph["community_max_size"] = MAX_COMMUNITY_SIZE
    export_graph(bipartite, ROOT / "output/recipe_ingredients")
    export_graph(ingredients, ROOT / "output/ingredients")
    sizes = [communities.count(group) for group in sorted(set(communities))]
    if sizes:
        print(f"Saved {len(sizes)} communities ({min(sizes)}–{max(sizes)} ingredients) and Gephi CSVs.")
        if min(sizes) < MIN_COMMUNITY_SIZE or max(sizes) > MAX_COMMUNITY_SIZE:
            print("Some size limits could not be met without forcing unsupported groups.")
    else:
        print("Saved empty graphs and Gephi CSVs.")


if __name__ == "__main__":
    main()
