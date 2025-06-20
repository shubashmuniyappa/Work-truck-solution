import os
import json
from datetime import datetime
from dotenv import load_dotenv

def load_environment_variables():
    # Load environment variables from a .env file
    load_dotenv()

    # Retrieve Azure Document Intelligence credentials from environment variables
    doc_intelligence_endpoint = os.getenv("AZURE_DOC_INTELLIGENCE_ENDPOINT")
    doc_intelligence_key = os.getenv("AZURE_DOC_INTELLIGENCE_KEY")

    # Retrieve Azure OpenAI credentials and deployment details from environment variables
    openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    openai_key = os.getenv("AZURE_OPENAI_KEY")
    openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    # Set the training folder path, defaulting if not found
    training_folder = os.getenv("TRAINING_FOLDER", "../Training-pdf/")
    # Define analysis features for document intelligence, here using high-resolution OCR
    analysis_features = ["ocrHighResolution"]

    # Return all loaded environment variables as a tuple
    return (
        doc_intelligence_endpoint,
        doc_intelligence_key,
        openai_endpoint,
        openai_key,
        openai_api_version,
        openai_deployment,
        training_folder,
        analysis_features,
    )

def load_body_models(file_path: str = "body_model.txt") -> list[str]:
    # Attempt to open and read the file containing body models
    try:
        with open(file_path, 'r') as f:
            # Read each line, remove leading/trailing whitespace, and filter out empty lines
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        # Warn if the body models file is not found
        print(f"Warning: Body models file {file_path} not found.")
        return []
    except Exception as e:
        # Handle other exceptions during file loading
        print(f"Error loading body models from {file_path}: {str(e)}")
        return []

def clean_and_validate_json(raw_content: str, filename: str) -> dict:
    # Remove leading/trailing whitespace from the raw content
    cleaned_content = raw_content.strip()
    # Remove common markdown fences (e.g., ```json, ```) from the content
    if cleaned_content.startswith("```json"):
        cleaned_content = cleaned_content[7:]
    if cleaned_content.startswith("```"):
        cleaned_content = cleaned_content[3:]
    if cleaned_content.endswith("```"):
        cleaned_content = cleaned_content[:-3]
    # Re-strip whitespace after markdown fence removal
    cleaned_content = cleaned_content.strip()

    data = {}
    # Attempt to parse the cleaned content as a JSON object
    try:
        data = json.loads(cleaned_content)
        print(f"Successfully parsed JSON for {filename}")
    except json.JSONDecodeError as e:
        # Log JSON parsing errors and show a snippet of the problematic content for debugging
        print(f"JSON parsing error for {filename}: {e}")
        print(f"Raw content (first 500 chars): {cleaned_content[:500]}...")
        # Continue execution with an empty 'data' dictionary if parsing fails,
        # allowing default values to be applied in subsequent steps
        pass

    # Define a list of all expected top-level fields in the JSON structure
    required_fields = ["inventory_arrival_date", "stock_number", "vin", "condition",
                       "model_year", "make", "model", "body_type", "body_line",
                       "body_manufacturer", "body_model", "distributor",
                       "distributor_location", "invoice_date", "components", "documents"]

    # Iterate through the required fields and ensure each exists in 'data',
    # setting its value to an empty string if missing or explicitly None
    for field in required_fields:
        if field not in data or data[field] is None:
            data[field] = ""

    # Ensure "components" field exists and is a list; initialize as empty list if not
    if "components" not in data or not isinstance(data["components"], list):
        data["components"] = []

    # Define a base ID for components to ensure unique IDs
    BASE_COMPONENT_ID = 3167729
    # Iterate through each component to validate and standardize its structure
    for i, component in enumerate(data["components"]):
        # Assign an ID to the component if it's missing
        if "id" not in component:
            component["id"] = BASE_COMPONENT_ID + i
        # Assign a default name if it's missing
        if "name" not in component:
            component["name"] = f"Component_{i+1}"
        # Ensure "attributes" field exists within each component and is a list; initialize if not
        if "attributes" not in component or not isinstance(component["attributes"], list):
            component["attributes"] = []

        # Iterate through each attribute within the current component to validate and standardize
        for j, attribute in enumerate(component["attributes"]):
            # Assign an ID to the attribute if it's missing
            if "id" not in attribute:
                attribute["id"] = j
            # Assign a default name if it's missing
            if "name" not in attribute:
                attribute["name"] = f"Attribute_{j+1}"
            # Assign an empty string as value if missing
            if "value" not in attribute:
                attribute["value"] = ""

    # Get the current date in YYYY-MM-DD format
    current_date = datetime.now().strftime('%Y-%m-%d')
    # Construct the document path based on the filename
    document_path = f"img/invoices/bodyinvoices/-/{filename}"

    # Check if the "documents" field is missing, not a list, or empty
    if "documents" not in data or not isinstance(data["documents"], list) or len(data["documents"]) == 0:
        # If any of the above, create a default document entry
        data["documents"] = [{
            "date": current_date,
            "type": "Invoice",
            "path": document_path
        }]
    else:
        # If "documents" exists and is not empty, ensure the first entry is a dictionary
        if not isinstance(data["documents"][0], dict):
            data["documents"][0] = {}
        # Update the date and path of the first document entry
        data["documents"][0]["date"] = current_date
        data["documents"][0]["path"] = document_path
        # Set the document type to "Invoice" if it's missing or empty
        if "type" not in data["documents"][0] or not data["documents"][0]["type"]:
            data["documents"][0]["type"] = "Invoice"

    return data

def get_minimal_data_structure(filename: str) -> dict:
    # Get the current date for the document entry
    current_date = datetime.now().strftime('%Y-%m-%d')
    # Construct the document path using the given filename
    document_path = f"img/invoices/bodyinvoices/-/{filename}"

    # Return a dictionary representing a minimal, valid data structure.
    # This serves as a fallback when full invoice processing fails.
    return {
        "inventory_arrival_date": "",
        "stock_number": "",
        "vin": "",
        "condition": "New",  # Default condition set to "New"
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