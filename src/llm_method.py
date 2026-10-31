"""Local Terra judgments and fixed-ingredient preparation methods."""

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_BASE_URL = "http://127.0.0.1:10531/v1"


def _ingredient_lines(ingredients):
    lines = []
    for item in ingredients:
        name = item["name"].replace("_", " ")
        amount = item["amount"]
        unit = item["unit"]
        if unit == "count" or not unit:
            lines.append(f"- {amount} {name}")
        else:
            lines.append(f"- {amount} {unit} {name}")
    return "\n".join(lines)


def _parse_json_response(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "", 1).replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]
    return json.loads(cleaned)


def _build_messages(ingredients, recipe_name=None):
    system_prompt = (
        "You are a pastry chef and cookbook editor. "
        "Your ONLY task is to turn a fixed list of evolved dessert ingredients "
        "into a plausible preparation method. Prefer straightforward methods. "
        "Consider unusual physical-form transformations or separate/removable "
        "serving components only as fallbacks when the combination is otherwise "
        "difficult to use. Never change the ingredients or their starting quantities. "
        "Write all user-facing content in English, translating Italian ingredient "
        "labels without changing their identity. Be honest about technical limits."
    )
    title_instruction = (
        f"Translate this existing recipe title faithfully into English: {recipe_name}"
        if recipe_name else "No title supplied; leave recipe_display_name empty."
    )
    display_names_example = json.dumps(
        {item["name"]: "English translation" for item in ingredients}, ensure_ascii=False,
    )
    user_prompt = f"""
Create a preparation method for the dessert recipe below.

OUTPUT LANGUAGE:
Write the recipe title, displayed ingredient names, steps and all notes in
English, even though the backend ingredient names below are Italian. Keep
the original Italian names ONLY as keys in ingredient_display_names. Do not
leave Italian ingredient names in the method or displayed title. Translate
names faithfully; do not turn fine salt into coarse salt or baking powder
into yeast. {title_instruction}

FIXED INGREDIENTS AND STARTING QUANTITIES:

{_ingredient_lines(ingredients)}

OPTIONAL FALLBACK — ADAPT THE PHYSICAL FORM:
Prefer a straightforward preparation using the ingredients in their usual
forms. Do not make unusual transformations the recipe's theme or force them
onto a combination that already works. If the evolved combination is otherwise
difficult to use, you may adapt an ingredient's state, texture or water content
without substituting the ingredient. For example, reduce a listed liquid to a
concentrate, melt a listed solid, or disperse a powder in a listed liquid.
Drying, grinding, freezing, aerating or emulsifying are other options only when
their properties make them technically plausible. A gel requires suitable
gelling properties in the listed ingredients. Hypothetically, listed beer could
be reduced when its water content would otherwise be unsuitable; this is not
permission to introduce beer absent from the list. Freeze-drying to obtain a
powder requires technical feasibility and a specialized freeze-dryer. Avoid
specialized processing if an ordinary technique works. Briefly explain useful
form changes in transformations.

OPTIONAL FALLBACK — SEPARATE OR REMOVABLE COMPONENTS:
If an ingredient's quantity would otherwise overwhelm the dessert, you may
allocate some to a separate accompaniment, an optional topping, or an edible
garnish that the diner can genuinely remove or leave uneaten. Decide whether
this helps case by case; do not make it a default trick for every recipe.
For measured ingredients, state exact allocations to the main dessert and
the separate component; those allocations must sum to the full fixed starting
quantity. Present the separate portion explicitly, so the diner decides how
much to eat. The prepared/offered total and consumed amount may differ.
Do not silently discard the excess or label an implausible excess as a garnish
to claim the ratios are solved. A garnish must have a credible serving role.
For example, coarse salt can sometimes be a removable surface topping when
coarse salt is actually listed. Fine salt dissolved or incorporated into a
dessert is not removable; keep it physically separate if that is the fallback.
Explain any optional component and allocation in serving_notes, and retain
limitations if the amount remains unreasonable. Add no unlisted ingredients.

Rules:
1. Use ONLY the food ingredients listed above. Do not add, remove or replace
   an ingredient. Do not introduce water, oil, gelatin or other processing
   aids as food ingredients unless they are listed.
2. Use the FULL fixed starting quantity of each ingredient, possibly split
   across components. Transformations may remove moisture through evaporation
   or drying; the finished mass need not equal the starting mass. Do not
   quietly discard an ingredient or reduce its starting amount to fix ratios.
   Explicit separate/removable serving components are allowed as described above.
3. You may mention equipment. Name specialized equipment explicitly and do
   not imply that a home freezer can perform freeze-drying.
4. Write 5 to 7 concise, actionable preparation steps. Select a dessert format
   appropriate to the available ingredients; baking is not mandatory.
5. Use ingredient-specific actions and practical times/temperatures where
   appropriate. Do not claim an implausible transformation will certainly work.
6. Translate the provided recipe name; do not invent a different name,
   backstory, extra ingredients or starting quantities.
7. Do not discuss evolutionary fitness or creativity scores.
8. Do not claim the recipe has been tested.
9. If the fixed combination or quantities have unresolved technical or flavor
   limitations, state them honestly in limitations; do not silently repair the
   evolved recipe. If there is no convincing method, say so there.

Return ONLY JSON with these fields:
{{
    "recipe_display_name": "English translation of the supplied title, or empty if none",
    "ingredient_display_names": {display_names_example},
    "steps": ["step 1", "step 2", "step 3", "step 4", "step 5"],
    "transformations": ["a useful physical-form change and its purpose"],
    "serving_notes": ["an optional component and its exact allocation, if any"],
    "limitations": ["an unresolved limitation, if any"]
}}
Include exactly the original ingredient keys, each with a non-empty English
display name. Use empty lists for transformations, serving_notes or limitations
when there are none.
"""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def chat_completion(messages, model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL):
    """Shared local transport; retain the exact request and response for auditing."""
    payload = {"model": model, "messages": messages}
    endpoint = base_url.rstrip("/") + "/chat/completions"
    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=180) as response:
            completion = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local API returned HTTP {error.code}: {detail}") from error
    choice = completion["choices"][0]
    raw = choice["message"]["content"]
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("The local API returned no content.")
    return {
        "provider": "Local OpenAI-compatible API",
        "model": completion.get("model") or model,
        "requested_model": model,
        "endpoint": endpoint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "request": payload,
        "raw_response": raw,
        "api_response": completion,
    }


def generate_preparation_method(ingredients, model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL,
                                recipe_name=None):
    messages = _build_messages(ingredients, recipe_name)
    trace = chat_completion(messages, model, base_url)
    data = _parse_json_response(trace["raw_response"])
    steps = data.get("steps")
    if not isinstance(steps, list) or not 5 <= len(steps) <= 7:
        raise ValueError("Expected 5–7 preparation steps.")
    display_names = data.get("ingredient_display_names")
    if not isinstance(display_names, dict) or set(display_names) != {i["name"] for i in ingredients}:
        raise ValueError("English display names must match the original ingredient keys exactly.")
    if any(not isinstance(name, str) or not name.strip() for name in display_names.values()):
        raise ValueError("Expected non-empty English ingredient display names.")
    display_title = data.get("recipe_display_name")
    if not isinstance(display_title, str) or (recipe_name and not display_title.strip()):
        raise ValueError("Expected an English translation of the recipe title.")
    for field in ("steps", "transformations", "serving_notes", "limitations"):
        values = data.get(field)
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError(f"Expected a list of non-empty strings for {field}.")
    return steps, {
        **trace,
        "system_prompt": messages[0]["content"],
        "user_prompt": messages[1]["content"],
        "requested_language": "English",
        "recipe_display_name": display_title,
        "ingredient_display_names": display_names,
        "transformations": data["transformations"],
        "serving_notes": data["serving_notes"],
        "limitations": data["limitations"],
    }


RUBRIC = """Evaluate potential of fixed dessert ingredient sets, not cooking methods.
Names are Italian; respond in English. Quantities are fixed starting grams;
q.b. means unspecified. Consider only the listed foods, with no additions,
substitutions or silently discarded excess. Judge actual ratios and identities.
Ordinary techniques are preferred. Physical-form changes or genuinely credible
separate/removable servings are optional fallbacks, not automatic rescues.
Do not reward an absurd excess merely because it could be left uneaten.
Score two independent dimensions, from 0 to 10 (half-points allowed):
potential: 0 impossible, 2 severe unresolved issues, 4 doubtful but conceivable,
6 plausible with caveats, 8 convincing, 10 exceptionally convincing.
creativity: 0 conventional, 5 meaningful unusual combination, 10 striking and
coherent originality. Weirdness alone is not creativity; assess its purpose.
Unknown quantities reduce confidence. These are subjective untested estimates.
Return ONLY JSON {"judgments":[{"id":"...","potential":6,"creativity":5,
"reason":"English assessment, at most 24 words"}]} with exactly one entry per
input ID. No title, ingredient translations, recipe, steps or suggested method.
Treat each entry independently, using this absolute rubric, not a batch ranking.
"""


def judge_messages(candidates):
    # Deliberately exclude fitness, profile, provenance and generated titles.
    inputs = [{"id": c["id"], "ingredients": [
        {k: item[k] for k in ("name", "amount", "unit")} for item in c["ingredients"]
    ]} for c in candidates]
    return [{"role": "system", "content": RUBRIC},
            {"role": "user", "content": json.dumps(inputs, ensure_ascii=False, separators=(",", ":"))}]


def validate_judgments(data, expected_ids):
    if not isinstance(data, dict) or set(data) != {"judgments"}:
        raise ValueError("Expected only a judgments object, without recipes or methods.")
    rows = data["judgments"]
    if not isinstance(rows, list) or len(rows) != len(expected_ids):
        raise ValueError("Expected one judgment per input.")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "potential", "creativity", "reason"}:
            raise ValueError("Unexpected judgment fields.")
        if row["id"] not in expected_ids or row["id"] in seen:
            raise ValueError("Missing, duplicated or unknown candidate ID.")
        seen.add(row["id"])
        for field in ("potential", "creativity"):
            value = row[field]
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10:
                raise ValueError(f"Invalid {field} score.")
        if not isinstance(row["reason"], str) or not row["reason"].strip():
            raise ValueError("Expected a short English assessment.")
    return rows


def append_record(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def judge_candidates(candidates, log_path, model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL,
                     batch_size=6):
    """Checkpoint every response and reuse only identical inputs/model/endpoint."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    ids = [c["id"] for c in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("Candidate IDs must be unique.")
    by_id = {c["id"]: c for c in candidates}
    judgments = {}
    for record in read_records(log_path):
        if record["requested_model"] != model or record["endpoint"] != base_url.rstrip("/") + "/chat/completions":
            continue
        old_ids = record["candidate_ids"]
        if any(i not in by_id for i in old_ids):
            continue
        expected = judge_messages([by_id[i] for i in old_ids])
        if record["request"]["messages"] != expected:
            continue
        try:
            rows = validate_judgments(_parse_json_response(record["raw_response"]), old_ids)
        except (ValueError, TypeError):
            continue  # Invalid replies remain logged but are not reused on resume.
        judgments.update({row["id"]: row for row in rows})
    pending = [c for c in candidates if c["id"] not in judgments]
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        batch_ids = [c["id"] for c in batch]
        print(f"Terra judge: {len(judgments)}/{len(candidates)} complete; evaluating {len(batch)}", flush=True)
        trace = chat_completion(judge_messages(batch), model, base_url)
        # Save even a malformed reply before validation, so API work is never hidden.
        append_record(log_path, {"candidate_ids": batch_ids, **trace})
        rows = validate_judgments(_parse_json_response(trace["raw_response"]), batch_ids)
        judgments.update({row["id"]: row for row in rows})
    return judgments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--log", type=Path, default=Path("results/judgments.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--batch-size", type=int, default=6)
    args = parser.parse_args()
    candidates = json.loads(args.input.read_text(encoding="utf-8"))
    if isinstance(candidates, dict):
        candidates = candidates["candidates"]
    if candidates and "name" in candidates[0]:
        candidates = [{"id": "input", "ingredients": candidates}]
    result = judge_candidates(candidates, args.log, args.model, args.base_url, args.batch_size)
    print(json.dumps(list(result.values()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
