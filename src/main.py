"""Consolidated EA candidates -> short Terra judgments -> two English cookbooks."""
import argparse
import csv
import hashlib
import json
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.config import PROFILES
from src.evolution import evolve, recipe_key
from src.fitness import fitness_breakdown, jaccard_similarity
from src.knowledgebase import load_ingredients, load_recipes, validate_knowledgebase
from src.llm_method import (
    DEFAULT_BASE_URL, DEFAULT_MODEL, _build_messages, append_record,
    generate_preparation_method, judge_candidates, read_records,
)
from src.presentation import fmt_ing, generate_name, quantify_recipe


BASE_DIR = Path(__file__).resolve().parent.parent
SEEDS = [1, 7, 21, 42, 99]  # Reproducibility seeds retained from the team's original runner.


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_pool(per_profile=20):
    db, recipes = load_ingredients(), load_recipes()
    validate_knowledgebase(db, recipes)
    pools, runs = {}, []
    for profile in PROFILES:
        for seed in SEEDS:
            print(f"EA: {profile}, seed {seed}", flush=True)
            random.seed(seed)
            ranked, history = evolve(recipes, db, profile=profile, verbose=False)
            pools[profile, seed] = ranked
            runs.append({"profile": profile, "seed": seed, "history": history})

    selected = {profile: [] for profile in PROFILES}
    seen = set()
    # Round-robin across profiles and seeds rather than choosing a favourite seed.
    for index in range(per_profile):
        seed = SEEDS[index % len(SEEDS)]
        for profile in PROFILES:
            previous = [c["ingredient_names"] for c in selected[profile]]
            pick = None
            for limit in (0.75, 0.90, 1.01):
                for rank, (names, score) in enumerate(pools[profile, seed], 1):
                    if recipe_key(names) in seen:
                        continue
                    if all(jaccard_similarity(names, old) < limit for old in previous):
                        pick = names, score, rank, limit
                        break
                if pick:
                    break
            if pick is None:
                raise ValueError(f"Not enough distinct final individuals for {profile}, seed {seed}.")
            names, score, rank, limit = pick
            seen.add(recipe_key(names))
            quantity_seed = seed * 100 + index + 1
            candidate = {
                "id": profile[0].upper() + f"{index + 1:02d}", "profile": profile,
                "seed": seed, "source_population_rank": rank, "quantity_seed": quantity_seed,
                "pool_similarity_limit": limit,
                "name": generate_name(names, db), "ingredient_names": names,
                "ingredients": quantify_recipe(names, db, quantity_seed),
                "fitness": score, "fitness_breakdown": fitness_breakdown(names, db, recipes, profile),
            }
            selected[profile].append(candidate)
    # Interleave profiles before judging; the judge sees neither profile nor fitness.
    candidates = [selected[p][i] for i in range(per_profile) for p in PROFILES]
    graph_path = BASE_DIR / "output/ingredients/graph.pickle"
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "KanuSaru/italian-recipes, Dolci only", "inspiring_recipes": len(recipes),
        "network_ingredients": len(db),
        "network_communities": len({x["community"] for x in db.values()}),
        "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "seeds": SEEDS, "per_profile": per_profile, "fitness_profiles": PROFILES,
        "ea_settings": {"generations": 100, "population_size": 60, "patience": 15,
                        "elite_size": 3, "mutation_rate": 0.45, "creative_rate": 0.12},
        "quantity_settings": {"known_mass_grams": 500, "independent_marginal_samples": True,
                              "renormalized": True},
        "runs": runs, "candidates": candidates,
    }


def select_collections(candidates, judgments, count=5, potential_floor=5.0):
    """Select disjoint diverse books; never silently lower the plausibility floor."""
    eligible = [c for c in candidates if judgments[c["id"]]["potential"] >= potential_floor]
    promising = sorted(eligible, key=lambda c: (
        -judgments[c["id"]]["potential"], -judgments[c["id"]]["creativity"], c["id"]))
    creative = sorted(eligible, key=lambda c: (
        -judgments[c["id"]]["creativity"], -c["fitness_breakdown"]["novelty"],
        -judgments[c["id"]]["potential"], c["id"]))
    books = {"promising": [], "creative": []}
    used = set()
    # Alternate collections so the first one does not consume all shared leaders.
    for _ in range(count):
        for name, ranking in (("promising", promising), ("creative", creative)):
            for candidate in ranking:
                if candidate["id"] in used:
                    continue
                if any(jaccard_similarity(candidate["ingredient_names"], old["ingredient_names"]) >= 0.8
                       for old in books[name]):
                    continue
                books[name].append(candidate)
                used.add(candidate["id"])
                break
    return {name: [c["id"] for c in rows] for name, rows in books.items()}


def render_book(name, ids, by_id, judgments, methods, model):
    title = "Promising Desserts" if name == "promising" else "Creative Dessert Experiments"
    lines = [f"# {title}", "", (
        "Ingredient sets evolved from real Italian dessert recipes using the "
        "size-controlled Leiden ingredient network. Independent empirical quantity samples were normalized "
        "to a 500 g known-mass starting batch; unspecified quantities are additional. "
        f"{model} judged the fixed candidates, then wrote methods only for selected finalists. "
        "Judge scores are subjective estimates, separate from evolutionary fitness. "
        "These recipes have not been cooked or tasted. Optional transformations and "
        "separate serving components are fallbacks; all starting amounts remain fixed."
    ), ""]
    for candidate_id in ids:
        if candidate_id not in methods:
            continue
        candidate, method, judgment = by_id[candidate_id], methods[candidate_id], judgments[candidate_id]
        lines += [f"## {method['recipe_display_name']}", "",
                  f"Candidate {candidate_id} · {candidate['profile']} · "
                  f"Potential {judgment['potential']}/10 · Creativity {judgment['creativity']}/10 · "
                  f"Graph fitness {candidate['fitness']:.4f}", "", judgment["reason"], "",
                  "### Ingredients", ""]
        lines += [fmt_ing(i, method["ingredient_display_names"]) for i in candidate["ingredients"]]
        lines += ["", "### Method (AI-generated)", ""]
        lines += [f"{n}. {step}" for n, step in enumerate(method["generated_method"], 1)]
        for title, field in (("Physical-form changes", "transformations"),
                             ("Serving and optional components", "serving_notes"),
                             ("Limitations", "limitations")):
            if method[field]:
                lines += ["", f"### {title}", ""] + [f"- {v}" for v in method[field]]
        lines += ["", "---", ""]
    return "\n".join(lines)


def export_rankings(path, candidates, judgments, collections):
    fields = ["id", "profile", "seed", "potential", "creativity", "graph_fitness",
              "graph_novelty", "collection", "assessment"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for c in sorted(candidates, key=lambda c: (-judgments[c["id"]]["potential"], c["id"])):
            j = judgments[c["id"]]
            writer.writerow({"id": c["id"], "profile": c["profile"], "seed": c["seed"],
                             "potential": j["potential"], "creativity": j["creativity"],
                             "graph_fitness": round(c["fitness"], 5),
                             "graph_novelty": round(c["fitness_breakdown"]["novelty"], 5),
                             "collection": next((k for k, ids in collections.items() if c["id"] in ids), ""),
                             "assessment": j["reason"]})


def curate(args):
    results, cookbook = BASE_DIR / "results", BASE_DIR / "cookbook"
    if args.fresh:
        for directory in (results, cookbook):
            if directory.is_symlink():
                raise ValueError(f"Refusing to remove a symlink: {directory}")
            if directory.exists():
                print(f"Removing old generated files: {directory}", flush=True)
                shutil.rmtree(directory)
    results.mkdir(exist_ok=True)
    pool_path = results / "candidates.json"
    if not pool_path.exists():
        write_json(pool_path, prepare_pool(args.per_profile))
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    graph_hash = hashlib.sha256((BASE_DIR / "output/ingredients/graph.pickle").read_bytes()).hexdigest()
    if pool["graph_sha256"] != graph_hash or pool["per_profile"] != args.per_profile:
        raise ValueError("Saved pool uses different settings/graph; use --fresh to regenerate.")
    print(f"Pool ready: {len(pool['candidates'])} candidates, {pool['network_communities']} communities", flush=True)
    if args.prepare_only:
        return
    candidates = pool["candidates"]
    judgments = judge_candidates(candidates, results / "judgments.jsonl", args.model, args.base_url)
    collections = select_collections(candidates, judgments, args.finalists, args.potential_floor)
    selection = {"model": args.model, "potential_floor": args.potential_floor,
                 "requested_per_book": args.finalists, "max_jaccard_within_book": 0.8,
                 "collections": collections, "judgments": judgments}
    write_json(results / "selection.json", selection)
    export_rankings(results / "rankings.csv", candidates, judgments, collections)
    by_id = {c["id"]: c for c in candidates}
    methods = {}
    log_path = results / "methods.jsonl"
    for record in read_records(log_path):
        candidate = by_id.get(record["candidate_id"])
        if candidate and record["requested_model"] == args.model and record["endpoint"] == args.base_url.rstrip("/") + "/chat/completions":
            if record["request"]["messages"] == _build_messages(candidate["ingredients"], candidate["name"]):
                methods[candidate["id"]] = record
    cookbook.mkdir(exist_ok=True)
    for name, ids in collections.items():
        if len(ids) < args.finalists:
            print(f"{name}: only {len(ids)} finalists meet the floor and diversity constraints.", flush=True)
        for candidate_id in ids:
            if candidate_id not in methods:
                candidate = by_id[candidate_id]
                print(f"Terra method: {candidate_id} ({name})", flush=True)
                steps, trace = generate_preparation_method(candidate["ingredients"], model=args.model,
                                                            base_url=args.base_url, recipe_name=candidate["name"])
                record = {"candidate_id": candidate_id, "ingredients": candidate["ingredients"],
                          "generated_method": steps, **trace}
                append_record(log_path, record)
                methods[candidate_id] = record
            (cookbook / f"{name}.md").write_text(
                render_book(name, ids, by_id, judgments, methods, args.model), encoding="utf-8")
    records = read_records(results / "judgments.jsonl") + read_records(log_path)
    usage = {}
    for record in records:
        for key, value in (record["api_response"].get("usage") or {}).items():
            if type(value) in (int, float):
                usage[key] = usage.get(key, 0) + value
    write_json(results / "usage.json", {"model": args.model, "api_calls": len(records),
                                      "reported_usage": usage, "currency_cost": None})
    print(f"Saved two cookbooks; {len(records)} API calls in audit logs. Reported usage: {usage}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", action="store_true", help="Delete generated results/ and cookbook/ first")
    parser.add_argument("--prepare-only", action="store_true", help="EA candidates only, no API calls")
    parser.add_argument("--per-profile", type=int, default=20)
    parser.add_argument("--finalists", type=int, default=5)
    parser.add_argument("--potential-floor", type=float, default=5.0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    if args.per_profile < 1 or args.finalists < 1 or not 0 <= args.potential_floor <= 10:
        parser.error("Use positive counts and a potential floor between 0 and 10.")
    curate(args)


if __name__ == "__main__":
    main()
