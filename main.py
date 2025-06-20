import os
import json
from datetime import datetime
from openai import AzureOpenAI
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader
from typing import List, Dict, Optional

# Import custom configuration and utility functions
from config import load_environment_variables
from utils import load_body_models, clean_and_validate_json, get_minimal_data_structure
from guidelines import guidelines

class InvoiceProcessor:
    def __init__(self):
        # Load environment variables for Azure AI services and OpenAI
        (self.doc_intelligence_endpoint, self.doc_intelligence_key,
         self.openai_endpoint, self.openai_key, self.openai_api_version,
         self.openai_deployment, self.training_folder, self.analysis_features) = \
            load_environment_variables()

        # Load predefined body models from a text file
        self.body_models = load_body_models("body_model.txt")
        if not self.body_models:
            print("Warning: No body models loaded. LLM might have reduced context for 'body_model' field.")

        # Initialize the Azure OpenAI client
        self.openai_client = AzureOpenAI(
            api_version=self.openai_api_version,
            azure_endpoint=self.openai_endpoint,
            api_key=self.openai_key,
        )

    def load_document_intelligence_data(self, file_path: str) -> str:
        # Use Azure AIDocumentIntelligenceLoader to extract text from a PDF document
        try:
            document_intelligence_loader = AzureAIDocumentIntelligenceLoader(
                api_endpoint=self.doc_intelligence_endpoint,
                api_key=self.doc_intelligence_key,
                file_path=file_path,
                api_model="prebuilt-invoice",  # Specify the prebuilt model for invoices
                mode="page",  # Process document page by page
                analysis_features=self.analysis_features,
            )
            # Load documents and concatenate page content into a single string
            documents = document_intelligence_loader.load()
            return "\n".join([doc.page_content for doc in documents])
        except Exception as e:
            # Raise an exception if document loading fails
            raise Exception(f"Failed to load document: {e}")

    def extract_invoice_data_with_llm(self, document_content: str, filename: str) -> str:
        # Get the current date to include in the prompt
        current_date = datetime.now().strftime('%Y-%m-%d')
        # Construct the user prompt with document content and guidelines
        prompt_content = f"""
Extract the information from the following document text and return it in the required JSON format:

Document filename: {filename}
Current date: {current_date}

{document_content}

{guidelines}
"""

        # Define the system message for the LLM, instructing it on data extraction and formatting
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

**CRITICAL: Return ONLY valid JSON - no markdown, no explanations, no additional text.**
"""

        # Make a chat completion request to Azure OpenAI
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
            # Return the extracted content from the LLM response
            return response.choices[0].message.content
        except Exception as e:
            # Raise an exception if the API call fails
            raise Exception(f"Azure OpenAI API call failed: {e}")

    def process_single_invoice(self, file_path: str, filename: str) -> Dict:
        # Process a single invoice file
        try:
            # Load document content using Azure Document Intelligence
            document_content = self.load_document_intelligence_data(file_path)
            # Extract raw JSON data using the LLM
            raw_llm_response = self.extract_invoice_data_with_llm(document_content, filename)
            # Clean, validate, and standardize the JSON response
            processed_data = clean_and_validate_json(raw_llm_response, filename)
            return processed_data
        except Exception as e:
            # If processing fails, print an error and return a minimal data structure
            print(f"Error processing file {filename}: {str(e)}")
            return get_minimal_data_structure(filename)

    def process_invoices(self, file_paths: List[str]) -> Dict[str, Dict]:
        # Process a list of invoice file paths
        results = {}
        for file_path in file_paths:
            # Extract filename from the file path
            filename = os.path.basename(file_path)
            # Process each invoice and store the result with the filename as key
            results[filename] = self.process_single_invoice(file_path, filename)
        return results