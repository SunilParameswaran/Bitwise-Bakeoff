import math
from collections import Counter
from src.config import PROFILES, IDEAL_LENGTH


# Cache repeated tournament evaluations; the inspiring set has 1,742 recipes.
_source_context = None
_source_sets = []
_novelty_cache = {}
_fitness_context = (None, None)
_fitness_cache = {}


def structural_score(recipe, ingredient_db):
    """Fraction of ingredients in the largest connected component."""
    if not recipe:
        return 0.0
    remaining = set(recipe)
    largest = 0
    while remaining:
        pending = [min(remaining)]
        remaining.remove(pending[0])
        size = 0
        while pending:
            name = pending.pop()
            size += 1
            adjacent = remaining.intersection(ingredient_db[name]["neighbors"])
            remaining.difference_update(adjacent)
            pending.extend(sorted(adjacent))
        largest = max(largest, size)
    return largest / len(recipe)


def compatibility_score(recipe, ingredient_db):
    if len(recipe) < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for i, a in enumerate(recipe):
        for b in recipe[i + 1:]:
            total += ingredient_db[a]["affinities"].get(b, 0.0)
            pairs += 1
    return total / pairs


def diversity_score(recipe, ingredient_db):
    """Normalized entropy of the ingredients' Leiden communities."""
    if len(recipe) < 2:
        return 0.0
    counts = Counter(ingredient_db[name]["community"] for name in recipe)
    possible = min(len(recipe), len({info["community"] for info in ingredient_db.values()}))
    if possible < 2:
        return 0.0
    entropy = -sum((n / len(recipe)) * math.log(n / len(recipe)) for n in counts.values())
    return entropy / math.log(possible)


def jaccard_similarity(a, b):
    a, b = set(a), set(b)
    union = a | b
    return 0.0 if not union else len(a & b) / len(union)


def novelty_score(recipe, inspiring_set):
    # Same nearest-source Jaccard novelty as the original; cache source sets.
    global _source_context, _source_sets, _novelty_cache
    if _source_context is not inspiring_set:
        _source_context = inspiring_set
        _source_sets = [set(source["ingredients"]) for source in inspiring_set]
        _novelty_cache = {}
    key = frozenset(recipe)
    if key not in _novelty_cache:
        similarity = max((len(key & source) / len(key | source) if key | source else 0.0)
                         for source in _source_sets)
        _novelty_cache[key] = 1.0 - similarity
    return _novelty_cache[key]


def length_score(recipe):
    lo, hi = IDEAL_LENGTH
    n = len(recipe)
    if lo <= n <= hi:
        return 1.0
    distance = lo - n if n < lo else n - hi
    return max(0.0, 1.0 - 0.25 * distance)


def quantity_support_score(recipe, ingredient_db):
    if not recipe:
        return 0.0
    total = 0.0
    for name in recipe:
        info = ingredient_db[name]
        if info["relative_quantities"]:
            total += 1.0
        elif info["known_mass_fractions"]:
            total += 0.5
    return total / len(recipe)


def support_penalty(recipe, ingredient_db):
    # Mean inverse node frequency: discourage reliance on one-off observations.
    if not recipe:
        return 1.0
    return sum(1.0 / ingredient_db[name]["recipe_count"] for name in recipe) / len(recipe)


def fitness_breakdown(recipe, ingredient_db, inspiring_set, profile="balanced"):
    w = PROFILES[profile]
    parts = {
        "structure": structural_score(recipe, ingredient_db),
        "compatibility": compatibility_score(recipe, ingredient_db),
        "novelty": novelty_score(recipe, inspiring_set),
        "diversity": diversity_score(recipe, ingredient_db),
        "length": length_score(recipe),
        "quantity_support": quantity_support_score(recipe, ingredient_db),
        "penalty": support_penalty(recipe, ingredient_db),
    }
    positive = sum(
        parts[k] * w[k]
        for k in (
            "structure", "compatibility", "novelty", "diversity", "length", "quantity_support",
        )
    )
    score = positive - w["penalty"] * parts["penalty"]
    parts["total"] = max(0.0, min(1.0, score))
    return parts


def calculate_fitness(recipe, ingredient_db, inspiring_set, profile="balanced"):
    global _fitness_context, _fitness_cache
    if _fitness_context[0] is not ingredient_db or _fitness_context[1] is not inspiring_set:
        _fitness_context = (ingredient_db, inspiring_set)
        _fitness_cache = {}
    key = (profile, tuple(sorted(recipe)))
    if key not in _fitness_cache:
        _fitness_cache[key] = fitness_breakdown(recipe, ingredient_db, inspiring_set, profile)["total"]
    return _fitness_cache[key]
