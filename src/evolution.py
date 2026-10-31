import random
from src.fitness import calculate_fitness
from src.genetic_ops import crossover, mutation, repair


def recipe_key(recipe):
    return tuple(sorted(recipe))


def create_initial_population(recipes, ingredient_db, population_size=60, creative_rate=0.12):
    population = []
    # Sample real desserts across the inspiring set, rather than its first rows.
    for r in random.sample(recipes, k=min(population_size, len(recipes))):
        population.append(repair(r["ingredients"].copy(), ingredient_db))
        if len(population) >= population_size:
            return population
    # Fill with lightly mutated source variants.
    while len(population) < population_size:
        base = random.choice(recipes)["ingredients"].copy()
        population.append(mutation(repair(base, ingredient_db), ingredient_db,
                                   mutation_rate=1.0, creative_rate=creative_rate))
    return population


def select_parent(population, ingredient_db, inspiring_set, profile, tournament_size=3):
    candidates = random.sample(population, k=min(tournament_size, len(population)))
    return max(candidates, key=lambda r: calculate_fitness(r, ingredient_db, inspiring_set, profile))


def evolve(recipes, ingredient_db, profile="balanced", generations=100, population_size=60,
           elite_size=3, mutation_rate=0.45, patience=15, verbose=True, creative_rate=0.12):
    population = create_initial_population(recipes, ingredient_db, population_size, creative_rate)
    history = []
    best_seen = -1.0
    stagnant = 0

    for generation in range(generations):
        scored = sorted(
            [(r, calculate_fitness(r, ingredient_db, recipes, profile)) for r in population],
            key=lambda x: x[1], reverse=True,
        )
        best_recipe, best_score = scored[0]
        mean_score = sum(s for _, s in scored) / len(scored)
        unique = len({recipe_key(r) for r, _ in scored})
        history.append({"generation": generation, "best": best_score, "mean": mean_score, "unique": unique})

        if verbose:
            print(f"Gen {generation:03d} | best={best_score:.3f} | mean={mean_score:.3f} | unique={unique:02d} | {best_recipe}")

        if best_score > best_seen + 1e-8:
            best_seen = best_score
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= patience:
            if verbose:
                print(f"Early stop: no best-fitness improvement for {patience} generations.")
            break
        if generation == generations - 1:
            break

        new_population = [r.copy() for r, _ in scored[:elite_size]]
        seen = {recipe_key(r) for r in new_population}
        attempts = 0
        while len(new_population) < population_size:
            p1 = select_parent(population, ingredient_db, recipes, profile)
            p2 = select_parent(population, ingredient_db, recipes, profile)
            child = crossover(p1, p2, ingredient_db)
            child = mutation(child, ingredient_db, mutation_rate=mutation_rate,
                             creative_rate=creative_rate)
            key = recipe_key(child)
            # Prefer unique individuals, but don't deadlock late in convergence.
            if key not in seen or attempts > population_size * 4:
                new_population.append(child)
                seen.add(key)
            attempts += 1
        population = new_population

    final = sorted(
        [(r, calculate_fitness(r, ingredient_db, recipes, profile)) for r in population],
        key=lambda x: x[1], reverse=True,
    )
    return final, history
