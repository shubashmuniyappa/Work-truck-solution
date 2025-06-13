import os
from openai import AzureOpenAI # type: ignore
import json
from azure.core.credentials import AzureKeyCredential # type: ignore
from azure.ai.documentintelligence import DocumentIntelligenceClient # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader # type: ignore
import uuid
from datetime import datetime
from guidelines import guidelines

# Replace with your actual endpoint and key
endpoint = "https://quaddocintelligence1.cognitiveservices.azure.com/"
key = "53uBovu34ZLs4HFKjFo3nW3qDUh8utA0gBY3Q8BlcjpTkPmefnBWJQQJ99BEACYeBjFXJ3w3AAALACOGSie3"
training_folder = "../Training-pdf/"  # Path to your training folder

analysis_features = ["ocrHighResolution"]

# Azure OpenAI configuration
openai_endpoint = "https://nikhi-mb4qln04-swedencentral.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
model_name = "gpt-4o"
deployment = "gpt-4o"
subscription_key = "4prHi16lJv4qDEATOl11M4f99KCcnntffozdHXm2Umfq8t3KeWVJJQQJ99BEACfhMk5XJ3w3AAAAACOGEJ7N"
api_version = "2025-01-01-preview"

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=openai_endpoint,
    api_key=subscription_key,
)

# Initialize list to store all processed data
all_data = []

# Process each PDF file in the training folder
for filename in os.listdir(training_folder):
    if filename.lower().endswith('.pdf'):
        file_path = os.path.join(training_folder, filename)
        print(f"Processing file: {filename}")
        
        try:
            document_intelligence_client = AzureAIDocumentIntelligenceLoader(
                api_endpoint=endpoint,
                api_key=key, 
                file_path=file_path, 
                api_model="prebuilt-invoice",
                mode="page",
                analysis_features=analysis_features,
            )

            documents = document_intelligence_client.load()
            print(f"Loaded document: {filename}")

            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """
You are an expert vehicle invoice parser that extracts structured data from automobile invoices including truck bodies, equipment, and vehicle modifications.

**CRITICAL: Return ONLY valid JSON - no markdown, no explanations, no additional text.**

**PARSING INSTRUCTIONS:**

**1. HEADER INFORMATION:**
- distributor: Extract the body/equipment manufacturer name from invoice header (the company that built/supplied the body/equipment, NOT the dealer/sold-to)
- distributor_location: Extract manufacturer's location from header (City, State ZIP format)
- make: Proper case formatting (e.g., "Ford", "International", "Freightliner", "Chevrolet", "Ram")
- model: Include dashes and proper formatting (e.g., "F-600", "MV", "Cascadia", "Silverado", "ProMaster")
- body_type: Classify as "Box Truck", "Flatbed", "Tank Truck", "Service Body", "Pickup Truck", "Van", "Other/Specialty", etc.
- body_line: More specific description if available (e.g., "Water Truck", "Dry Van", "Stake Bed", "Refrigerated", "Utility Body") - leave empty if not clearly specified
- body_manufacturer: The company that manufactured the body/equipment
- body_model: Full descriptive specification from invoice

**2. INVENTORY ARRIVAL DATE:**
- inventory_arrival_date: ONLY extract if date is hand-written on the document or explicitly labeled as "arrival date", "delivery date", or similar
- Leave empty ("") if no hand-written or explicit arrival date is found
- Do not use invoice date, quote date, or other standard dates

**3. DYNAMIC COMPONENT EXTRACTION:**
- Analyze invoice content to identify ALL installed components/equipment
- Create components based on what's actually present in the invoice
- Start component IDs from a base number (0) and increment sequentially
- Common component types include:
  * Body/Tank: Main structure with dimensions and materials
  * Engine: Motor specifications
  * Transmission: Gearbox details
  * Pump/PTO: Power systems
  * Hose Reel: Hose management systems  
  * Ladder: Access equipment
  * Safety Equipment: Safety features and kits
  * Electrical: Lighting, cameras, controls, batteries
  * Hydraulics: Lift gates, dump systems
  * Plumbing: Valves, fittings, tanks
  * Storage: Toolboxes, compartments
  * Accessories: Steps, fenders, guards, bumpers
  * Interior: Seats, dash components, upholstery
  * Exterior: Paint, decals, mirrors

**4. ATTRIBUTE EXTRACTION RULES:**
- Start attribute IDs from 0 and increment sequentially within each component
- Material: Steel, Aluminum, Composite, Stainless Steel, Plastic, etc.
- Dimensions: Use inches with quote marks (64.75", 96", 192")
- Capacity: Include units (2,000 Gallon, 2500lb, etc.)
- Description: Comprehensive but concise feature descriptions
- Manufacturer/Model: When specified for components
- Type: Functional classification

**5. FLEXIBLE STRUCTURE:**
- Extract only components that actually exist in the invoice
- Don't force predetermined component lists
- Adapt to different vehicle types (trucks, vans, cars, specialty vehicles)
- Use appropriate attribute names based on component type

**6. DATE AND DOCUMENT HANDLING:**
- All dates in YYYY-MM-DD format
- inventory_arrival_date: Only if hand-written or explicitly labeled as arrival/delivery date
- invoice_date: Actual invoice/quote date
- Document type: "Invoice", "Sales Quote", "Work Order", "Bill of Sale", etc.

**7. MATERIAL AND SPECIFICATION PRECISION:**
- Extract exact materials mentioned (Steel, Aluminum, Composite, etc.)
- Convert dimensions to consistent units (inches preferred)
- Include capacity ratings with units
- Preserve technical specifications exactly as stated

**8. DOCUMENT PATH STRUCTURE:**
- path: "img/invoices/bodyinvoices/-/" + filename
- date: Today's date (current date when processing)
- type: Document type from invoice ("Invoice", "Quote", "Bill of Sale", etc.)

Return the JSON structure with all identified components and their specific attributes:
{
  "inventory_arrival_date": "",
  "stock_number": "",
  "vin": "",
  "condition": "",
  "model_year": "",
  "make": "",
  "model": "",
  "body_type": "",
  "body_line": "",
  "body_manufacturer": "",
  "body_model": "",
  "distributor": "",
  "distributor_location": "",
  "invoice_date": "",
  "components": [
    {
      "id": 1,
      "name": "Component Name",
      "attributes": [
        { "id": 0, "name": "Attribute Name", "value": "Attribute Value" },
        { "id": 1, "name": "Attribute Name", "value": "Attribute Value" }
      ]
    }
  ],
  "documents": [
    {
      "date": "2025-06-10",
      "type": "Invoice",
      "path": "img/invoices/bodyinvoices/-/filename.pdf"
    }
  ]
}
"""
                    },
                    {
                        "role": "user",
                        "content": f"""
Extract the information from the following document text and return it in the required JSON format:

Document filename: {filename}
Current date: {datetime.now().strftime('%Y-%m-%d')}

{documents}

{guidelines}
"""
                    }
                ],
                max_tokens=5000,
                temperature=1.0,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=deployment
            )

            raw_content = response.choices[0].message.content

            # Clean the response - remove any markdown formatting
            cleaned_content = raw_content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            if cleaned_content.startswith("```"):
                cleaned_content = cleaned_content[3:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            cleaned_content = cleaned_content.strip()

            # Parse and validate JSON structure
            try:
                data = json.loads(cleaned_content)
                
                # Ensure required fields exist (but don't enforce specific values)
                required_fields = ["inventory_arrival_date", "stock_number", "vin", "condition", 
                                  "model_year", "make", "model", "body_type", "body_line", 
                                  "body_manufacturer", "body_model", "distributor", 
                                  "distributor_location", "invoice_date", "components", "documents"]
                
                for field in required_fields:
                    if field not in data:
                        data[field] = ""
                
                # Ensure components structure exists
                if "components" not in data or not isinstance(data["components"], list):
                    data["components"] = []
                
                # Ensure each component has required structure with attribute IDs
                component_id = 3167729  # Base component ID
                for i, component in enumerate(data["components"]):
                    if "id" not in component:
                        component["id"] = component_id + i
                    if "name" not in component:
                        component["name"] = f"Component_{i+1}"
                    if "attributes" not in component or not isinstance(component["attributes"], list):
                        component["attributes"] = []
                    
                    # Ensure each attribute has an ID starting from 0
                    for j, attribute in enumerate(component["attributes"]):
                        if "id" not in attribute:
                            attribute["id"] = j
                        if "name" not in attribute:
                            attribute["name"] = f"Attribute_{j+1}"
                        if "value" not in attribute:
                            attribute["value"] = ""
                
                # Ensure documents structure exists with current date and correct path
                current_date = datetime.now().strftime('%Y-%m-%d')
                document_path = f"img/invoices/bodyinvoices/-/{filename}"
                
                if "documents" not in data or not isinstance(data["documents"], list) or len(data["documents"]) == 0:
                    data["documents"] = [{
                        "date": current_date,
                        "type": "Invoice",
                        "path": document_path
                    }]
                else:
                    # Update existing document entry
                    data["documents"][0]["date"] = current_date
                    data["documents"][0]["path"] = document_path
                    if "type" not in data["documents"][0] or not data["documents"][0]["type"]:
                        data["documents"][0]["type"] = "Invoice"
                
                print(f"Successfully parsed JSON for {filename}")
                all_data.append(data)
                
            except json.JSONDecodeError as e:
                print(f"JSON parsing error for {filename}: {e}")
                print(f"Raw content: {cleaned_content}")
                # Create minimal structure on error
                current_date = datetime.now().strftime('%Y-%m-%d')
                document_path = f"img/invoices/bodyinvoices/-/{filename}"
                
                data = {
                    "inventory_arrival_date": "",
                    "stock_number": "",
                    "vin": "",
                    "condition": "New",
                    "model_year": "",
                    "make": "",
                    "model": "",
                    "body_type": "",
                    "body_line": "",
                    "body_manufacturer": "",
                    "body_model": "",
                    "distributor": "",
                    "distributor_location": "",
                    "invoice_date": "",
                    "components": [],
                    "documents": [{
                        "date": current_date,
                        "type": "Invoice",
                        "path": document_path
                    }]
                }
                all_data.append(data)
                
        except Exception as e:
            print(f"Error processing file {filename}: {str(e)}")
            # Add minimal structure even if processing failed
            current_date = datetime.now().strftime('%Y-%m-%d')
            document_path = f"img/invoices/bodyinvoices/-/{filename}"
            
            data = {
                "inventory_arrival_date": "",
                "stock_number": "",
                "vin": "",
                "condition": "New",
                "model_year": "",
                "make": "",
                "model": "",
                "body_type": "",
                "body_line": "",
                "body_manufacturer": "",
                "body_model": "",
                "distributor": "",
                "distributor_location": "",
                "invoice_date": "",
                "components": [],
                "documents": [{
                    "date": current_date,
                    "type": "Invoice",
                    "path": document_path
                }]
            }
            all_data.append(data)

# Save all processed data to a single JSON file
with open("data.json", "w") as f:
    json.dump(all_data, f, indent=2)

print(f"Processed {len(all_data)} files and saved to all_data.json")