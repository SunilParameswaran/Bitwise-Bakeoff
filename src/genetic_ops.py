import random
from src.config import IDEAL_LENGTH, MIN_LENGTH, MAX_LENGTH


def _category_map(recipe, ingredient_db):
    # Keep the original grouping helper, grouping by learned community.
    out = {}
    for name in recipe:
        out.setdefault(ingredient_db[name]["community"], []).append(name)
    return out


def _choose_candidate(candidates, context, ingredient_db):
    # Prefer candidates connected to the remaining ingredients.
    weights = [
        sum(ingredient_db[name]["affinities"].get(other, 0.0) for other in context)
        for name in candidates
    ]
    if not any(weights):
        return random.choice(candidates)
    return random.choices(candidates, weights=[w + 1e-6 for w in weights], k=1)[0]


def repair(recipe, ingredient_db):
    # De-duplicate while keeping order, as in the original implementation.
    child = list(dict.fromkeys(recipe))
    while len(child) > MAX_LENGTH:
        child.pop(random.randrange(len(child)))
    while len(child) < MIN_LENGTH:
        options = [name for name in ingredient_db if name not in child]
        if not options:
            break
        child.append(_choose_candidate(options, child, ingredient_db))
    return child


def crossover(parent1, parent2, ingredient_db):
    """Inherit shared communities, then mix the parents' remaining genes."""
    p1 = _category_map(parent1, ingredient_db)
    p2 = _category_map(parent2, ingredient_db)
    child = []
    for community in sorted(p1.keys() & p2.keys()):
        child.append(random.choice(p1[community] + p2[community]))
    optional_pool = [n for n in dict.fromkeys(parent1 + parent2) if n not in child]
    random.shuffle(optional_pool)
    target = random.randint(*IDEAL_LENGTH)
    child.extend(optional_pool[:max(0, target - len(child))])
    return repair(child, ingredient_db)


def mutation(recipe, ingredient_db, mutation_rate=0.45, creative_rate=0.12):
    child = recipe.copy()
    if random.random() > mutation_rate:
        return child
    op = random.choices(["replace", "add", "remove"], weights=[0.60, 0.25, 0.15], k=1)[0]

    if op in {"replace", "add"} and child:
        if op == "add" and len(child) >= MAX_LENGTH:
            return child
        idx = random.randrange(len(child))
        old = child[idx]
        community = ingredient_db[old]["community"]
        cross_community = random.random() < creative_rate
        candidates = [
            name for name, info in ingredient_db.items()
            if name not in child and (info["community"] != community) == cross_community
        ]
        context = child[:idx] + child[idx + 1:] if op == "replace" else child
        if candidates:
            chosen = _choose_candidate(candidates, context, ingredient_db)
            if op == "replace":
                child[idx] = chosen
            else:
                child.append(chosen)
    elif op == "remove" and len(child) > MIN_LENGTH:
        child.pop(random.randrange(len(child)))
    return repair(child, ingredient_db)
