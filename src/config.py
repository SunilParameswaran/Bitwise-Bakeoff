PROFILES = {
    "conservative": {
        "structure": 0.38,
        "compatibility": 0.30,
        "novelty": 0.10,
        "diversity": 0.08,
        "length": 0.08,
        "quantity_support": 0.06,
        "penalty": 0.35,
    },
    "balanced": {
        "structure": 0.30,
        "compatibility": 0.25,
        "novelty": 0.20,
        "diversity": 0.10,
        "length": 0.08,
        "quantity_support": 0.07,
        "penalty": 0.30,
    },
    "experimental": {
        "structure": 0.24,
        "compatibility": 0.18,
        "novelty": 0.32,
        "diversity": 0.12,
        "length": 0.07,
        "quantity_support": 0.07,
        "penalty": 0.25,
    },
}

# Retain the original search-size constraints, but no mandatory cookie roles.
IDEAL_LENGTH = (6, 9)
MAX_LENGTH = 10
MIN_LENGTH = 5
