# Setup and reproducibility

## Installation

Use Python 3.10 or newer. The publishing check uses Python 3.10.21 with the supplied `igraph==1.0.0` pin. All other runtime imports are from the Python standard library. No OpenAI SDK is required; the client uses `urllib.request`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell activation: `.venv\Scripts\Activate.ps1`.

## Pipeline stages

Run from the repository root, in this order:

| Command | Input | Output |
|---|---|---|
| `python net_pipeline/1_prepare_dataset.py` | Public source CSV; `unit_weights.csv` | `data/italian_recipes.csv`, `data/recipes.json` |
| `python net_pipeline/2_build_bipartite_graph.py` | Cleaned recipes | `output/recipe_ingredients/graph.pickle` |
| `python net_pipeline/3_project_ingredients.py` | Bipartite graph | `output/ingredients/graph.pickle` |
| `python net_pipeline/4_run_leiden.py` | Both graphs | Community labels; both graphs; Gephi `nodes.csv` / `edges.csv` |
| `python -m src.main --prepare-only` | Recipes and annotated ingredient graph | `results/candidates.json` |
| `python -m src.main --base-url URL --model MODEL_ID` | Candidate pool and external model endpoint | Judgments, selections, methods, rankings, cookbooks |

The data URL points to the dataset's `main` revision, not an immutable version. The first stage reuses an existing CSV; preserve its hash and a local copy when recording an experiment. Dataset updates, Python/igraph versions, graph order, or model changes may change results despite fixed seeds.

Community detection uses seed 42 and target community sizes 8–35. Disconnected or unsplittable groups may fall outside those targets; the script reports this rather than forcing unsupported merges.

The candidate pool stores settings, run histories, quantity seeds, and a graph SHA-256. Cached pools reject changes to graph hash or requested per-profile count. They do **not** automatically detect every source-code change; regenerate after changing search/fitness code.

## LLM endpoint requirements

The historical defaults in `src/llm_method.py` are a local server at `http://127.0.0.1:10531/v1` and the label `gpt-5.6-terra`. Neither a server nor access to this model is provided.

Supply your own endpoint and supported model name:

```bash
python -m src.main --base-url http://127.0.0.1:10531/v1 --model YOUR_SERVER_MODEL_ID
```

The client:

- POSTs `{ "model": "...", "messages": [...] }` to `BASE_URL/chat/completions`.
- Expects `choices[0].message.content` containing a JSON object as text.
- Has a 180-second HTTP timeout and sends no Authorization header.
- Does not set temperature or an API sampling seed; deterministic search does not imply deterministic model judgments.
- Validates judgment IDs/scores, recipe fields, ingredient translation keys, and 5–7 method steps. It does not semantically prove that every instruction preserves ingredients and quantities.

An authenticated remote service needs a compatible trusted proxy or a deliberate client change. There is no implemented `OPENAI_API_KEY` setting. Model output with invalid JSON/schema raises an error rather than silently accepting it. No paid model calls are part of the publication verification.

## Outputs and reruns

| Path | Contents |
|---|---|
| `results/candidates.json` | Fixed candidate pool, provenance, graph hash, evolutionary histories |
| `results/judgments.jsonl` | Completed judging requests/responses and validated scores |
| `results/selection.json` | Selected IDs, thresholds, and judgments |
| `results/rankings.csv` | Candidate scores and collection assignments |
| `results/methods.jsonl` | Generated methods, requests/responses, provenance |
| `results/usage.json` | Reported API usage totals; currency cost is unknown |
| `cookbook/promising.md`, `cookbook/creative.md` | Rendered English collections |

Matching completed API calls can be reused. A repeated run is not necessarily a new independent evaluation. Runtime traces may include endpoint details and complete model responses; they are ignored by Git.

The two tracked cookbook files are the supplied historical deliverables. Before regenerating, copy them elsewhere if you want to retain them. `--fresh` recursively deletes `results/` **and** `cookbook/` before any new work, even with `--prepare-only`. It is not necessary for an initial clone.

For Gephi, import `nodes.csv` as the node table and `edges.csv` as an undirected edge table for the chosen graph. Community labels are available for coloring. The graph layouts in the report were created in Gephi, not automatically by these scripts.

## Tests

```bash
python -m unittest discover -s tests -v
```

These offline checks cover mass normalization, novelty, judge-input separation, score validation, and finalist selection. They do not establish culinary feasibility or model quality.

## Troubleshooting

- **Missing `igraph`:** activate the environment and install `requirements.txt` using its Python.
- **Missing graph/recipes:** run all four numbered scripts in order.
- **Connection refused:** `--prepare-only` works without a server; judging requires your external endpoint.
- **HTTP 401/403:** the client sends no authentication. Configure your compatible endpoint appropriately.
- **Pool settings mismatch:** archive the old outputs, then explicitly regenerate. Read the `--fresh` deletion behavior first.
- **Fewer than five finalists:** the floor or diversity constraints left too few eligible candidates. The program intentionally does not relax the potential floor.
- **Malformed model response:** inspect the configured model/server; successful HTTP transport is not enough to satisfy the JSON contract.

The historical full candidate and API logs were not included in the supplied project folder. The cookbooks and report are preserved, while a new no-LLM run can reconstruct and inspect the candidate-generation stage. It cannot establish that model judgments match the historical ones.
