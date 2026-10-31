import json
import math
from pathlib import Path

import igraph as ig

BASE_DIR = Path(__file__).resolve().parent.parent


def load_json(filename: str):
    path = BASE_DIR / "data" / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ingredients():
    path = BASE_DIR / "output/ingredients/graph.pickle"
    if not path.exists():
        raise FileNotFoundError("Run the four numbered scripts in net_pipeline/ first.")
    graph = ig.Graph.Read_Pickle(str(path))
    ingredient_db = {}
    for vertex in graph.vs:
        name = vertex["ingredient"]
        ingredient_db[name] = {
            "name": name,
            "label": vertex["label"],
            "community": vertex["community"],
            "recipe_count": vertex["recipe_count"],
            "relative_quantities": vertex["relative_quantities"],
            "known_mass_fractions": vertex["known_mass_fractions"],
            "neighbors": {},
            "affinities": {},
        }
    for edge in graph.es:
        a = graph.vs[edge.source]["ingredient"]
        b = graph.vs[edge.target]["ingredient"]
        count = edge["weight"]
        # Cosine association: shared recipes / sqrt(freq(a) * freq(b)).
        affinity = count / math.sqrt(
            ingredient_db[a]["recipe_count"] * ingredient_db[b]["recipe_count"]
        )
        ingredient_db[a]["neighbors"][b] = count
        ingredient_db[b]["neighbors"][a] = count
        ingredient_db[a]["affinities"][b] = affinity
        ingredient_db[b]["affinities"][a] = affinity
    return ingredient_db


def load_recipes():
    return [
        {"name": recipe["label"], "source_id": recipe["name"],
         "source": recipe["url"], "ingredients": list(recipe["ingredients"])}
        for recipe in load_json("recipes.json")
        if recipe["category"].strip().casefold() == "dolci" and recipe["ingredients"]
    ]


def validate_knowledgebase(ingredient_db, recipes):
    if not ingredient_db or not recipes:
        raise ValueError("The network and inspiring set must be non-empty.")
    missing = []
    for recipe in recipes:
        for ingredient in recipe["ingredients"]:
            if ingredient not in ingredient_db:
                missing.append((recipe["name"], ingredient))
    if missing:
        detail = ", ".join(f"{r}: {i}" for r, i in missing)
        raise ValueError(f"Unknown ingredients in recipes: {detail}")
