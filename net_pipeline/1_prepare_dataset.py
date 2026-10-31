"""Download and clean Italian dessert recipe data."""

import ast
import csv
import json
import re
import math
import unicodedata
from pathlib import Path
from urllib.request import urlopen


# File locations
ROOT = Path(__file__).resolve().parent.parent

DATASET_URL = (
    "https://huggingface.co/datasets/KanuSaru/italian-recipes/"
    "resolve/main/italian_recipes.csv"
)

# Conversion values for fractions
FRACTIONS = {
    "¼": 0.25,
    "½": 0.5,
    "¾": 0.75,
    "⅓": 1 / 3,
    "⅔": 2 / 3
}


def normalize_name(name):
    """Make ingredient names consistent."""

    name = unicodedata.normalize("NFC", name)
    name = name.replace("’", "'")
    name = " ".join(name.split())
    name = name.lower()

    return name


def load_unit_weights(file_path):
    """Read ingredient weights from a CSV file."""

    weights = {}

    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            name = normalize_name(row["ingredient"])
            grams = float(row["grams_per_unit"])
            max_count = float(row["max_count"])

            # Check that the values are valid
            if name in weights:
                raise ValueError("Duplicate ingredient: " + name)

            if not math.isfinite(grams) or grams <= 0:
                raise ValueError("Invalid weight: " + name)

            if not math.isfinite(max_count) or max_count <= 0:
                raise ValueError("Invalid maximum count: " + name)

            weights[name] = (grams, max_count)

    return weights


def parse_mass(name, quantity, unit_weights):
    """Convert an ingredient quantity into grams."""

    quantity = quantity.strip().lower()

    # Ignore quantities such as "q.b." (quanto basta)
    cleaned_quantity = quantity.replace(".", "").replace(" ", "")

    if cleaned_quantity == "qb":
        return None, "ignored"

    # Look for quantities such as 200g, 1kg or 500ml
    pattern = r"(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)"
    match = re.fullmatch(pattern, quantity)

    if match:
        amount = float(match.group(1).replace(",", "."))
        unit = match.group(2)

        if unit == "kg":
            grams = amount * 1000
            source = "mass"

        elif unit == "l":
            grams = amount * 1000
            source = "volume"

        elif unit == "ml":
            grams = amount
            source = "volume"

        else:
            grams = amount
            source = "mass"

        if grams > 0 and math.isfinite(grams):
            return grams, source

    # Check whether the quantity is a fraction
    count = None

    if quantity in FRACTIONS:
        count = FRACTIONS[quantity]

    # Otherwise, check whether it is a number
    elif re.fullmatch(r"\d+(?:[.,]\d+)?", quantity):
        count = float(quantity.replace(",", "."))

    # Convert ingredient counts using the weight table
    if count is not None:
        if name in unit_weights:
            grams_per_unit, max_count = unit_weights[name]

            if count > 0 and count <= max_count:
                total_grams = count * grams_per_unit
                return total_grams, "count_estimate"

    # The quantity could not be converted
    return None, "unresolved"


def download_dataset(file_path):
    """Download the dataset if it does not already exist."""

    if file_path.exists():
        return

    # Create the data folder if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = file_path.with_suffix(".csv.download")

    print("Downloading recipe dataset...")

    with urlopen(DATASET_URL, timeout=60) as response:
        with open(temporary_path, "wb") as file:

            while True:
                chunk = response.read(1024 * 1024)

                if not chunk:
                    break

                file.write(chunk)

    # Rename the file after downloading
    temporary_path.replace(file_path)

    print("Download completed!")


def load_recipes(file_path, unit_weights):
    """Read Dolci recipes and convert their ingredient quantities."""

    recipes = []

    with open(file_path, "r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for index, row in enumerate(reader):

            # Keep only desserts, including sweet biscuits and cookies.
            if row["Categoria"].strip().casefold() != "dolci":
                continue

            # Convert the ingredient text into a Python list
            try:
                ingredient_list = ast.literal_eval(row["Ingredienti"])

            except (ValueError, SyntaxError):
                raise ValueError(
                    "Invalid ingredients in recipe: " + row["Nome"]
                )

            if not isinstance(ingredient_list, list):
                raise ValueError("Ingredients must be a list")

            ingredients = {}
            mass_complete = len(ingredient_list) > 0

            # Process every ingredient in the recipe
            for entry in ingredient_list:

                if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                    raise ValueError("Invalid ingredient entry")

                label, quantity = entry

                if not isinstance(label, str) or not label.strip():
                    raise ValueError("Invalid ingredient name")

                if not isinstance(quantity, str):
                    raise ValueError("Invalid ingredient quantity")

                name = normalize_name(label)

                # Create a new ingredient if it has not appeared before
                if name not in ingredients:
                    ingredients[name] = {
                        "label": " ".join(label.split()),
                        "quantities": [],
                        "mass_g": 0.0,
                        "sources": []
                    }

                # Convert the ingredient quantity
                grams, source = parse_mass(
                    name, quantity, unit_weights
                )

                ingredient = ingredients[name]

                ingredient["quantities"].append(quantity)
                ingredient["sources"].append(source)

                # Add the converted mass if it is known
                if grams is not None:
                    ingredient["mass_g"] += grams

                if source == "unresolved":
                    mass_complete = False

            # Calculate the total known mass
            total_mass = 0.0

            for ingredient in ingredients.values():
                total_mass += ingredient["mass_g"]

            # Store the cleaned recipe
            recipe = {
                "name": "recipe_" + str(index),
                "label": row["Nome"],
                "category": row["Categoria"],
                "url": row["Link"],
                "servings": row["Persone/Pezzi"],
                "ingredients": ingredients,
                "known_mass_g": total_mass,
                "mass_complete": mass_complete
            }

            recipes.append(recipe)

    return recipes


def main():
    """Run the complete data preparation process."""

    # Step 1: Set the file paths
    dataset_path = ROOT / "data" / "italian_recipes.csv"
    weights_path = Path(__file__).resolve().parent / "unit_weights.csv"
    output_path = ROOT / "data" / "recipes.json"

    # Step 2: Download the dataset
    download_dataset(dataset_path)

    # Step 3: Load the ingredient weight conversions
    unit_weights = load_unit_weights(weights_path)

    # Step 4: Clean and process the recipes
    recipes = load_recipes(dataset_path, unit_weights)

    # Step 5: Save the cleaned data as JSON
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(recipes, file, ensure_ascii=False)

    print("Saved data/recipes.json")


if __name__ == "__main__":
    main()
