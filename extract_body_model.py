import json

# Load the input JSON
with open("bodymodel_components_20250609160803.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Use a set to track seen names (deduplicates automatically)
seen = set()
inventory = []

for item in data:
    name = item.get("body_model_name", "").strip()
    if name and name not in seen:
        seen.add(name)
        inventory.append({"body_model_name": name})

# Write the unique body model names to a new JSON file
with open("body_models.json", "w", encoding="utf-8") as f:
    json.dump(inventory, f, indent=2)

print(f"Extracted {len(inventory)} unique body model names to inventory_body_models.json")
