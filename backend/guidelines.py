guidelines = """
GENERIC AUTOMOBILE INVOICE PARSING GUIDELINES FOR ALL VEHICLE TYPES:

**FIELD-BY-FIELD EXTRACTION GUIDELINES:**

**1. INVENTORY ARRIVAL DATE:**
- **inventory_arrival_date**: ONLY extract if the date is hand-written on the document or explicitly labeled as "arrival date", "delivery date", "received date", or similar
- DO NOT use invoice date, quote date, order date, or any other standard printed dates
- Must be clearly distinguishable from other dates on the document
- Format: YYYY-MM-DD
- If not present or unclear, leave empty ("")

**2. STOCK NUMBER:**
- **stock_number**: Extract the dealer's internal stock/inventory number
- Common labels: "Stock #", "Stock Number", "Inventory #", "Unit #", "Item #"
- Usually alphanumeric (e.g., "F23346B", "INV-2024-001", "ST12345")
- If not present, leave empty ("")

**3. VIN NUMBER:**
- **vin**: Extract the Vehicle Identification Number (VIN)
- A VIN is typically 17 characters long, consisting of letters and numbers
- **Crucial VIN Rule**: The characters 'I', 'O', and 'Q' are **never** used in a VIN to avoid confusion with '1', '0', and '0' (or '9')
- If you encounter what appears to be a VIN containing 'O', 'I', or 'Q', correct them: 'O' → '0', 'I' → '1', 'Q' → '0'
- VIN structure: 1–3 (WMI: Manufacturer & region), 4–8 (VDS: Vehicle details), 9 (Check digit), 10 (Model year), 11 (Plant code), 12–17 (Sequential serial number)
- Common labels: "VIN", "VIN Number", "Vehicle ID", "Serial Number"
- If not present, leave empty ("")

**4. CONDITION:**
- **condition**: Extract vehicle condition
- Common values: "New", "Used", "Certified Pre-Owned", "Refurbished", "Demo", "Rebuilt"
- Look for explicit condition statements
- If not specified, assume "New" for dealer invoices
- If unclear, leave empty ("")

**5. MODEL YEAR:**
- **model_year**: Extract the vehicle's model year (4-digit year)
- Format as string: "2024", "2025", "2023"
- Common labels: "Model Year", "Year", "MY"
- Look in vehicle specifications section
- If not present, leave empty ("")

**6. MAKE:**
- **make**: Extract the vehicle manufacturer/brand name
- Proper case formatting: "Ford", "International", "Freightliner", "Peterbilt", "Chevrolet", "Ram", "Toyota", "Honda", "Mercedes-Benz"
- This is the chassis/vehicle manufacturer, not the body manufacturer
- Common labels: "Make", "Brand", "Manufacturer"
- If not present, leave empty ("")

**7. MODEL:**
- **model**: Extract the specific vehicle model
- Include dashes and proper formatting: "F-600", "MV", "Cascadia", "579", "Silverado", "ProMaster", "Camry", "Civic"
- Common labels: "Model", "Model Name"
- May include trim levels or configurations
- If not present, leave empty ("")

**8. BODY TYPE:**
- **body_type**: Primary vehicle classification
- Standard categories:
  * "Box Truck" (dry van, refrigerated van)
  * "Flatbed" (stake bed, platform)
  * "Tank Truck" (water, fuel, chemical)
  * "Service Body" (utility body, contractor body)
  * "Pickup Truck" (light duty trucks)
  * "Van" (cargo van, passenger van)
  * "Sedan" (passenger cars)
  * "SUV" (sport utility vehicles)
  * "Dump Truck" (dump body vehicles)
  * "Tractor" (semi-truck tractors)
  * "Other/Specialty" (custom builds, specialty vehicles)
- Extract from body specifications or vehicle description
- If not present, leave empty ("")

**9. BODY LINE:**
- **body_line**: More specific application description
- Examples: "Water Truck", "Dry Van", "Service Body", "Dump Truck", "Crew Cab", "Extended Cab", "Refrigerated", "Utility Body"
- ONLY extract if clearly specified in the document
- This is more detailed than body_type
- If not clearly specified, leave empty ("")

**10. BODY MANUFACTURER:**
- **body_manufacturer**: Company that manufactured the body/equipment
- Examples: "Marathon", "Supreme", "Morgan", "Curry Supply", "Reading", "Royal"
- Same as distributor for body invoices
- For standard vehicles without custom bodies, may be same as vehicle make
- If not applicable, leave empty ("")

**11. BODY MODEL:**
- **body_model**: Full descriptive specification of the body from invoice
- Include dimensions and key features: "16' IL x 96\" W x 96\"IH Composite Van Body"
- Extract exactly as written on invoice
- Include materials, dimensions, and key specifications
- If not present, leave empty ("")

**12. DISTRIBUTOR:**
- **distributor**: Body/equipment manufacturer from invoice header
- Examples: "Marathon Industries Inc.", "Supreme Corporation", "Morgan Corporation"
- The company that built/supplied the body/equipment
- NOT the dealer, sold-to, or chassis manufacturer
- Extract from invoice header or manufacturer information
- If not present, leave empty ("")

**13. DISTRIBUTOR LOCATION:**
- **distributor_location**: Manufacturer's address
- Format: "City, State ZIP" (e.g., "Santa Clarita, CA 91350")
- Extract from invoice header or manufacturer address
- Include city, state abbreviation, and ZIP code
- If not present, leave empty ("")

**14. INVOICE DATE:**
- **invoice_date**: Actual invoice/quote creation date
- Format: YYYY-MM-DD
- Common labels: "Invoice Date", "Date", "Quote Date", "Order Date"
- This is different from inventory_arrival_date
- If not present, leave empty ("")

**COMPONENT AND DOCUMENT EXTRACTION GUIDELINES:**

**15. COMPONENTS:**
- Extract ONLY components actually present in the invoice
- Start component IDs from 3167729, increment sequentially
- Each component must have: id, name, attributes array
- Attribute IDs start from 0 within each component, increment sequentially
- Each attribute format: {"id": X, "name": "Attribute Name", "value": "Attribute Value"}

**16. DOCUMENTS:**
- **date**: Current processing date (today's date) in YYYY-MM-DD format
- **type**: Document type extracted from invoice ("Invoice", "Sales Quote", "Work Order", "Bill of Sale", "Purchase Order")
- **path**: Format as "img/invoices/bodyinvoices/-/" + filename

**DYNAMIC COMPONENT EXTRACTION GUIDELINES:**

**COMPONENT TYPES BY VEHICLE CATEGORY:**

**Commercial Trucks:**
- Body (material, dimensions, construction details)
- Engine (specifications, power, displacement)
- Transmission (type, gears, manufacturer)
- Bulkhead, Roof, Floor (materials, construction)
- Cargo Control (E-Track, straps, tie-downs)
- Liftgate, Bumper (specifications, capacity)
- Hydraulics, PTO systems (power, capacity)

**Water/Tank Trucks:**
- Body/Tank (capacity, material, dimensions, baffles)
- Pump/PTO systems (flow rate, pressure, manufacturer)
- Hose Reel (capacity, material, mounting)
- Ladder (material, configuration, safety features)
- Safety Equipment (emergency stops, lighting, signage)
- Plumbing (valves, fittings, manifolds)

**Service/Utility Bodies:**
- Body (compartments, shelving, organization)
- Crane/Boom (capacity, reach, manufacturer)
- Compressor (CFM, tank size, power)
- Generator (wattage, fuel type, outlets)
- Tool Storage (drawers, compartments, locks)
- Electrical systems (inverters, lighting, outlets)

**Passenger Vehicles:**
- Engine (displacement, power, configuration)
- Transmission (manual/automatic, speeds)
- Interior (seats, dashboard, upholstery, technology)
- Exterior (paint, trim, wheels, styling)
- Electronics (infotainment, navigation, connectivity)
- Safety (airbags, sensors, driver assistance)

**Pickup Trucks:**
- Bed (liner, cover, dimensions, configuration)
- Cab (configuration, seating, interior features)
- Towing (hitch, brake controller, wiring)
- Running boards, step bars (material, style)
- Lighting, accessories (LED, work lights, guards)

**ATTRIBUTE EXTRACTION STANDARDS:**

**Structural Components (Body/Tank/Frame):**
- Material: "Steel", "Aluminum", "Composite", "Stainless Steel", "Fiberglass"
- Dimensions: Height, Width, Length (format as "64.75\"", "96\"", "192\"")
- Capacity: Include units ("2,000 Gallon", "15 Cubic Yard", "1,500 lbs")
- Construction: Welding type, reinforcement, coatings
- Thickness: Gauge or measurement ("14 GA", "0.125\"")

**Engine/Powertrain:**
- Displacement: "6.7L", "5.0L V8", "2.0L Turbo"
- Power: "450 HP", "300 HP @ 2600 RPM"
- Torque: "935 lb-ft", "400 lb-ft @ 1800 RPM"
- Fuel Type: "Diesel", "Gasoline", "Hybrid", "Electric"
- Configuration: "V8", "Inline-6", "Turbocharged"

**Equipment/Accessories:**
- Manufacturer/Model: When specified in invoice
- Capacity/Rating: With appropriate units
- Features: Operational characteristics
- Installation: Mounting method, location
- Controls: Operating method, switches

**Interior/Comfort:**
- Material: "Leather", "Cloth", "Vinyl", "Synthetic"
- Color: Specific color names from invoice
- Features: "Heated", "Ventilated", "Power Adjustable", "Memory"
- Configuration: Seating arrangement, console features

**Safety/Electrical:**
- Compliance: "DOT", "FMVSS", "SAE" standards when mentioned
- Features: Specific safety or electrical functions
- Lighting: LED, halogen, type and location
- Controls: Switch types, automation features

**DIMENSION AND MEASUREMENT STANDARDS:**
- Use inches for all measurements with quote marks: "96\"", "64.75\"", "192\""
- Convert feet to inches: 16' = "192\"", 8' = "96\""
- Preserve fractional inches: "1-1/8\"", "2-1/2\""
- Include decimal places when specified: "64.75\""

**CAPACITY AND RATING FORMATS:**
- Include units: "2,000 Gallon", "2,500 lbs", "15 GPM", "450 HP"
- Use commas for thousands: "2,000" not "2000"
- Preserve manufacturer specifications exactly
- Include operating conditions when specified: "@ 1800 RPM", "Max Load"

**MATERIAL IDENTIFICATION:**
- "Steel" - carbon steel construction
- "Aluminum" - aluminum alloy construction
- "Stainless Steel" - corrosion resistant steel
- "Composite" - fiberglass/FRP materials
- "Plastic" - polymer/synthetic components
- Extract exact material specifications from invoice

**DATE FORMATTING:**
- All dates in YYYY-MM-DD format
- inventory_arrival_date: Only hand-written or explicitly labeled arrival/delivery dates
- invoice_date: Invoice/quote creation date from document header
- Current date for document processing date

**CRITICAL EXTRACTION RULES:**
1. Extract only components that actually exist on the invoice
2. Don't force predetermined component lists
3. Adapt to any vehicle type (commercial, passenger, specialty)
4. Use appropriate attribute names for each component type
5. Preserve technical specifications exactly as written
6. Focus on functional equipment and major components
7. Component IDs start at 3167729, increment sequentially
8. Attribute IDs start at 0 within each component
9. Leave fields empty ("") if not clearly specified
10. Correct VIN characters: 'O'→'0', 'I'→'1', 'Q'→'0'

**RETURN ONLY VALID JSON WITH DYNAMIC STRUCTURE BASED ON ACTUAL INVOICE CONTENT**
"""