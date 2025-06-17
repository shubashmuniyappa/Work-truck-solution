import os
import json
from datetime import datetime
from openai import AzureOpenAI
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader

from config import load_environment_variables
from utils import load_body_models, clean_and_validate_json, get_minimal_data_structure
from guidelines import guidelines # Assuming guidelines.py is in the same directory

class InvoiceProcessor:
    """
    A class for processing vehicle invoices using Azure Document Intelligence and Azure OpenAI.
    Encapsulates all necessary configurations and processing logic.
    """
    def __init__(self):
        """
        Initializes the InvoiceProcessor by loading environment variables,
        body models, and setting up Azure AI clients.
        """
        (self.doc_intelligence_endpoint, self.doc_intelligence_key,
         self.openai_endpoint, self.openai_key, self.openai_api_version,
         self.openai_deployment, self.training_folder, self.analysis_features) = \
            load_environment_variables()

        self.body_models = load_body_models("body_model.txt")
        if not self.body_models:
            print("Warning: No body models loaded. LLM might have reduced context for 'body_model' field.")

        self.openai_client = AzureOpenAI(
            api_version=self.openai_api_version,
            azure_endpoint=self.openai_endpoint,
            api_key=self.openai_key,
        )
        print("InvoiceProcessor initialized with Azure AI clients.")

    def load_document_intelligence_data(self, file_path: str) -> str:
        """
        Loads and extracts text content from a PDF document using Azure Document Intelligence.

        Args:
            file_path (str): The full path to the PDF file.

        Returns:
            str: The extracted text content from the document.

        Raises:
            Exception: If there's an error loading the document.
        """
        try:
            document_intelligence_loader = AzureAIDocumentIntelligenceLoader(
                api_endpoint=self.doc_intelligence_endpoint,
                api_key=self.doc_intelligence_key,
                file_path=file_path,
                api_model="prebuilt-invoice",
                mode="page",
                analysis_features=self.analysis_features,
            )
            documents = document_intelligence_loader.load()
            print(f"Successfully loaded document from Document Intelligence: {file_path}")
            # Assuming 'documents' is a list of Document objects, join their page_content
            return "\n".join([doc.page_content for doc in documents])
        except Exception as e:
            raise Exception(f"Failed to load document from Document Intelligence: {e}")

    def extract_invoice_data_with_llm(self, document_content: str, filename: str) -> str:
        """
        Sends the extracted document content to Azure OpenAI for structured data extraction.

        Args:
            document_content (str): The text content extracted from the invoice.
            filename (str): The name of the original PDF file (for context in prompt).

        Returns:
            str: The raw JSON string response from the LLM.

        Raises:
            Exception: If the LLM call fails.
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        prompt_content = f"""
Extract the information from the following document text and return it in the required JSON format:

Document filename: {filename}
Current date: {current_date}

{document_content}

{guidelines}
"""
        # Construct the system message with body models for context
        system_message_content = f"""
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

**9. KNOWLEDGE BASE OF BODY MODELS:**
Below is a list of known body models for reference when identifying the body_model from invoice text:
""" + '\n'.join([f"- {model}" for model in self.body_models]) + """

Instructions for extracting the body_model field:

Exact Match:
If the invoice text contains a body model name that exactly matches one from the knowledge base, return that exact match.

Fuzzy/Similar Match:
If no exact match is found, identify the most similar model name from the knowledge base. Accept close variations where the difference is minor (e.g., "16' Dry Van" vs "16' Composite Van"). Return the matched model name from the knowledge base.

Annotated Variations (Optional):
If the invoice text includes extra descriptive details (e.g., size, material), consider appending or preserving those details alongside the matched model name as additional context.

No Match Found:
If no close match exists in the knowledge base, return the original body_model text as it appears in the invoice.
# Replace the current body model instructions with this more detailed version:

**BODY MODEL EXTRACTION RULES:**

1. **Exact Match Priority**:
   - First look for EXACT matches (case-insensitive) between invoice text and known models
   - Pay special attention to alphanumeric codes (like "PVMXT-263C", "782F") - these should match exactly or not at all

2. **Partial Match Rules**:
   For non-alphanumeric models (descriptive names), use these matching rules:
   - Match if ≥80% of words appear in same order ("Pro Series" matches "9' Pro Series - Platform")
   - Ignore measurements and dimensions when matching ("8'6" SK Deluxe" matches "SK Deluxe")
   - Ignore punctuation and special characters

3. **No Match Handling**:
   - If no match found, return the FULL descriptive text from the invoice
   - Never return a partial match for alphanumeric codes
   - For descriptive names, you may return the closest match with original details in parentheses

4. **Special Cases**:
   - "Stake" models: Match both "PVMXT-263C Stake" and "PHHJT-123B Stake" to any mention of "Stake"
   - Numeric models: "782F" should only match exactly "782F" or "782 F" (with space)
   - Branded models: "Duracube" should match any mention of "Duracube" followed by numbers

**KNOWN BODY MODELS:**
""" + '\n'.join([f"- {model}" for model in self.body_models]) + """

**CRITICAL: Return ONLY valid JSON - no markdown, no explanations, no additional text.**

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


        try:
            response = self.openai_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_message_content},
                    {"role": "user", "content": prompt_content}
                ],
                max_tokens=5000,
                temperature=1.0,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=self.openai_deployment
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Azure OpenAI API call failed: {e}")

    def process_single_invoice(self, file_path: str, filename: str) -> dict:
        """
        Processes a single PDF invoice file.

        Args:
            file_path (str): The full path to the PDF file.
            filename (str): The name of the PDF file.

        Returns:
            dict: The standardized JSON data extracted from the invoice.
        """
        print(f"Processing file: {filename}")
        try:
            document_content = self.load_document_intelligence_data(file_path)
            raw_llm_response = self.extract_invoice_data_with_llm(document_content, filename)
            processed_data = clean_and_validate_json(raw_llm_response, filename)
            print(f"Successfully processed and validated data for {filename}")
            return processed_data
        except Exception as e:
            print(f"Error processing file {filename}: {str(e)}")
            return get_minimal_data_structure(filename)

    def process_all_invoices_in_folder(self, output_json_filename: str = "data.json") -> None:
        """
        Processes all PDF files in the configured training folder and saves
        the combined results to a single JSON file.

        Args:
            output_json_filename (str): The name of the output JSON file.
        """
        all_processed_data = []
        if not os.path.isdir(self.training_folder):
            print(f"Error: Training folder '{self.training_folder}' not found.")
            return

        for filename in os.listdir(self.training_folder):
            if filename.lower().endswith('.pdf'):
                file_path = os.path.join(self.training_folder, filename)
                data = self.process_single_invoice(file_path, filename)
                all_processed_data.append(data)

        with open(output_json_filename, "w") as f:
            json.dump(all_processed_data, f, indent=2)

        print(f"Processed {len(all_processed_data)} files and saved to {output_json_filename}")

if __name__ == "__main__":
    processor = InvoiceProcessor()
    processor.process_all_invoices_in_folder()