"""Build the bipartite recipe–ingredient graph from the cleaned recipes."""

import json
from pathlib import Path

import igraph as ig


ROOT = Path(__file__).resolve().parent.parent


def build_bipartite_graph(recipes):
    labels = {}
    for recipe in recipes:
        for name, ingredient in recipe["ingredients"].items():
            labels.setdefault(name, ingredient["label"])
    names = sorted(labels)
    ingredient_index = {name: index for index, name in enumerate(names)}
    recipe_count = len(recipes)
    relative_quantities = [[] for _ in names]
    known_mass_fractions = [[] for _ in names]
    edges = []
    edge_data = []
    for recipe_index, recipe in enumerate(recipes):
        total = recipe["known_mass_g"]
        for name, ingredient in recipe["ingredients"].items():
            index = ingredient_index[name]
            fraction = ingredient["mass_g"] / total if total > 0 and ingredient["mass_g"] > 0 else None
            relative = fraction if recipe["mass_complete"] else None
            if fraction is not None:
                known_mass_fractions[index].append(fraction)
            if relative is not None:
                relative_quantities[index].append(relative)
            edges.append((recipe_index, recipe_count + index))
            edge_data.append({
                "quantities": ingredient["quantities"],
                "mass_sources": ingredient["sources"],
                "known_mass_g": ingredient["mass_g"],
                "known_mass_fraction": fraction,
                "relative_quantity": relative,
            })

    bipartite = ig.Graph(n=recipe_count + len(names), edges=edges)
    bipartite.vs["name"] = [r["name"] for r in recipes] + [f"ingredient_{i}" for i in range(len(names))]
    bipartite.vs["label"] = [r["label"] for r in recipes] + [labels[n] for n in names]
    bipartite.vs["type"] = [False] * recipe_count + [True] * len(names)
    bipartite.vs["kind"] = ["recipe"] * recipe_count + ["ingredient"] * len(names)
    bipartite.vs["ingredient"] = [None] * recipe_count + names
    bipartite.vs["relative_quantities"] = [None] * recipe_count + relative_quantities
    bipartite.vs["known_mass_fractions"] = [None] * recipe_count + known_mass_fractions
    for attribute in ("category", "url", "servings", "known_mass_g", "mass_complete"):
        bipartite.vs[attribute] = [r[attribute] for r in recipes] + [None] * len(names)
    bipartite.es["weight"] = [1] * len(edges)
    for attribute in ("quantities", "mass_sources", "known_mass_g", "known_mass_fraction", "relative_quantity"):
        bipartite.es[attribute] = [edge[attribute] for edge in edge_data]
    bipartite.vs["recipe_count"] = [None] * recipe_count + bipartite.degree()[recipe_count:]

    return bipartite


def main():
    recipes = json.loads((ROOT / "data/recipes.json").read_text(encoding="utf-8"))
    graph = build_bipartite_graph(recipes)
    directory = ROOT / "output/recipe_ingredients"
    directory.mkdir(parents=True, exist_ok=True)
    graph.write_pickle(str(directory / "graph.pickle"))
    print("Saved output/recipe_ingredients/graph.pickle")


if __name__ == "__main__":
    main()
