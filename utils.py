import json
from datetime import datetime

def load_body_models(file_path: str = "body_model.txt") -> list[str]:
    # Attempt to open and read the file
    try:
        with open(file_path, 'r') as f:
            # Read each line, strip whitespace, and filter out empty lines
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        # Handle the case where the file does not exist
        print(f"Warning: Body models file {file_path} not found.")
        return []
    except Exception as e:
        # Catch any other potential errors during file processing
        print(f"Error loading body models from {file_path}: {str(e)}")
        return []

def clean_and_validate_json(raw_content: str, filename: str) -> dict:
    # Remove leading/trailing whitespace from the raw content
    cleaned_content = raw_content.strip()
    # Remove common markdown JSON fences if they exist
    if cleaned_content.startswith("```json"):
        cleaned_content = cleaned_content[7:]
    if cleaned_content.startswith("```"):
        cleaned_content = cleaned_content[3:]
    if cleaned_content.endswith("```"):
        cleaned_content = cleaned_content[:-3]
    # Re-strip after fence removal
    cleaned_content = cleaned_content.strip()

    data = {}
    # Attempt to parse the cleaned content as JSON
    try:
        data = json.loads(cleaned_content)
        print(f"Successfully parsed JSON for {filename}")
    except json.JSONDecodeError as e:
        # Log JSON parsing errors and provide a snippet of the problematic content
        print(f"JSON parsing error for {filename}: {e}")
        print(f"Raw content (first 500 chars): {cleaned_content[:500]}...")
        # Continue with an empty data dictionary to apply default validations
        pass

    # Define a list of required fields for the JSON data
    required_fields = ["inventory_arrival_date", "stock_number", "vin", "condition",
                       "model_year", "make", "model", "body_type", "body_line",
                       "body_manufacturer", "body_model", "distributor",
                       "distributor_location", "invoice_date", "components", "documents"]

    # Iterate through required fields and ensure they exist, setting to empty string if missing or None
    for field in required_fields:
        if field not in data or data[field] is None:
            data[field] = ""

    # Ensure "components" field exists and is a list
    if "components" not in data or not isinstance(data["components"], list):
        data["components"] = []

    # Define a base ID for components
    BASE_COMPONENT_ID = 3167729
    # Iterate through components to ensure proper structure and assign default IDs/names
    for i, component in enumerate(data["components"]):
        if "id" not in component:
            component["id"] = BASE_COMPONENT_ID + i
        if "name" not in component:
            component["name"] = f"Component_{i+1}"
        # Ensure "attributes" field exists within each component and is a list
        if "attributes" not in component or not isinstance(component["attributes"], list):
            component["attributes"] = []

        # Iterate through attributes within each component to ensure proper structure and assign default IDs/names/values
        for j, attribute in enumerate(component["attributes"]):
            if "id" not in attribute:
                attribute["id"] = j
            if "name" not in attribute:
                attribute["name"] = f"Attribute_{j+1}"
            if "value" not in attribute:
                attribute["value"] = ""

    # Get the current date for document entry
    current_date = datetime.now().strftime('%Y-%m-%d')
    # Construct the document path using the filename
    document_path = f"img/invoices/bodyinvoices/-/{filename}"

    # Ensure "documents" field exists, is a list, and contains at least one entry
    if "documents" not in data or not isinstance(data["documents"], list) or len(data["documents"]) == 0:
        # If missing or empty, create a default document entry
        data["documents"] = [{
            "date": current_date,
            "type": "Invoice",
            "path": document_path
        }]
    else:
        # If documents exist, ensure the first entry is a dictionary
        if not isinstance(data["documents"][0], dict):
            data["documents"][0] = {}
        # Update the date and path for the first document entry
        data["documents"][0]["date"] = current_date
        data["documents"][0]["path"] = document_path
        # Set default type to "Invoice" if missing or empty
        if "type" not in data["documents"][0] or not data["documents"][0]["type"]:
            data["documents"][0]["type"] = "Invoice"

    return data

def get_minimal_data_structure(filename: str) -> dict:
    # Get the current date for the document entry
    current_date = datetime.now().strftime('%Y-%m-%d')
    # Construct the document path using the filename
    document_path = f"img/invoices/bodyinvoices/-/{filename}"

    # Return a dictionary representing the minimal, standardized data structure
    return {
        "inventory_arrival_date": "",
        "stock_number": "",
        "vin": "",
        "condition": "New",  # Default condition
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