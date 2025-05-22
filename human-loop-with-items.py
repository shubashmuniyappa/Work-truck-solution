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

def parse_invoice_with_di(source: str, is_url: bool = True) -> dict:
    """
    Parses an invoice using Azure Document Intelligence's prebuilt-invoice model.
    """
    print(f"Sending '{source}' to Document Intelligence for analysis...")
    try:
        if is_url:
            poller = document_intelligence_client.begin_analyze_document(
                "prebuilt-invoice", AnalyzeDocumentRequest(url_source=source)
            )
        else:
            with open(source, "rb") as f:
                file_content = f.read()
            poller = document_intelligence_client.begin_analyze_document(
                "prebuilt-invoice",
                file_content,
                content_type=get_content_type(source)
            )

        result: AnalyzeResult = poller.result()
        print("Analysis complete.")

        extracted_data = {}
        highest_confidence_for_review = 1.0
        scalar_fields_processed = 0

        if result.documents:
            invoice = result.documents[0]
            for name, field in invoice.fields.items():
                field_value, field_confidence = extract_field_value(field)

                extracted_data[name] = {
                    "value": field_value,
                    "confidence": field_confidence
                }

                # Only consider confidence of top-level scalar types for overall_confidence check
                if field.value_string is not None or \
                   field.value_date is not None or \
                   field.value_number is not None or \
                   field.value_integer is not None or \
                   field.value_currency is not None or \
                   field.value_address is not None:
                    highest_confidence_for_review = min(highest_confidence_for_review, field_confidence)
                    scalar_fields_processed += 1

        else:
            print("No documents found in the analysis result.")
            highest_confidence_for_review = 0.0

        if scalar_fields_processed == 0 and result.documents:
            extracted_data["overall_confidence"] = 0.0
        else:
            extracted_data["overall_confidence"] = highest_confidence_for_review

        return extracted_data

    except Exception as e:
        print(f"An error occurred during Document Intelligence analysis: {e}")
        return {}

def get_content_type(file_path: str) -> str:
    """Determines the content type based on file extension for local files."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".pdf":
        return "application/pdf"
    elif extension == ".jpg" or extension == ".jpeg":
        return "image/jpeg"
    elif extension == ".png":
        return "image/png"
    else:
        print(f"Warning: Unsupported file type: {extension}. Using application/octet-stream. "
              "For best results, use .pdf, .jpg, or .png files.")
        return "application/octet-stream"

def human_review_interface(extracted_data: dict, invoice_id: str) -> dict:
    """
    Provides a basic command-line interface for human review and correction.
    """
    print(f"\n--- Human Review Interface for: {invoice_id} ---")
    print(f"Overall AI Confidence: {extracted_data.get('overall_confidence', 0.0):.2f}\n")

    corrected_data = extracted_data.copy()
    fields_to_review_count = 0

    for field_name, field_info in extracted_data.items():
        if field_name == "overall_confidence":
            continue

        current_value = field_info.get("value", "N/A")
        confidence = field_info.get("confidence", 0.0)

        # Handle complex fields (lists like 'Items')
        if isinstance(current_value, list):
            print(f"\n  Complex Field: {field_name.replace('_', ' ').title()} (contains {len(current_value)} items)")
            item_review_needed = False
            reviewed_items = []
            for i, item in enumerate(current_value):
                print(f"\n    --- Item {i+1} ---")
                reviewed_item = {}
                for sub_field_name, sub_field_info in item.items():
                    sub_value = sub_field_info.get("value", "N/A")
                    sub_confidence = sub_field_info.get("confidence", 0.0)

                    sub_field_needs_review = False
                    if sub_confidence < AI_CONFIDENCE_THRESHOLD:
                        sub_field_needs_review = True
                    elif sub_confidence == 0.0 and (sub_value is None or str(sub_value).strip() in ["", "N/A", "[]", "{}"]):
                        sub_field_needs_review = True

                    print(f"    Sub-Field: {sub_field_name.replace('_', ' ').title()}")
                    print(f"    AI Extracted Value: {sub_value}")
                    print(f"    Confidence: {sub_confidence:.2f}")

                    if sub_field_needs_review:
                        item_review_needed = True
                        print(f"    ---> Review required (low confidence or missing data). <---")
                        new_sub_value = input(f"    Enter corrected value (or press Enter to keep '{sub_value}'): ").strip()
                        if new_sub_value:
                            reviewed_item[sub_field_name] = {"value": new_sub_value, "confidence": 1.0}
                        else:
                            reviewed_item[sub_field_name] = sub_field_info
                    else:
                        reviewed_item[sub_field_name] = sub_field_info
                reviewed_items.append(reviewed_item)
                print("    ------------")

            corrected_data[field_name]["value"] = reviewed_items
            if item_review_needed:
                fields_to_review_count += 1
                print(f"\n  ---> Review completed for {field_name.replace('_', ' ').title()}. <---")
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
            print(f"  Field: {field_name.replace('_', ' ').title()}")
            print(f"  AI Extracted Value: {current_value}")
            print(f"  Confidence: {confidence:.2f}")
            print(f"  ---> Review required (low confidence or missing data). <---")

            new_value = input(f"  Enter corrected value (or press Enter to keep '{current_value}'): ").strip()
            if new_value:
                corrected_data[field_name]["value"] = new_value
                corrected_data[field_name]["confidence"] = 1.0
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
    safe_identifier = "".join(c for c in identifier if c.isalnum() or c in (' ', '.', '_')).rstrip()
    safe_identifier = safe_identifier.replace(" ", "_")
    safe_identifier = safe_identifier[:50]

    output_file_path = os.path.join(output_dir, f"{safe_identifier}_{status}.json")

    final_output_data = {}
    for k, v in data.items():
        if k == "overall_confidence":
            continue # Skip overall_confidence from output

        # If it's a field dict with 'value' and 'confidence', just take the 'value'
        if isinstance(v, dict) and 'value' in v:
            # Handle nested lists (like 'Items') recursively to strip confidence
            if isinstance(v['value'], list):
                simplified_list = []
                for item in v['value']:
                    if isinstance(item, dict):
                        simplified_item = {ik: iv['value'] if isinstance(iv, dict) and 'value' in iv else iv
                                           for ik, iv in item.items()}
                        simplified_list.append(simplified_item)
                    else:
                        simplified_list.append(item)
                final_output_data[k] = simplified_list
            # Handle nested objects (if any) recursively to strip confidence
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
    invoice_source = input("Enter the path to your local invoice file (e.g., invoice.pdf or image.jpg): ").strip()
    is_url = False
    invoice_identifier = os.path.basename(invoice_source)

    if not os.path.exists(invoice_source):
        print(f"Error: Local file not found at '{invoice_source}'")
        exit(1)

    extracted_invoice_data = parse_invoice_with_di(invoice_source, is_url=is_url)

    if extracted_invoice_data:
        overall_confidence = extracted_invoice_data.get("overall_confidence", 0.0)

        if overall_confidence < AI_CONFIDENCE_THRESHOLD:
            print("\n--- AI Confidence is LOW, human review recommended ---")
            validated_data = human_review_interface(extracted_invoice_data, invoice_identifier)
            # overall_confidence is for internal logic, doesn't need to be 1.0 in validated_data for saving,
            # as it's skipped in save_extracted_data anyway.
            # But keeping it here for consistency if future logic might use it.
            validated_data["overall_confidence"] = 1.0
            save_extracted_data(validated_data, "processed_invoices", invoice_identifier, "validated")
        else:
            print("\n--- AI Confidence is HIGH, no human review needed ---")
            save_extracted_data(extracted_invoice_data, "processed_invoices", invoice_identifier, "auto_processed")
    else:
        print("Invoice parsing failed. No data to process or review.")