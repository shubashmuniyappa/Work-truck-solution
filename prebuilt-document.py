import os
import json
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult

# --- Configuration ---
load_dotenv()

DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
DOCUMENT_INTELLIGENCE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
AI_CONFIDENCE_THRESHOLD = 0.75 # Adjust this threshold as needed (e.g., 0.75 for 75%)

# --- Hardcoded Invoice URL ---
HARCODED_INVOICE_URL = "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-ae96c1bb-2724-4206-9e73-4ce4724b685a.pdf"

# Ensure credentials are loaded
if not DOCUMENT_INTELLIGENCE_ENDPOINT or not DOCUMENT_INTELLIGENCE_KEY:
    print("Error: Missing Document Intelligence endpoint or key. Please ensure your .env file is correct and loaded.")
    exit(1)

document_intelligence_client = DocumentIntelligenceClient(
    endpoint=DOCUMENT_INTELLIGENCE_ENDPOINT,
    credential=AzureKeyCredential(DOCUMENT_INTELLIGENCE_KEY)
)

def extract_field_value(field):
    """Recursively extracts the value and confidence from a Document Intelligence Field object."""
    field_value = None
    field_confidence = field.confidence if field.confidence is not None else 0.0

    if field.value_string is not None:
        field_value = field.value_string
    elif field.value_date is not None:
        field_value = str(field.value_date)
    elif field.value_number is not None:
        field_value = str(field.value_number)
    elif field.value_integer is not None:
        field_value = str(field.value_integer)
    elif field.value_currency is not None:
        if field.value_currency.amount is not None:
            currency_symbol = getattr(field.value_currency, 'symbol', '')
            field_value = f"{field.value_currency.amount} {currency_symbol}".strip()
        else:
            field_value = field.content # Fallback if amount not present
    elif field.value_address is not None:
        field_value = getattr(field.value_address, 'content', '')
    elif field.value_array is not None:
        items_list = []
        for item_field in field.value_array:
            if item_field.value_object:
                item_details = {}
                for sub_field_name, sub_field in item_field.value_object.items():
                    sub_value, sub_confidence = extract_field_value(sub_field)
                    item_details[sub_field_name] = {"value": sub_value, "confidence": sub_confidence}
                items_list.append(item_details)
        field_value = items_list
    elif field.value_object is not None:
        object_details = {}
        for sub_field_name, sub_field in field.value_object.items():
            sub_value, sub_confidence = extract_field_value(sub_field)
            object_details[sub_field_name] = {"value": sub_value, "confidence": sub_confidence}
        field_value = object_details
    else:
        field_value = field.content

    return field_value, field_confidence

def parse_invoice_with_di(source_url: str) -> dict:
    """
    Parses a document from a URL using Azure Document Intelligence's general document model.
    """
    # Use the correct model ID for the general document model (specifying API version)
    # 'prebuilt-2023-07-31' is the generally recommended stable version for general documents.
    # If you're on a very new SDK version and need cutting-edge features, 'prebuilt-2024-02-29-preview'
    # might also be an option, but stick to stable for production.
    general_document_model_id = "prebuilt-document" 

    print(f"Sending '{source_url}' to Document Intelligence for analysis using model '{general_document_model_id}'...")
    try:
        poller = document_intelligence_client.begin_analyze_document(
            general_document_model_id, AnalyzeDocumentRequest(url_source=source_url)
        )
        result: AnalyzeResult = poller.result()
        print("Analysis complete.")

        extracted_data = {}
        overall_confidence = 1.0 # Initialize with high confidence

        if result.documents:
            document = result.documents[0]
            # The general document model populates 'fields' for extracted key-value pairs
            # and other high-level entities.
            for name, field in document.fields.items():
                field_value, field_confidence = extract_field_value(field)

                extracted_data[name] = {
                    "value": field_value,
                    "confidence": field_confidence
                }
                overall_confidence = min(overall_confidence, field_confidence)

            # The general document model also provides raw key-value pairs which might be more granular
            # You might want to process these as well, especially if your target fields are not directly
            # extracted into `document.fields`.
            if hasattr(document, 'key_value_pairs') and document.key_value_pairs:
                for kvp in document.key_value_pairs:
                    # Key-value pairs provide content directly on the key/value objects
                    key_content = kvp.key.content if kvp.key else "N/A"
                    value_content = kvp.value.content if kvp.value else "N/A"
                    kvp_confidence = kvp.confidence if kvp.confidence is not None else 0.0

                    # You can choose to add these to your extracted_data, perhaps with a prefix
                    extracted_data[f"raw_kvp_{key_content.replace(' ', '_').lower()}"] = {"value": value_content, "confidence": kvp_confidence}
                    overall_confidence = min(overall_confidence, kvp_confidence)

            # And also tables
            if hasattr(result, 'tables') and result.tables:
                extracted_data["tables"] = []
                for table_idx, table in enumerate(result.tables):
                    table_data = []
                    for cell in table.cells:
                        # You'll need more sophisticated logic to reconstruct rows/columns from cells
                        # based on their row_index and column_index. For simplicity here, just storing content.
                        table_data.append({
                            "content": cell.content,
                            "row_index": cell.row_index,
                            "column_index": cell.column_index,
                            "confidence": cell.confidence
                        })
                    extracted_data["tables"].append(table_data)
                    # Confidence for tables can be tricky; you might average cell confidences
                    # or set a default high if the table structure is well-detected.
                    overall_confidence = min(overall_confidence, table.confidence if table.confidence is not None else 1.0)


        else:
            print("No documents found in the analysis result.")
            overall_confidence = 0.0

        extracted_data["overall_confidence"] = overall_confidence
        return extracted_data

    except Exception as e:
        print(f"An error occurred during Document Intelligence analysis: {e}")
        return {"error": str(e)}

def human_review_interface(extracted_data: dict, invoice_id: str) -> dict:
    """
    Provides a command-line interface for human review and correction.
    """
    print(f"\n--- Human Review Interface for Invoice: {invoice_id} ---")
    print(f"Overall AI Confidence: {extracted_data.get('overall_confidence', 0.0):.2f}\n")

    corrected_data = extracted_data.copy()
    fields_to_review_count = 0

    for field_name, field_info in extracted_data.items():
        if field_name == "overall_confidence":
            continue

        # Skip tables and raw_kvp if you only want to review main fields.
        # You might want to build a separate review process for tables or granular KVP.
        if field_name == "tables" or field_name.startswith("raw_kvp_"):
            continue

        current_value = field_info.get("value", "N/A")
        confidence = field_info.get("confidence", 0.0)

        # Handle complex fields (lists) like 'Items' from prebuilt-invoice.
        # 'prebuilt-document' generally returns simpler fields, but if you have nested
        # structures labeled in a custom model, this part would still apply.
        if isinstance(current_value, list) and field_name != "tables": # Exclude 'tables' list from this generic review
            print(f"\n   Complex Field: {field_name.replace('_', ' ').title()} (contains {len(current_value)} items)")
            item_review_needed = False
            reviewed_items = []
            for i, item in enumerate(current_value):
                print(f"\n     --- Item {i+1} ---")
                reviewed_item = {}
                for sub_field_name, sub_field_info in item.items():
                    sub_value = sub_field_info.get("value", "N/A")
                    sub_confidence = sub_field_info.get("confidence", 0.0)

                    sub_field_needs_review = False
                    if sub_confidence < AI_CONFIDENCE_THRESHOLD:
                        sub_field_needs_review = True
                    elif sub_confidence == 0.0 and (sub_value is None or str(sub_value).strip() in ["", "N/A", "[]", "{}"]):
                        sub_field_needs_review = True

                    print(f"     Sub-Field: {sub_field_name.replace('_', ' ').title()}")
                    print(f"     AI Extracted Value: {sub_value}")
                    print(f"     Confidence: {sub_confidence:.2f}")

                    if sub_field_needs_review:
                        item_review_needed = True
                        print(f"     ---> Review required (low confidence or missing data). <---")
                        new_sub_value = input(f"     Enter corrected value (or press Enter to keep '{sub_value}'): ").strip()
                        if new_sub_value:
                            reviewed_item[sub_field_name] = {"value": new_sub_value, "confidence": 1.0}
                        else:
                            reviewed_item[sub_field_name] = sub_field_info
                    else:
                        reviewed_item[sub_field_name] = sub_field_info
                reviewed_items.append(reviewed_item)
                print("     ------------")

            corrected_data[field_name]["value"] = reviewed_items
            if item_review_needed:
                fields_to_review_count += 1
                print(f"\n   ---> Review completed for {field_name.replace('_', ' ').title()}. <---")
            print("-" * 40)
            continue

        # Handles non-array fields (scalar or object types that are not arrays)
        needs_review = False
        if confidence < AI_CONFIDENCE_THRESHOLD:
            needs_review = True
        elif confidence == 0.0 and (current_value is None or str(current_value).strip() in ["", "N/A", "{}"]):
            needs_review = True

        if needs_review:
            fields_to_review_count += 1
            print(f"   Field: {field_name.replace('_', ' ').title()}")
            print(f"   AI Extracted Value: {current_value}")
            print(f"   Confidence: {confidence:.2f}")
            print(f"   ---> Review required (low confidence or missing data). <---")

            new_value = input(f"   Enter corrected value (or press Enter to keep '{current_value}'): ").strip()
            if new_value:
                corrected_data[field_name]["value"] = new_value
                corrected_data[field_name]["confidence"] = 1.0 # Mark as human-validated
            print("-" * 40)

    if fields_to_review_count == 0:
        print("All individual fields meet the confidence threshold or are acceptably populated. No specific fields require review.")
    print("\n--- Review Complete ---")
    return corrected_data

def save_extracted_data(data: dict, output_dir: str, identifier: str, status: str):
    """
    Saves the extracted or validated data to a JSON file, WITHOUT confidence values.
    """
    os.makedirs(output_dir, exist_ok=True)
    # Create a safe filename from the URL, removing special characters and limiting length
    safe_identifier = os.path.basename(identifier).split('?')[0] # remove query params if any
    safe_identifier = "".join(c for c in safe_identifier if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
    safe_identifier = safe_identifier.replace(" ", "_")
    safe_identifier = safe_identifier[:100].strip('_') # Limit length and clean trailing underscores

    output_file_path = os.path.join(output_dir, f"{safe_identifier}_{status}.json")

    final_output_data = {}
    for k, v in data.items():
        if k == "overall_confidence":
            continue # Skip overall_confidence from final output

        # If it's a field dict with 'value' and 'confidence', just take the 'value'
        if isinstance(v, dict) and 'value' in v:
            # Handle nested lists (like 'Items') recursively to strip confidence
            if isinstance(v['value'], list):
                simplified_list = []
                for item in v['value']:
                    if isinstance(item, dict):
                        # Ensure to handle potentially deeply nested structures if they exist
                        simplified_item = {ik: iv['value'] if isinstance(iv, dict) and 'value' in iv else iv
                                           for ik, iv in item.items()}
                        simplified_list.append(simplified_item)
                    else:
                        simplified_list.append(item)
                final_output_data[k] = simplified_list
            # Handle nested objects recursively to strip confidence
            elif isinstance(v['value'], dict):
                simplified_object = {ik: iv['value'] if isinstance(iv, dict) and 'value' in iv else iv
                                     for ik, iv in v['value'].items()}
                final_output_data[k] = simplified_object
            else:
                final_output_data[k] = v['value']
        else:
            final_output_data[k] = v # Fallback for any other structure


    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(final_output_data, f, indent=4, ensure_ascii=False)
    print(f"Saved {status} data to: {output_file_path}")


if __name__ == "__main__":
    invoice_identifier = os.path.basename(HARCODED_INVOICE_URL) # Use URL filename as identifier
    extracted_invoice_data = parse_invoice_with_di(HARCODED_INVOICE_URL)

    if extracted_invoice_data and "error" not in extracted_invoice_data:
        overall_confidence = extracted_invoice_data.get("overall_confidence", 0.0)

        # Check if human review is required based on overall confidence
        if overall_confidence < AI_CONFIDENCE_THRESHOLD:
            print("\n--- AI Confidence is LOW, human review recommended ---")
            validated_data = human_review_interface(extracted_invoice_data, invoice_identifier)
            # Set overall_confidence to 1.0 for validated data
            validated_data["overall_confidence"] = 1.0
            save_extracted_data(validated_data, "processed_invoices", invoice_identifier, "validated")
        else:
            print("\n--- AI Confidence is HIGH, no human review needed ---")
            save_extracted_data(extracted_invoice_data, "processed_invoices", invoice_identifier, "auto_processed")
    else:
        print("Invoice parsing failed. No data to process or review.")