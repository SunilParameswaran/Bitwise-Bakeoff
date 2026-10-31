# Results, interpretation, and evaluation scope

## Evidence available

This repository includes the team's original [four-page report](project-report.pdf), two [Markdown cookbooks](../cookbook/), and two presentation images. Report measurements describe the original experiment. The original `results/` logs and generated graphs were not provided in the source folder.

The referenced Computational Creativity conversation adds context about cookbook presentation and a later proposed human evaluation. It is not treated as evidence that an additional experiment was performed. The styled six-page cookbook PDFs mentioned there were not supplied, so this repository does not claim to include them.

## Historical network and evolutionary results

The report gives 1,742 Dolci recipes, 646 distinct normalized ingredients, 16,254 bipartite edges, and 13,873 projected edges. Name normalization standardizes case, whitespace, and apostrophes, but is not a complete synonym ontology.

The profile summaries from Table 2 are:

| Profile | Mean fitness | Novelty | Compatibility | Core coverage |
|---|---:|---:|---:|---:|
| Conservative | 0.752 | 0.39 | 0.48 | 85% |
| Balanced | 0.730 | 0.66 | 0.20 | 10% |
| Experimental | 0.769 | 0.84 | 0.03 | 0% |
| Source recipes | — | — | — | 75% |

“Core” is an analysis in the report, not a labeled ingredient taxonomy used by the algorithm. Fitness combines different weights across profiles, so a larger experimental score is not evidence of better desserts. The report says every candidate had structural score 1.0, making that term non-discriminating in that experiment.

The report also gives correlations on **only the ten selected finalists**: judge creativity versus graph novelty, Spearman rho 0.85; judged potential versus graph fitness, 0.25; potential versus novelty, -0.54. These are reported historical statistics, not independently recomputed here. Selection at potential ≥5, mixed profile scales, and the tiny sample limit interpretation.

## The two collections

Promising finalists: **C12, C08, E04, B16, C11**. Creative finalists: **E14, E09, B11, B05, B13**. These IDs and their scores are visible in the supplied cookbooks. Both contain five recipes, and the sets are disjoint.

The best potential score among the finalists is 8/10 (C12 and C08). The highest creativity score is 6/10 (E14). Those are LLM judgments, not measured sensory outcomes. The creative collection is not simply the five globally highest creativity scores: selection alternates collections and imposes disjointness and within-book diversity.

The LLM does not see explicit profile or fitness fields. Candidate IDs still use profile-derived prefixes (C/B/E), so this is field omission, not a formally blinded randomized study. The LLM is instructed to preserve starting ingredients and amounts; code validates structure and translation keys, but cannot guarantee semantic compliance inside free-text instructions.

## Why quantities matter

The pipeline converts mass directly, approximates 1 ml as 1 g, and uses a small count-to-gram table. Those are estimates, not ingredient-specific density measurements. Unspecified `q.b.` quantities do not contribute to the known mass.

Each ingredient's fraction is sampled independently, then known quantities are normalized to 500 g. This can destroy workable relationships among sugar, flour, eggs, liquids, and setting agents. A 500 g known-mass batch is not necessarily a 500 g final dish: unspecified quantities are additional, and processing changes water content.

The reports of missing binders, excessive liquid, or weak sweetness therefore reveal a real limitation of the representation. Graph compatibility is a co-occurrence association, not a chemistry or food-safety model. Recipes remain untested culinary proposals.

## Presentation and AI disclosure

The report attributes judging and English method writing to the historical server label `gpt-5.6-terra`, and the illustrations to `gpt-image-2`. These are recorded provenance labels rather than promises of model availability. Images were created separately from the Python pipeline.

The report explicitly observes that the artwork can add garnishes or imply textures not supported by the ingredients. The repository labels the images as illustrative and preserves the limitations alongside each recipe. Visual appeal is not evidence that a generated recipe works.

## Future human evaluation

The later conversation proposed a Lovelace 2.0-style constraint challenge. This remains **future work**, not an implemented benchmark or a completed result:

1. Ask for a dessert satisfying explicit constraints, such as chocolate and fruit.
2. Add constraints such as no eggs, an unusual pairing, or a plausible baked form.
3. Have a human judge check whether the artifact is valid and actually meets each constraint.
4. Have a human referee check that the challenge is reasonable, and record the point of failure.

This tests constraint satisfaction and artifact validity; tasting or aesthetic preference would be a separate evaluation. The current CLI does not accept arbitrary natural-language ingredient constraints. Implementing this study requires a constraint interface, recorded challenges, independent human judgments, and a defined failure criterion.

Other useful next steps include joint quantity sampling, comparisons against random/source-recipe baselines, repeated independent judges, and expert or practical cooking evaluation. No results from these follow-ups are claimed.

## Publication verification

On 31 October 2026, a fresh download and the complete no-LLM pipeline produced 33 communities and 60 distinct candidate ingredient sets across all 15 runs. Every candidate had 5–10 ingredients and 500 g of measured ingredients. Five offline unit tests passed. See [machine-readable verification](validation.json) for versions and the downloaded dataset hash.

One discrepancy was found: preprocessing retains 1,744 Dolci rows, two with no ingredients. The graph builder includes those two isolated recipe nodes, yielding **2,390 bipartite nodes**, whereas the submitted report says 2,388. Evolution filters empty recipes, leaving the reported **1,742-recipe inspiring set**. The 646 ingredient nodes, 16,254 bipartite edges, and 13,873 ingredient edges match the report. The historical report and algorithm are preserved rather than silently altered.

No LLM endpoint was called, no historical judge scores were revalidated, and no recipes were cooked.
