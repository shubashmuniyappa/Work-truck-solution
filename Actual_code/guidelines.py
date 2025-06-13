guidelines = """
ENHANCED EXTRACTION GUIDELINES:

=== DATE FORMATTING ===
- Convert ALL dates to YYYY-MM-DD format:
  - "03/12/25" → "2025-03-12"
  - "March 12, 2025" → "2025-03-12"
  - "12-Mar-25" → "2025-03-12"
- For 2-digit years: 00-30 = 20xx, 31-99 = 19xx

=== FIELD EXTRACTION PRIORITIES ===

1. **Stock Number**: Look for variations:
   - "Stock Number", "Stock #", "Stock No.", "Item #", "Part #"
   - Extract exact alphanumeric value

2. **VIN**: 17-character vehicle identification number
   - Usually starts with numbers/letters like "1FD", "3C6", etc.

3. **Vehicle Information**:
   - Make: Ford, Chevrolet, Ram, etc.
   - Model: F-600, Transit 350, ProMaster, etc.
   - Year: 4-digit year (2024, 2025, etc.)

4. **Body Information**:
   - body_type: "Box Truck", "Service Utility Van", "Upfitted Cargo Van", "Dovetail Landscape"
   - body_manufacturer: "Marathon", "Knapheide", "Reading", "Wil-Ro"
   - body_model: Include dimensions like "16' IL x 96\" W x 96\"IH Composite Van Body"

5. **Component ID Extraction**:
   - Look for line item numbers, part numbers, or serial numbers
   - Use format like 3169660, 3169661, etc. if found in invoice
   - If not found, use sequential numbers starting from 1

=== COMPONENT MAPPING STRATEGY ===

Group invoice line items into logical components:

**Body Components**:
- "Body", "Van Body", "Truck Body" → "Body"
- Include: material, dimensions, wall specifications

**Floor Components**:
- "Floor", "Flooring", "Floor Assembly" → "Floor"
- Include: material, thickness, crossmembers

**Roof Components**:
- "Roof", "Roof Assembly", "Roof Bows" → "Roof"
- Include: material, construction details

**Door Components**:
- "Door", "Rear Door", "Roll-Up Door" → "Door"
- Include: type, dimensions, features

**Liftgate Components**:
- "Liftgate", "Lift Gate", "Tailgate Lift" → "Liftgate"
- Include: manufacturer, model, capacity, platform size

**Hardware/Accessories**:
- "E-Track", "Cargo Control" → "Cargo Control"
- "Step Bumper", "Bumper" → "Bumper"
- "Toolbox", "Storage" → "Toolbox"

=== ATTRIBUTE EXTRACTION ===

For each component, extract relevant attributes:
- **Dimensions**: Width, Height, Length, Depth, Thickness
- **Materials**: Aluminum, Steel, Composite, Hardwood
- **Specifications**: Model numbers, part numbers, descriptions
- **Features**: Special characteristics, options, accessories

=== CLEANING RULES ===

1. **Remove Labels**: Strip "Item:", "Part:", "Serial:", etc.
2. **Clean Values**: Remove extra whitespace, normalize formatting
3. **Standardize Units**: Keep units like ", \", ', etc. in values
4. **Empty Values**: Use empty string "" if value not found

=== REQUIRED OUTPUT STRUCTURE ===

MUST include "documents" array:
```json
"documents": [
  {
    "date": "YYYY-MM-DD",
    "type": "Invoice",
    "path": "img/invoices/bodyinvoices/-/filename.pdf"
  }
]
```

=== VALIDATION CHECKLIST ===

Before returning JSON, verify:
☐ All dates in YYYY-MM-DD format
☐ Component IDs extracted from invoice or sequential
☐ Components logically grouped (Body, Floor, Roof, etc.)
☐ Attributes properly structured with name/value pairs
☐ Documents array included
☐ No missing required fields
☐ Values cleaned of labels and formatting

=== EXAMPLE COMPONENT STRUCTURE ===
```json
{
  "id": 3169660,
  "name": "Body",
  "attributes": [
    { "name": "Material", "value": "Composite" },
    { "name": "Width", "value": "96\"" },
    { "name": "Inside Height", "value": "96\"" },
    { "name": "Inside Length", "value": "192\"" }
  ]
}
```

RETURN ONLY THE STRUCTURED JSON - NO EXPLANATIONS OR ADDITIONAL TEXT.
"""