import os
import json
import requests
import tempfile
from urllib.parse import urlparse
import streamlit as st
from openai import AzureOpenAI  # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader  # type: ignore
from pydantic import BaseModel, Field, conlist # For better structured data validation and handling

# --- Configuration ---
DOCINTELLIGENCE_ENDPOINT = "https://quaddocintelligence1.cognitiveservices.azure.com/"
DOCINTELLIGENCE_KEY = "53uBovu34ZLs4HFKjFo3nW3qDUh8utA0gBY3Q8BlcjpTkPmefnBWJQQJ99BEACYeBjFXJ3w3AAALACOGSie3"

OPENAI_ENDPOINT = "https://nikhi-mb4qln04-swedencentral.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
OPENAI_DEPLOYMENT = "gpt-4o"
OPENAI_API_KEY = "4prHi16lJv4qDEATOl11M4f99KCcnntffozdHXm2Umfq8t3KeWVJJQQJ99BEACfhMk5XJ3w3AAAAACOGEJ7N"
OPENAI_API_VERSION = "2025-01-01-preview"

# ADI analysis features
ADI_ANALYSIS_FEATURES = ["ocrHighResolution"]

# Confidence Threshold for Human Review
CONFIDENCE_THRESHOLD = 0.80 # 80%

# Initialize Azure OpenAI Client
openai_client = AzureOpenAI(
    api_version=OPENAI_API_VERSION,
    azure_endpoint=OPENAI_ENDPOINT,
    api_key=OPENAI_API_KEY,
)

# --- Define Pydantic Models for Structured Output (Optional but highly recommended) ---
# This helps ensure the JSON structure is consistent and can be validated.
class Item(BaseModel):
    description: str = ""
    amount: str = ""

class InvoiceData(BaseModel):
    invoice_number: str = ""
    bill_to: str = ""
    ship_to: str = ""
    vin: str = ""
    distributor: str = ""
    make: str = ""
    model: str = ""
    year: str = ""
    invoice_date: str = ""
    list_of_items: conlist(Item) = Field(default_factory=list) # List of Item models
    total_amount: float = 0.0
    file_path: str = ""
    
    # Fields to store confidence for human review (not part of original output JSON)
    # These will be populated by the ADI results
    confidence_scores: dict = Field(default_factory=dict)
    needs_review: dict = Field(default_factory=dict) # Flag for human review
    error: str = "" # Added to explicitly store error messages if processing fails

# --- Utility Functions ---
def get_filename_from_url(url: str) -> str:
    """Extracts filename from a URL."""
    return os.path.basename(urlparse(url).path)

def get_relative_path_from_url(url: str) -> str:
    """Extracts the relative path starting from 'img/' from a URL."""
    parsed_url = urlparse(url)
    path_segments = parsed_url.path.split('/')
    try:
        img_index = path_segments.index('img')
        relative_path = '/'.join(path_segments[img_index:])
        return relative_path
    except ValueError:
        return parsed_url.path.lstrip('/')

def download_file(url: str) -> str:
    """Downloads a file from a URL to a temporary location."""
    response = requests.get(url, stream=True)
    response.raise_for_status() # Raise an exception for bad status codes
    
    suffix = os.path.splitext(get_filename_from_url(url))[-1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk)
    return tmp.name

# --- Document Intelligence and LLM Extraction ---

def extract_document_data(file_path: str):
    """
    Loads document using Azure AIDocumentIntelligenceLoader, extracts full text,
    and returns raw ADI analysis results including confidence scores.
    """
    loader = AzureAIDocumentIntelligenceLoader(
        api_endpoint=DOCINTELLIGENCE_ENDPOINT,
        api_key=DOCINTELLIGENCE_KEY,
        file_path=file_path,
        api_model="prebuilt-invoice",
        mode="page", # Keep "page" mode to get content per page for full text
        analysis_features=ADI_ANALYSIS_FEATURES,
    )
    documents = loader.load()

    full_text = "\n\n".join([doc.page_content for doc in documents])
    
    # The raw_results contain the structured fields and confidence scores
    # This assumes all pages are part of one invoice, and we'll take the first invoice result.
    # For a simple prebuilt-invoice model, the main results are typically in documents[0].metadata['invoice_pages'][0]['invoices'][0]
    raw_adi_invoice_data = {}
    if documents and 'invoice_pages' in documents[0].metadata and documents[0].metadata['invoice_pages']:
        if documents[0].metadata['invoice_pages'][0]['invoices']:
            raw_adi_invoice_data = documents[0].metadata['invoice_pages'][0]['invoices'][0]

    return full_text, raw_adi_invoice_data

def extract_invoice_json_llm(text: str) -> dict:
    """Uses Azure OpenAI (LLM) to extract structured invoice data."""
    system_prompt = """
    You are an intelligent and detail-oriented assistant specialized in vehicle inventory data extraction from single-invoice documents.
    Your primary goal is to accurately extract structured information and present it in a JSON format.

    For each field, **if the information is not explicitly and clearly found in the document, leave the string fields empty ("") and numerical fields as 0.0, unless specific fallback rules are provided.** Do not invent or infer values.

    The required JSON format is as follows:
    {
      "invoice_number": "",
      "bill_to": "",
      "ship_to": "",
      "vin": "",
      "distributor": "",
      "make": "",
      "model": "",
      "year": "",
      "invoice_date": "",
      "list_of_items": [
        {
          "description": "",
          "amount": ""
        }
      ],
      "total_amount": 0.0
    }
    
    NOTE: The "file_path" field is handled by the system and should NOT be included in your JSON output.

    Here are the detailed extraction guidelines for each field:

    - **invoice_number**:
        - Look for keywords like "invoice", "invoice no", "invoice #".
        - Extract the value immediately following these keywords.
        - If not present, leave empty ("").

    - **bill_to**:
        - Look for keywords like "bill to", "sold to".
        - Extract the *entire* associated address block, including name, street, city, state, zip, etc. Do not exclude any lines or parts of the address.
        - If not present, leave empty ("").

    - **ship_to**:
        - Look for keywords like "ship to", "deliver to".
        - Extract the *entire* associated address block, including name, street, city, state, zip, etc. Do not exclude any lines or parts of the address.
        - **IMPORTANT FALLBACK**: If "ship to" or "deliver to" information is explicitly not found, use the *exact content* extracted for "bill_to" as the value for "ship_to".

    - **vin**:
        - Extract the Vehicle Identification Number (VIN). A VIN is typically 17 characters long, consisting of letters and numbers.
        - If not present, leave empty ("").

    - **distributor**:
        - Identify the name of the entity that issued the invoice. This can often be found in the invoice heading, logo area, or near "brokerage".
        - If not clearly identifiable, leave empty ("").

    - **make**:
        - Look for the **explicit keyword** "make" followed by a brand name (e.g., "Make: Ford").
        - Alternatively, identify a prominent car manufacturer's name in the document (e.g., "Chevrolet", "Toyota").
        - **If no clear "make" keyword or distinct car manufacturer name is found, leave this field empty (""). Do NOT use codes, model numbers, or general vehicle types as the make.**

    - **model**:
        - Look for the **explicit keyword** "model" followed by a model name or number (e.g., "Model: F-150").
        - **If no clear "model" keyword is found, leave this field empty (""). Do NOT use other descriptive text or partial product codes as the model.**

    - **year**:
        - Look for the **explicit keyword** "year".
        - If "year" keyword is not present, extract a four-digit year from the "invoice_date".
        - If neither is found, leave empty ("").

    - **invoice_date**:
        - Look for keywords like "date", "invoice date".
        - Extract the full date.
        - If not present, leave empty ("").

    - **list_of_items**:
        - Extract all individual line items and any *grouped* items from the invoice.
        - Each entry in `list_of_items` must have a "description" and an "amount".
        - **Handling Grouped Items with a Single Amount**:
            - If multiple descriptive lines or components are clearly grouped together visually (e.g., indented, listed under a common heading, or followed by a single amount that applies to all of them), combine their descriptions into a single string for the "description" field. Use a semicolon and a space (`; `) to separate concatenated elements within this description.
            - Associate the single, explicitly stated total amount for that entire group with this combined description. Do NOT perform any arithmetic summation; extract the amount exactly as it appears.
        - **Handling Individual Items**: For items that are not part of a visible group, extract their specific "description" and "amount".
        - **Handling Missing Individual Amounts (for non-grouped items)**: If an individual item's amount is *not explicitly present* or clearly associated with it, set its "amount" field to an empty string ("").
        - Ensure all relevant descriptions are captured, whether they are individual or part of a group.

    - **total_amount**:
        - Look for keywords like "total", "total amount", "grand total", "balance due".
        - Extract the final numerical total amount of the invoice.
        - If not present, default to 0.0.

    - Extract clean text (no trailing whitespace or labels).
    - Ensure the output strictly adheres to the JSON structure and field names specified above.
    - Be very precise and thorough in extracting all available information based on these guidelines.
    """

    response = openai_client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract the information from the following document text:\n\n{text}"},
        ],
        max_tokens=5000,
        temperature=0.0,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        model=OPENAI_DEPLOYMENT,
    )

    content = response.choices[0].message.content
    cleaned = content.strip().strip("```").replace("json", "", 1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        st.error(f"LLM JSON parsing failed: {cleaned}")
        return {"error": "JSON parsing failed", "raw_response": cleaned}

def map_adi_to_llm_fields(adi_data: dict) -> tuple[dict, dict]:
    """
    Maps relevant ADI extracted fields to our target LLM JSON structure,
    including their confidence scores.
    """
    mapped_data = {}
    confidence_scores = {}

    # Define a mapping from ADI field names to our desired JSON field names
    # and their default values if not found or low confidence
    field_mapping = {
        "InvoiceId": "invoice_number",
        "BillTo": "bill_to",
        "ShipTo": "ship_to",
        "VendorName": "distributor", # ADI often calls this VendorName
        "CustomerName": "bill_to", # Could be an alternative for bill_to
        "CustomerAddress": "bill_to", # Often contains full bill_to address
        "InvoiceDate": "invoice_date",
        "Total": "total_amount",
        # VIN, Make, Model, Year, list_of_items are less reliably extracted
        # by ADI prebuilt for all document types, or confidence might be low.
        # We'll rely on LLM for these primarily, or combine.
    }

    # Extract top-level fields
    for adi_field, target_field in field_mapping.items():
        if adi_field in adi_data and adi_data[adi_field] and 'value' in adi_data[adi_field] and adi_data[adi_field]['value'] is not None:
            value = adi_data[adi_field]['value']
            confidence = adi_data[adi_field].get('confidence', 0.0)
            
            # Special handling for addresses: ADI often gives structured address objects
            if target_field in ["bill_to", "ship_to"]:
                if isinstance(value, dict) and 'content' in value:
                    mapped_data[target_field] = value['content']
                elif isinstance(value, str):
                    mapped_data[target_field] = value
                else:
                    mapped_data[target_field] = "" # Fallback for unexpected format
            elif target_field == "total_amount":
                 # ADI might return total as a string or number, try to convert to float
                 try:
                     mapped_data[target_field] = float(value)
                 except (ValueError, TypeError):
                     mapped_data[target_field] = 0.0
            else:
                mapped_data[target_field] = str(value)
            
            confidence_scores[target_field] = confidence
        else:
            mapped_data[target_field] = "" if target_field != "total_amount" else 0.0
            confidence_scores[target_field] = 0.0 # No value, no confidence

    # Handle list_of_items (ADI's LineItems)
    mapped_data['list_of_items'] = []
    if 'LineItems' in adi_data and adi_data['LineItems'] and adi_data['LineItems']['value']:
        item_confidences = []
        for adi_item in adi_data['LineItems']['value']:
            desc = adi_item.get('description', {}).get('value', '')
            amount = adi_item.get('amount', {}).get('value', '')
            
            # ADI item confidence applies to the whole item
            item_confidence = adi_item.get('confidence', 0.0)
            mapped_data['list_of_items'].append(Item(description=desc, amount=str(amount)))
            item_confidences.append(item_confidence)
        
        # Store average or lowest item confidence for review purposes
        if item_confidences:
            confidence_scores['list_of_items'] = sum(item_confidences) / len(item_confidences)
        else:
            confidence_scores['list_of_items'] = 0.0
    else:
        confidence_scores['list_of_items'] = 0.0

    return mapped_data, confidence_scores

def process_invoice(url: str):
    """Processes a single invoice URL, combining ADI and LLM extraction."""
    st.write(f"**Processing:** {url}")
    relative_file_path = get_relative_path_from_url(url)
    local_file = None
    try:
        local_file = download_file(url)
        full_text, adi_raw_data = extract_document_data(local_file)
        
        # Extract initial data and confidence from ADI (prebuilt model)
        adi_extracted_data, adi_confidence_scores = map_adi_to_llm_fields(adi_raw_data)
        
        # Use LLM for more complex parsing, especially for items, make, model, vin
        # (LLM doesn't give confidence per field, so we assume 1.0 for fields it populates)
        llm_extracted_data = extract_invoice_json_llm(full_text)
        
        # Initialize with Pydantic model defaults
        final_invoice_data = InvoiceData(file_path=relative_file_path)
        
        needs_review = {}

        # Define fields to check for review
        # Include all fields from InvoiceData model's schema
        fields_to_check = InvoiceData.schema()['properties'].keys()
        
        for field in fields_to_check:
            # Skip internal fields of InvoiceData model that are not part of core extraction
            if field in ["file_path", "confidence_scores", "needs_review", "error"]:
                continue

            adi_value = adi_extracted_data.get(field)
            adi_conf = adi_confidence_scores.get(field, 0.0)
            llm_value = llm_extracted_data.get(field)

            if field == "list_of_items":
                # Prioritize LLM for list_of_items as it has more sophisticated grouping logic
                if llm_value:
                    try:
                        # Ensure LLM list_of_items are correctly parsed into Item models
                        final_invoice_data.list_of_items = [Item(**item) for item in llm_value]
                    except Exception as e:
                        st.warning(f"Failed to parse LLM list_of_items for {url}: {e}. Using empty list.")
                        final_invoice_data.list_of_items = []
                        needs_review[field] = True
                elif adi_extracted_data.get('list_of_items'): # Fallback to ADI if LLM fails
                    final_invoice_data.list_of_items = [Item(**item) for item in adi_extracted_data['list_of_items']]
                else:
                    final_invoice_data.list_of_items = []
                
                # Flag for review if LLM didn't get items OR ADI confidence was low AND LLM also didn't get items
                if not final_invoice_data.list_of_items or (adi_conf < CONFIDENCE_THRESHOLD and not final_invoice_data.list_of_items):
                    needs_review[field] = True
                else:
                    needs_review[field] = False
                
                # Use ADI confidence for flagging, as LLM doesn't provide it directly
                final_invoice_data.confidence_scores[field] = adi_conf 
                
            else: # For other simple fields
                # Check ADI first if high confidence and value exists
                if adi_conf >= CONFIDENCE_THRESHOLD and adi_value not in ["", 0.0, None]:
                    if field == "total_amount":
                        try:
                            setattr(final_invoice_data, field, float(adi_value))
                        except ValueError:
                            setattr(final_invoice_data, field, 0.0)
                            needs_review[field] = True # Flag if conversion failed
                    else:
                        setattr(final_invoice_data, field, adi_value)
                    needs_review[field] = False # ADI confident, no review needed
                    
                # Otherwise, if ADI not confident OR value missing, check LLM
                elif llm_value not in ["", 0.0, None]:
                    if field == "total_amount":
                        try:
                            setattr(final_invoice_data, field, float(llm_value))
                            # Set confidence to 1.0 if LLM successfully extracted a numerical total
                            final_invoice_data.confidence_scores[field] = 1.0 
                        except ValueError:
                            setattr(final_invoice_data, field, 0.0)
                            needs_review[field] = True # Flag if conversion failed
                            final_invoice_data.confidence_scores[field] = 0.0 # Confidence is 0 if it fails to convert
                    else:
                        setattr(final_invoice_data, field, llm_value)
                        # Assume LLM is confident if it provides a value
                        final_invoice_data.confidence_scores[field] = 1.0 
                    
                    # Flag for review if ADI was low/missing AND LLM provided a value
                    # OR if LLM provided value but ADI didn't exist for this field at all (meaning LLM is primary source)
                    needs_review[field] = True 
                else:
                    # If neither ADI (confidently) nor LLM has a value, it needs review
                    setattr(final_invoice_data, field, "" if field != "total_amount" else 0.0)
                    needs_review[field] = True
                    final_invoice_data.confidence_scores[field] = 0.0 # No value, no confidence

        final_invoice_data.needs_review = needs_review
        
        # --- MODIFICATION START ---
        output_dict = final_invoice_data.dict()
        # Remove the fields you don't want in the final output
        output_dict.pop("confidence_scores", None)
        output_dict.pop("needs_review", None)
        return output_dict
        # --- MODIFICATION END ---

    except Exception as e:
        st.error(f"Error processing {url}: {e}")
        # Initialize an empty InvoiceData model and then update only error and review flags
        error_data_model = InvoiceData(file_path=relative_file_path, error=str(e))
        # Flag all fields as needing review if there's a processing error
        error_data_model.needs_review = {
            field: True for field in error_data_model.schema()['properties'].keys() 
            if field not in ["file_path", "confidence_scores", "needs_review", "error"]
        }
        
        # --- MODIFICATION START ---
        error_output_dict = error_data_model.dict()
        error_output_dict.pop("confidence_scores", None)
        error_output_dict.pop("needs_review", None)
        return error_output_dict
        # --- MODIFICATION END ---
    finally:
        if local_file and os.path.exists(local_file):
            os.unlink(local_file)


# --- Streamlit Application ---
st.set_page_config(layout="wide", page_title="Invoice Review Application")

st.title("Invoice Data Extraction & Human Review")

# Hardcoded URLs for demonstration
DEMO_URLS =[
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-419bb7b3-26ef-487f-8319-0fb753b0b179.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-8ad73279-2a32-4f43-9167-bbe134ae9d50.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-4ce8b538-e524-4040-86b1-e6373c444d61.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-0c5eedf1-02b7-43f7-8082-eb1a058e3a44.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-c8ae41c4-0d29-48da-82ec-e7b84e9121b0.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-181b0e40-9822-4430-b92b-40a7a0a86a1f.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-bc0c8b1a-84a2-4cd6-a1d2-0a8cc7476580.pdf"
]

# State management for invoices to review
if 'invoices_to_review' not in st.session_state:
    st.session_state.invoices_to_review = []
if 'reviewed_invoices' not in st.session_state:
    st.session_state.reviewed_invoices = []
if 'current_invoice_idx' not in st.session_state:
    st.session_state.current_invoice_idx = 0

if st.button("Start Extraction and Review"):
    st.session_state.invoices_to_review = []
    st.session_state.reviewed_invoices = []
    st.session_state.current_invoice_idx = 0
    st.info("Starting extraction for all invoices...")
    for url in DEMO_URLS:
        processed_data = process_invoice(url)
        st.session_state.invoices_to_review.append(processed_data)
    st.success("Extraction complete. Ready for review!")

# Display current invoice for review
if st.session_state.invoices_to_review:
    if st.session_state.current_invoice_idx < len(st.session_state.invoices_to_review):
        current_invoice = st.session_state.invoices_to_review[st.session_state.current_invoice_idx]
        st.subheader(f"Review Invoice {st.session_state.current_invoice_idx + 1}/{len(st.session_state.invoices_to_review)}")
        st.markdown(f"**File Path:** `{current_invoice.get('file_path', 'N/A')}`")
        if current_invoice.get('error'):
            st.error(f"Error encountered for this invoice: {current_invoice['error']}")
            st.warning("Please review or skip this invoice.")
            # Provide skip/next buttons for error cases
            if st.button("Skip Invoice"):
                st.session_state.current_invoice_idx += 1
                st.rerun() 
        else:
            # Display PDF in an iframe (optional, but very helpful)
            st.markdown("---")
            st.markdown("### Original Invoice Document")
            # Using the direct image URL from Worktruck Solutions. Adjust if your image serving differs.
            st.markdown(f'<iframe src="{urlparse(current_invoice.get("file_path", ""))._replace(scheme="https", netloc="images.worktrucksolutions.com").geturl() if current_invoice.get("file_path") else ""}" width="800" height="600"></iframe>', unsafe_allow_html=True)
            st.markdown("---")

            # Display fields for human review
            st.markdown("### Extracted Data & Review")
            st.write("Fields highlighted in :red[red] either had low confidence or were not extracted and require attention.")

            form_key = f"invoice_form_{st.session_state.current_invoice_idx}"
            with st.form(key=form_key):
                # When presenting the form, we need to use the full `current_invoice` data,
                # including `confidence_scores` and `needs_review` to drive the UI.
                # So, we'll extract these from the `invoices_to_review` item directly.
                
                # These are extracted from the original processed data stored in session_state,
                # which *does* include confidence_scores and needs_review for UI logic.
                current_invoice_full = st.session_state.invoices_to_review[st.session_state.current_invoice_idx]
                
                updated_data = {}
                # Iterate through the fields defined in the Pydantic model for consistent ordering and display
                # excluding the internal tracking fields that are never displayed in the form
                fields_to_display = [f for f in InvoiceData.schema()['properties'].keys() if f not in ["file_path", "confidence_scores", "needs_review", "error"]]
                
                for field_name in fields_to_display:
                    field_value = current_invoice_full.get(field_name) 
                    needs_review = current_invoice_full.get('needs_review', {}).get(field_name, False)
                    confidence = current_invoice_full.get('confidence_scores', {}).get(field_name, 0.0)
                    
                    label_color = ":red" if needs_review else ""
                    label = f"{field_name.replace('_', ' ').title()} (Conf: {confidence:.2f})"
                    
                    if field_name == "list_of_items":
                        st.markdown(f"**{label_color}[{label}]**")
                        # Ensure the list of Item objects is correctly converted to a list of dicts for JSON dumping
                        # The session_state data for list_of_items will be a list of dicts already
                        current_items_for_json = field_value
                        current_items_str = json.dumps(current_items_for_json, indent=2)
                        
                        edited_items_str = st.text_area(
                            f"Edit {field_name}",
                            current_items_str,
                            height=200,
                            key=f"edit_{field_name}_{form_key}"
                        )
                        try:
                            parsed_items = json.loads(edited_items_str)
                            updated_data[field_name] = [Item(**item_dict).dict() for item_dict in parsed_items] # Ensure it's a list of dicts
                        except (json.JSONDecodeError, TypeError, ValueError) as e:
                            st.warning(f"Invalid JSON for {field_name}. Please correct it. Error: {e}")
                            updated_data[field_name] = [] # Fallback to empty list
                    else:
                        current_val = str(field_value) if field_value is not None else ""
                        edited_val = st.text_input(
                            label,
                            current_val,
                            key=f"edit_{field_name}_{form_key}"
                        )
                        if field_name == "total_amount":
                            try:
                                updated_data[field_name] = float(edited_val) if edited_val else 0.0
                            except ValueError:
                                st.warning(f"Invalid number for {field_name}. Please enter a numerical value.")
                                updated_data[field_name] = 0.0
                        else:
                            updated_data[field_name] = edited_val
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_button = st.form_submit_button("Submit & Next")
                with col2:
                    # Allow skipping without submitting current edits
                    skip_button = st.form_submit_button("Skip (Discard Changes) & Next")


                if submit_button:
                    # When submitting, we create a new dict for the reviewed_invoices list.
                    # We start with a copy of the *original* current_invoice dict from session state
                    # and then overlay the form updates and remove the unwanted fields.
                    final_output_for_reviewed = current_invoice_full.copy() 
                    for key, val in updated_data.items():
                        final_output_for_reviewed[key] = val
                    
                    # Remove confidence_scores and needs_review for the final output
                    final_output_for_reviewed.pop("confidence_scores", None)
                    final_output_for_reviewed.pop("needs_review", None)
                    final_output_for_reviewed.pop("error", None) # Also remove error if it was successfully submitted
                    
                    st.session_state.reviewed_invoices.append(final_output_for_reviewed)
                    st.session_state.current_invoice_idx += 1
                    st.success("Invoice submitted successfully!")
                    st.rerun() 
                elif skip_button:
                    st.session_state.current_invoice_idx += 1
                    st.warning("Invoice skipped. Changes discarded.")
                    st.rerun() 

    else:
        st.subheader("All invoices reviewed!")
        st.json(st.session_state.reviewed_invoices, expanded=False)
        
        # Optionally save the final reviewed data to a file
        if st.button("Save All Reviewed Data"):
            output_reviewed_filename = "reviewed_invoice_data.json"
            with open(output_reviewed_filename, "w", encoding="utf-8") as f:
                json.dump(st.session_state.reviewed_invoices, f, indent=2)
            st.success(f"All reviewed data saved to '{output_reviewed_filename}'")
            st.download_button(
                label="Download Reviewed Data",
                data=json.dumps(st.session_state.reviewed_invoices, indent=2),
                file_name=output_reviewed_filename,
                mime="application/json"
            )

else:
    st.info("Click 'Start Extraction and Review' to begin processing invoices.")