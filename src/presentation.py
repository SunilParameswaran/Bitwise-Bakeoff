import hashlib  # noqa: I001
import random


def _stable_rng(recipe, seed=0):
    key = "|".join(sorted(recipe)) + f"|{seed}"
    value = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
    return random.Random(value)



def quantify_recipe(recipe, ingredient_db, seed=0, total_mass=500.0):
    """Sample node distributions, then normalize known quantities to a batch."""
    if total_mass <= 0:
        raise ValueError("total_mass must be positive")
    rng = _stable_rng(recipe, seed)
    samples = {}
    for name in sorted(recipe):
        info = ingredient_db[name]
        source = "relative_quantities"
        distribution = info[source]
        if not distribution:
            source = "known_mass_fractions"
            distribution = info[source]
        if distribution:
            samples[name] = (rng.choice(distribution), source)
    total = sum(fraction for fraction, _ in samples.values())
    detailed = []
    for name in recipe:
        if name in samples:
            fraction, source = samples[name]
            detailed.append({
                "name": name, "amount": max(0.1, round(total_mass * fraction / total, 1)), "unit": "g",
                "sampled_fraction": fraction, "quantity_source": source,
            })
        else:
            detailed.append({"name": name, "amount": "q.b.", "unit": "",
                             "quantity_source": "unquantified"})
    # Absorb rounding error into the largest measured amount.
    weighed = [item for item in detailed if item["unit"] == "g"]
    if weighed:
        largest = max(weighed, key=lambda item: item["amount"])
        largest["amount"] = round(largest["amount"] + total_mass - sum(item["amount"] for item in weighed), 1)
    return detailed


def generate_name(recipe, ingredient_db):
    # Stable labels from the data; avoid forcing every dessert to be a cookie.
    chosen = sorted(recipe, key=lambda n: (ingredient_db[n]["recipe_count"], n))[:3]
    return "Dolce con " + ", ".join(ingredient_db[n]["label"] for n in chosen)


def fmt_ing(item, display_names):
    name = display_names[item["name"]]
    amount, unit = item["amount"], item["unit"]
    if amount == "q.b.":
        return f"- {name} (quantity unspecified)"
    if unit == "count" or not unit:
        return f"- {amount} {name}"
    return f"- {amount} {unit} {name}"
