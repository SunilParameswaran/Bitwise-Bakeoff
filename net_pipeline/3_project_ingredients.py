"""Project the bipartite graph onto ingredients, counting shared recipes."""

from pathlib import Path

import igraph as ig


ROOT = Path(__file__).resolve().parent.parent


def main():
    bipartite = ig.Graph.Read_Pickle(str(ROOT / "output/recipe_ingredients/graph.pickle"))
    # Equivalent to A.T @ A, with the diagonal removed, for binary A.
    ingredients = bipartite.bipartite_projection(which=1, multiplicity=True)
    for attribute in ("category", "url", "servings", "known_mass_g", "mass_complete", "community"):
        if attribute in ingredients.vs.attributes():
            del ingredients.vs[attribute]
    directory = ROOT / "output/ingredients"
    directory.mkdir(parents=True, exist_ok=True)
    ingredients.write_pickle(str(directory / "graph.pickle"))
    print("Saved output/ingredients/graph.pickle")


if __name__ == "__main__":
    main()
