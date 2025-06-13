import json
import re

# Keywords for matching distributor names (case-insensitive, partial match)
distributor_keywords = {"marathon", "scelzi", "monroe", "reading", "knapheide", "pjs", "forest"}

# Normalize string: lowercase, remove apostrophes and extra whitespace
def normalize(text):
    return re.sub(r"[’']", "", text.lower()).strip()

# Load JSON data
with open('onlot_with_invoices_20250516220118.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

base_url = "https://images.worktrucksolutions.com/"
output_file = 'extracted_urls.txt'
urls = []

for obj in data:
    match_found = False

    # Check body_manufacturer
    body_mfr = normalize(obj.get("body_manufacturer", ""))
    if any(keyword in body_mfr for keyword in distributor_keywords):
        match_found = True

    # If not found, check all component attribute values
    if not match_found:
        for comp in obj.get("components", []):
            for attr in comp.get("attributes", []):
                val = normalize(attr.get("value", ""))
                if any(keyword in val for keyword in distributor_keywords):
                    match_found = True
                    break
            if match_found:
                break

    # Extract document paths if matched
    if match_found:
        for doc in obj.get("documents", []):
            path = doc.get("path")
            if path:
                urls.append(base_url + path)

# Write URLs to file
with open(output_file, 'w') as f:
    for url in urls:
        f.write(f"{url}\n")

print(f"Extracted {len(urls)} URLs to {output_file}")
