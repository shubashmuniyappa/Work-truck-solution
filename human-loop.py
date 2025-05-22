import os
import json
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult

# --- Configuration ---
load_dotenv() # Load environment variables from .env file

DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
DOCUMENT_INTELLIGENCE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
AI_CONFIDENCE_THRESHOLD = 0.75 # Adjust this threshold as needed (e.g., 0.75 for 75%)

# Ensure credentials are loaded
if not DOCUMENT_INTELLIGENCE_ENDPOINT or not DOCUMENT_INTELLIGENCE_KEY:
    print("Error: Missing Document Intelligence endpoint or key. Please ensure your .env file is correct and loaded.")
    exit(1) # Exit if credentials are not found

document_intelligence_client = DocumentIntelligenceClient(
    endpoint=DOCUMENT_INTELLIGENCE_ENDPOINT,
    credential=AzureKeyCredential(DOCUMENT_INTELLIGENCE_KEY)
)

def parse_invoice_with_di(source: str, is_url: bool = True) -> dict:
    """
    Parses an invoice using Azure Document Intelligence's prebuilt-invoice model.

    Args:
        source (str): The URL or local file path to the invoice.
        is_url (bool): True if source is a URL, False if it's a local file path.

    Returns:
        dict: A dictionary containing extracted data and confidence scores,
              or an empty dictionary if parsing fails.
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
                content_type=get_content_type(source) # Helper for local file types
            )

        result: AnalyzeResult = poller.result()
        print("Analysis complete.")

        extracted_data = {}
        highest_confidence_for_review = 1.0
        scalar_fields_processed = 0

        if result.documents:
            invoice = result.documents[0]
            for name, field in invoice.fields.items():
                field_confidence = field.confidence if field.confidence is not None else 0.0

                field_value = None
                if field.value_string is not None:
                    field_value = field.value_string
                    highest_confidence_for_review = min(highest_confidence_for_review, field_confidence)
                    scalar_fields_processed += 1
                elif field.value_date is not None:
                    field_value = str(field.value_date)
                    highest_confidence_for_review = min(highest_confidence_for_review, field_confidence)
                    scalar_fields_processed += 1
                elif field.value_number is not None:
                    field_value = str(field.value_number)
                    highest_confidence_for_review = min(highest_confidence_for_review, field_confidence)
                    scalar_fields_processed += 1
                elif field.value_integer is not None:
                    field_value = str(field.value_integer)
                    highest_confidence_for_review = min(highest_confidence_for_review, field_confidence)
                    scalar_fields_processed += 1
                elif field.value_currency is not None:
                    if field.value_currency.amount is not None:
                        currency_symbol = getattr(field.value_currency, 'symbol', '')
                        field_value = f"{field.value_currency.amount} {currency_symbol}".strip()
                        highest_confidence_for_review = min(highest_confidence_for_review, field_confidence)
                        scalar_fields_processed += 1
                    else:
                        field_value = field.content
                elif field.value_address is not None:
                    field_value = getattr(field.value_address, 'content', '')
                    highest_confidence_for_review = min(highest_confidence_for_review, field_confidence)
                    scalar_fields_processed += 1
                elif field.value_array is not None:
                    field_value = f"[{len(field.value_array)} items]" if field.value_array else "[]"
                elif field.value_object is not None:
                    field_value = f"{{object_with_{len(field.value_object)} fields}}" if field.value_object else "{}"
                else:
                    field_value = field.content
                    highest_confidence_for_review = min(highest_confidence_for_review, field_confidence)
                    scalar_fields_processed += 1


                extracted_data[name] = {
                    "value": field_value,
                    "confidence": field_confidence
                }
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
    Provides a basic command-line interface for human review and correction,
    prompting for fields below the AI_CONFIDENCE_THRESHOLD or fields that are missing/empty.

    Args:
        extracted_data (dict): The data extracted by Document Intelligence.
        invoice_id (str): A unique identifier for the invoice (e.g., filename or URL).

    Returns:
        dict: The corrected/validated data.
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

        # Determine if field needs review:
        # 1. Confidence is below threshold
        # 2. Confidence is 0 AND the value is effectively empty/missing (for scalar fields)
        needs_review = False
        if confidence < AI_CONFIDENCE_THRESHOLD:
            needs_review = True
        elif confidence == 0.0 and (current_value is None or str(current_value).strip() in ["", "N/A", "[]", "{}"]):
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
                corrected_data[field_name]["confidence"] = 1.0 # Human validated, so confidence is high
            print("-" * 40)

    if fields_to_review_count == 0:
        print("All individual fields meet the confidence threshold or are acceptably populated. No specific fields require review.")
    print("\n--- Review Complete ---")
    return corrected_data

def save_extracted_data(data: dict, output_dir: str, identifier: str, status: str):
    """
    Saves the extracted or validated data to a JSON file.
    """
    os.makedirs(output_dir, exist_ok=True)
    safe_identifier = "".join(c for c in identifier if c.isalnum() or c in (' ', '.', '_')).rstrip()
    safe_identifier = safe_identifier.replace(" ", "_")
    safe_identifier = safe_identifier[:50]

    output_file_path = os.path.join(output_dir, f"{safe_identifier}_{status}.json")

    simplified_data = {}
    for k, v in data.items():
        if k == "overall_confidence":
            simplified_data[k] = v
        else:
            simplified_data[k] = v.get('value')

    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(simplified_data, f, indent=4, ensure_ascii=False)
    print(f"Saved {status} data to: {output_file_path}")


if __name__ == "__main__":
    # --- CHANGE START ---
    invoice_source = input("Enter the path to your local invoice file (e.g., invoice.pdf or image.jpg): ").strip()
    is_url = False
    invoice_identifier = os.path.basename(invoice_source) # Use the filename as identifier

    if not os.path.exists(invoice_source):
        print(f"Error: Local file not found at '{invoice_source}'")
        exit(1)
    # --- CHANGE END ---

    extracted_invoice_data = parse_invoice_with_di(invoice_source, is_url=is_url)

    if extracted_invoice_data:
        overall_confidence = extracted_invoice_data.get("overall_confidence", 0.0)

        # This is the main check for human review (overall confidence based on scalar fields)
        if overall_confidence < AI_CONFIDENCE_THRESHOLD:
            print("\n--- AI Confidence is LOW, human review recommended ---")
            validated_data = human_review_interface(extracted_invoice_data, invoice_identifier)
            validated_data["overall_confidence"] = 1.0 # Reflect human validation
            save_extracted_data(validated_data, "processed_invoices", invoice_identifier, "validated")
        else:
            print("\n--- AI Confidence is HIGH, no human review needed ---")
            # For auto-processed documents, we still want to save the AI's extraction
            save_extracted_data(extracted_invoice_data, "processed_invoices", invoice_identifier, "auto_processed")
    else:
        print("Invoice parsing failed. No data to process or review.")