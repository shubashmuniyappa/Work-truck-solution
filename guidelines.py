# guidelines.py

guidelines = """
Guidelines for Extraction:
-Extract the stock number from the invoice by identifying labels like "Stock Number", "Stock #", or "Stock No." and provide its exact value as a string.
-For example: "Stock Number: ABC12345", "Stock #: 789XYZ", or "Stock No. 456DEF".
- Extract each field only if it is clearly present in the invoice text.
- For any missing fields:
  - Either omit the field entirely or
  - Include it with an empty string "" — both approaches are acceptable.
- The components list should contain only components explicitly mentioned in the invoice.
- Each component must include:
  - A unique "id" (start at 1 or use a serial/item number if available).
  - A descriptive "name" (e.g., "Body", "Floor", "Roof", "Liftgate").
  - An "attributes" list containing { "name": ..., "value": ... } pairs.
- If an attribute is present without a value, set the "value" to an empty string "".
- Clean all extracted values:
  - Remove labels, colons, units unless meaningful, and extra whitespace (e.g., strip "Item #", "Serial No:", etc.).
- Follow the exact JSON structure and field names shown in the Desired Output Format.
- Return only the structured JSON result — do not include explanations, notes, or additional text.

"""