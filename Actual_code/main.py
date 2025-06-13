import os
from openai import AzureOpenAI # type: ignore
import json
from azure.core.credentials import AzureKeyCredential # type: ignore
from azure.ai.documentintelligence import DocumentIntelligenceClient # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader # type: ignore
import uuid
import re
from datetime import datetime

# Enhanced Guidelines
guidelines = """
ENHANCED EXTRACTION GUIDELINES:

=== CRITICAL EXTRACTION RULES ===
1. ONLY extract fields that are EXPLICITLY present in the invoice
2. Use EMPTY STRING "" for any field not found in the document
3. Focus on PRECISE component and attribute extraction
4. Auto-increment component IDs starting from 1

=== DATE FORMATTING ===
- Convert ALL dates to YYYY-MM-DD format:
  - "03/12/25" → "2025-03-12"
  - "March 12, 2025" → "2025-03-12"
  - "12-Mar-25" → "2025-03-12"
- For 2-digit years: 00-30 = 20xx, 31-99 = 19xx

=== FIELD EXTRACTION PRIORITIES ===

1. **Stock Number**: Look for variations:
   - "Stock Number", "Stock #", "Stock No.", "Item #", "Part #", "Unit #"
   - Extract exact alphanumeric value

2. **VIN**: 17-character vehicle identification number
   - Usually starts with numbers/letters like "1FD", "3C6", "54D", etc.

3. **Vehicle Information**:
   - Make: Ford, Chevrolet, Ram, Isuzu, etc.
   - Model: F-600, Transit 350, ProMaster, LCF 5500, etc.
   - Year: 4-digit year (2024, 2025, etc.)

4. **Body Information**:
   - body_type: "Box Truck", "Service Utility Van", "Upfitted Cargo Van", "Dovetail Landscape", "Service Truck"
   - body_manufacturer: "Marathon", "Knapheide", "Reading", "Wil-Ro"
   - body_model: Include dimensions and specifications

5. **Distributor Information**:
   - Look for dealer/distributor name and complete address
   - Include city, state, and ZIP code

=== ENHANCED COMPONENT MAPPING STRATEGY ===

Extract EVERY line item and group into logical components:

**Primary Components**:
- Body/Van Body/Truck Body → "Body"
- Floor/Flooring/Floor Assembly → "Floor"  
- Roof/Roof Assembly/Roof Structure → "Roof"
- Door/Rear Door/Roll-Up Door/Barn Door → "Door"
- Liftgate/Lift Gate/Tailgate → "Liftgate"
- Toolbox/Tool Box/Storage Box → "Toolbox"
- Bumper/Step Bumper → "Bumper"
- Shelving/Shelves → "Shelving"
- Lighting/Lights/LED Lights → "Lighting"
- Compartment/Storage Compartment → "Compartment"

**Secondary Components**:
- E-Track/Cargo Control/Tie Downs → "Cargo Control"
- Bulkhead/Partition → "Bulkhead"
- Headache Rack/Headboard → "Headache Rack"
- Mud Flaps → "Mud Flaps"
- Hitch/Receiver Hitch → "Hitch"
- Alarm/Warning System → "Alarm"
- Camera/Backup Camera → "Camera"
- Ladder Rack → "Ladder Rack"
- Side Panels/Sides → "Side"
- Dovetail/Ramp → "Dovetail"

=== PRECISE ATTRIBUTE EXTRACTION ===

For each component, extract ALL relevant attributes from the invoice text:

**Dimension Attributes**:
- Width, Height, Length, Depth, Thickness
- Inside Width, Inside Height, Inside Length
- Platform dimensions

**Material Attributes**:
- Material: Aluminum, Steel, Composite, Hardwood, etc.
- Gauge: 12 gauge, 14 gauge, etc.

**Specification Attributes**:
- Model, Part Number, Description
- Type, Style, Class
- Manufacturer, Brand
- Quantity, Weight, Capacity
- Color, Finish

**Feature Attributes**:
- Special features, options, accessories
- Location (Front, Rear, Both Sides, etc.)

=== ATTRIBUTE EXTRACTION RULES ===

1. **Capture Complete Descriptions**: Include full product descriptions
2. **Preserve Technical Details**: Keep model numbers, specifications
3. **Extract Dimensions**: Capture all measurements with units
4. **Include Options**: List all optional features and upgrades
5. **Maintain Context**: Keep related information together

=== CLEANING AND FORMATTING RULES ===

1. **Remove Prefixes**: Strip "Item:", "Part:", "Description:", etc.
2. **Preserve Units**: Keep ", \", ', lbs, etc. in values
3. **Clean Whitespace**: Remove extra spaces, normalize formatting
4. **Handle Special Characters**: Preserve dimension symbols and technical notation
5. **Empty Fields**: Use "" for any field not found in invoice

=== VALIDATION REQUIREMENTS ===

Before returning JSON:
☐ All dates in YYYY-MM-DD format
☐ Component IDs auto-increment starting from 1
☐ Components extracted from actual invoice line items
☐ Attributes capture complete specifications
☐ Only fields present in invoice are populated
☐ Empty strings for missing fields
☐ Documents array included with correct path

=== COMPONENT GROUPING LOGIC ===

Group related line items intelligently:
- Multiple lighting items → separate "Lighting" components with different attributes
- Door hardware and door → combine into "Door" component
- Related accessories → group by function (e.g., all hitch-related items)

EXTRACT EVERY POSSIBLE DETAIL FROM THE INVOICE.
RETURN ONLY THE STRUCTURED JSON - NO EXPLANATIONS.
"""

class InvoiceParser:
    def __init__(self, azure_endpoint, azure_key, openai_endpoint, openai_key, api_version="2025-01-01-preview"):
        self.azure_endpoint = azure_endpoint
        self.azure_key = azure_key
        self.openai_client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=openai_endpoint,
            api_key=openai_key,
        )
        self.deployment = "gpt-4o"
    
    def extract_document_text(self, file_path):
        """Extract text from PDF using Azure Document Intelligence"""
        try:
            analysis_features = ["ocrHighResolution"]
            
            document_intelligence_client = AzureAIDocumentIntelligenceLoader(
                api_endpoint=self.azure_endpoint,
                api_key=self.azure_key,
                file_path=file_path,
                api_model="prebuilt-invoice",
                mode="page",
                analysis_features=analysis_features,
            )
            
            documents = document_intelligence_client.load()
            print("Document content extracted successfully")
            return documents
            
        except Exception as e:
            print(f"Error extracting document: {e}")
            return None
    
    def normalize_date(self, date_str):
        """Normalize date to YYYY-MM-DD format"""
        if not date_str:
            return ""
        
        # Common date patterns
        patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{2,4})',  # MM/DD/YY or MM/DD/YYYY
            r'(\d{1,2})-(\d{1,2})-(\d{2,4})',  # MM-DD-YY or MM-DD-YYYY
            r'(\d{4})-(\d{1,2})-(\d{1,2})',    # YYYY-MM-DD (already correct)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                part1, part2, part3 = match.groups()
                
                # Handle different formats
                if len(part1) == 4:  # YYYY-MM-DD format
                    return f"{part1}-{part2.zfill(2)}-{part3.zfill(2)}"
                else:  # MM/DD/YY or MM-DD-YY format
                    year = int(part3)
                    if year < 50:
                        year += 2000
                    elif year < 100:
                        year += 1900
                    
                    return f"{year}-{part1.zfill(2)}-{part2.zfill(2)}"
        
        return date_str  # Return as-is if no pattern matches
    
    def create_enhanced_prompt(self, documents, file_path):
        """Create enhanced prompt for precise extraction"""
        return f"""
Extract ALL information from the following invoice document and return it in the required JSON format.

CRITICAL INSTRUCTIONS:
1. Extract ONLY fields that are explicitly present in the invoice
2. Use empty string "" for any field not found
3. Focus on extracting EVERY component and attribute mentioned
4. Auto-increment component IDs starting from 1
5. Group related line items into logical components
6. Preserve all technical specifications and dimensions

Document text:
{documents}

Guidelines:
{guidelines}

File path for reference: {file_path}

REQUIRED JSON STRUCTURE:
{{
  "inventory_arrival_date": "YYYY-MM-DD or empty string",
  "stock_number": "exact stock number from invoice or empty string",
  "vin": "17-character VIN or empty string", 
  "condition": "New/Used/Refurbished or empty string",
  "model_year": "4-digit year or empty string",
  "make": "vehicle manufacturer or empty string",
  "model": "vehicle model or empty string",
  "body_type": "body type description or empty string",
  "body_line": "body line specification or empty string", 
  "body_manufacturer": "body manufacturer or empty string",
  "body_model": "body model with specifications or empty string",
  "distributor": "distributor/dealer name or empty string",
  "distributor_location": "distributor location or empty string",
  "invoice_date": "YYYY-MM-DD or empty string",
  "components": [
    {{
      "id": 1,
      "name": "Component Name",
      "attributes": [
        {{"name": "Attribute Name", "value": "Attribute Value"}}
      ]
    }}
  ],
  "documents": [
    {{
      "date": "YYYY-MM-DD",
      "type": "Invoice", 
      "path": "img/invoices/bodyinvoices/-/filename.pdf"
    }}
  ]
}}

RETURN ONLY THE JSON - NO EXPLANATIONS OR ADDITIONAL TEXT.
"""
    
    def parse_invoice(self, file_path):
        """Main method to parse invoice and extract structured data"""
        print(f"Processing invoice: {file_path}")
        
        # Extract document text
        documents = self.extract_document_text(file_path)
        if not documents:
            return None
        
        print("\nDocument text extracted, sending to AI for processing...")
        
        # Create enhanced prompt
        prompt = self.create_enhanced_prompt(documents, file_path)
        
        try:
            # Send to OpenAI for processing
            response = self.openai_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert invoice parser that extracts precise structured data from truck invoice documents. Extract ONLY information that is explicitly present in the invoice."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=8000,
                temperature=0.0,  # Most consistent extraction
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=self.deployment
            )
            
            raw_content = response.choices[0].message.content
            print("\nRaw AI Response received")
            
            # Clean and parse JSON
            parsed_data = self.clean_and_parse_json(raw_content, file_path)
            
            if parsed_data:
                print("\nSuccessfully parsed invoice data")
                return parsed_data
            else:
                print("\nFailed to parse JSON response")
                return None
                
        except Exception as e:
            print(f"Error processing with AI: {e}")
            return None
    
    def clean_and_parse_json(self, raw_content, file_path):
        """Clean AI response and parse JSON"""
        try:
            # Clean the response
            cleaned_content = raw_content.strip()
            
            # Remove markdown code blocks
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            elif cleaned_content.startswith("```"):
                cleaned_content = cleaned_content[3:]
            
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            
            cleaned_content = cleaned_content.strip()
            
            # Parse JSON
            data = json.loads(cleaned_content)
            
            # Post-process and validate
            data = self.post_process_data(data, file_path)
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {e}")
            print("Cleaned content preview:")
            print(cleaned_content[:500] + "..." if len(cleaned_content) > 500 else cleaned_content)
            
            # Save for debugging
            with open("debug_output.txt", "w", encoding='utf-8') as f:
                f.write(f"Raw content:\n{raw_content}\n\nCleaned content:\n{cleaned_content}")
            
            return None
            
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def post_process_data(self, data, file_path):
        """Post-process extracted data for consistency"""
        # Ensure documents array exists
        if "documents" not in data or not data["documents"]:
            data["documents"] = [
                {
                    "date": data.get("invoice_date", ""),
                    "type": "Invoice",
                    "path": f"img/invoices/bodyinvoices/-/{os.path.basename(file_path)}"
                }
            ]
        
        # Normalize dates
        if "invoice_date" in data and data["invoice_date"]:
            data["invoice_date"] = self.normalize_date(data["invoice_date"])
        
        if "inventory_arrival_date" in data and data["inventory_arrival_date"]:
            data["inventory_arrival_date"] = self.normalize_date(data["inventory_arrival_date"])
        
        # Ensure components have sequential IDs
        if "components" in data and data["components"]:
            for i, component in enumerate(data["components"], 1):
                component["id"] = i
                # Ensure attributes exist
                if "attributes" not in component:
                    component["attributes"] = []
        
        # Ensure all required fields exist
        required_fields = [
            "inventory_arrival_date", "stock_number", "vin", "condition", 
            "model_year", "make", "model", "body_type", "body_line", 
            "body_manufacturer", "body_model", "distributor", 
            "distributor_location", "invoice_date", "components", "documents"
        ]
        
        for field in required_fields:
            if field not in data:
                if field in ["components", "documents"]:
                    data[field] = []
                else:
                    data[field] = ""
        
        return data
    
    def save_results(self, data, output_file="extracted_data.json"):
        """Save extracted data to JSON file"""
        try:
            with open(output_file, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\nData successfully saved to {output_file}")
            return True
        except Exception as e:
            print(f"Error saving data: {e}")
            return False

# Main execution
def main():
    # Configuration
    azure_endpoint = "https://quaddocintelligence1.cognitiveservices.azure.com/"
    azure_key = "53uBovu34ZLs4HFKjFo3nW3qDUh8utA0gBY3Q8BlcjpTkPmefnBWJQQJ99BEACYeBjFXJ3w3AAALACOGSie3"
    
    openai_endpoint = "https://nikhi-mb4qln04-swedencentral.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
    openai_key = "4prHi16lJv4qDEATOl11M4f99KCcnntffozdHXm2Umfq8t3KeWVJJQQJ99BEACfhMk5XJ3w3AAAAACOGEJ7N"
    
    file_path = r"..\Training-pdf\invoice-0c5eedf1-02b7-43f7-8082-eb1a058e3a44.pdf"
    
    # Initialize parser
    parser = InvoiceParser(azure_endpoint, azure_key, openai_endpoint, openai_key)
    
    # Parse invoice
    result = parser.parse_invoice(file_path)
    
    if result:
        # Display results
        print("\n" + "="*50)
        print("EXTRACTED DATA:")
        print("="*50)
        print(json.dumps(result, indent=2))
        
        # Save results
        parser.save_results(result, "extracted_invoice_data.json")
        
        # Display summary
        print(f"\nSUMMARY:")
        print(f"Stock Number: {result.get('stock_number', 'Not found')}")
        print(f"VIN: {result.get('vin', 'Not found')}")
        print(f"Vehicle: {result.get('model_year', '')} {result.get('make', '')} {result.get('model', '')}")
        print(f"Body Type: {result.get('body_type', 'Not found')}")
        print(f"Components Extracted: {len(result.get('components', []))}")
        
    else:
        print("Failed to process invoice")

if __name__ == "__main__":
    main()