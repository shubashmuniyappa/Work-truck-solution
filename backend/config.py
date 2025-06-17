import json
from datetime import datetime

import os
from dotenv import load_dotenv

def load_environment_variables():
    load_dotenv()

    doc_intelligence_endpoint = os.getenv("AZURE_DOC_INTELLIGENCE_ENDPOINT")
    doc_intelligence_key = os.getenv("AZURE_DOC_INTELLIGENCE_KEY")

    openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    openai_key = os.getenv("AZURE_OPENAI_KEY")
    openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    training_folder = os.getenv("TRAINING_FOLDER", "../Training-pdf/")
    analysis_features = ["ocrHighResolution"]

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
    """
    Loads body model names from a text file, one per line.

    Args:
        file_path (str): The path to the file containing body models.

    Returns:
        list[str]: A list of body model strings.
    """
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Warning: Body models file {file_path} not found.")
        return []
    except Exception as e:
        print(f"Error loading body models from {file_path}: {str(e)}")
        return []

def clean_and_validate_json(raw_content: str, filename: str) -> dict:
    """
    Cleans the raw content (removes markdown) and parses it as JSON.
    Validates and standardizes the JSON structure, adding default values if missing.

    Args:
        raw_content (str): The raw string content from the LLM.
        filename (str): The name of the file being processed, used for document path.

    Returns:
        dict: The cleaned, validated, and standardized JSON data.
    """
    cleaned_content = raw_content.strip()
    # Attempt to remove common markdown fences
    if cleaned_content.startswith("```json"):
        cleaned_content = cleaned_content[7:]
    if cleaned_content.startswith("```"):
        cleaned_content = cleaned_content[3:]
    if cleaned_content.endswith("```"):
        cleaned_content = cleaned_content[:-3]
    cleaned_content = cleaned_content.strip()

    data = {}
    try:
        data = json.loads(cleaned_content)
        print(f"Successfully parsed JSON for {filename}")

    except json.JSONDecodeError as e:
        print(f"JSON parsing error for {filename}: {e}")
        print(f"Raw content (first 500 chars): {cleaned_content[:500]}...")
        # Fallback to a minimal structure on parsing error
        pass

    # Ensure required fields exist and standardize
    required_fields = ["inventory_arrival_date", "stock_number", "vin", "condition",
                       "model_year", "make", "model", "body_type", "body_line",
                       "body_manufacturer", "body_model", "distributor",
                       "distributor_location", "invoice_date", "components", "documents"]

    for field in required_fields:
        if field not in data or data[field] is None: # Handle None values explicitly
            data[field] = ""

    # Ensure components structure exists and standardize
    if "components" not in data or not isinstance(data["components"], list):
        data["components"] = []

    # Ensure each component has required structure with attribute IDs
    BASE_COMPONENT_ID = 3167729 # Define as a constant
    for i, component in enumerate(data["components"]):
        if "id" not in component:
            component["id"] = BASE_COMPONENT_ID + i
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
        # Update existing document entry or create if first is malformed
        if not isinstance(data["documents"][0], dict):
            data["documents"][0] = {} # Ensure it's a dictionary
        data["documents"][0]["date"] = current_date
        data["documents"][0]["path"] = document_path
        if "type" not in data["documents"][0] or not data["documents"][0]["type"]:
            data["documents"][0]["type"] = "Invoice"

    return data

def get_minimal_data_structure(filename: str) -> dict:
    """
    Returns a minimal, valid data structure for a given filename,
    used when full processing fails.

    Args:
        filename (str): The name of the file that failed processing.

    Returns:
        dict: A dictionary with a minimal, standardized structure.
    """
    current_date = datetime.now().strftime('%Y-%m-%d')
    document_path = f"img/invoices/bodyinvoices/-/{filename}"

    return {
        "inventory_arrival_date": "",
        "stock_number": "",
        "vin": "",
        "condition": "New", # Default to New if condition extraction fails
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