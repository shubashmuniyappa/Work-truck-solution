import os
import json
import requests
import tempfile
import base64 # Import base64 for encoding
from urllib.parse import urlparse
import streamlit as st # type: ignore
from openai import AzureOpenAI # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader # type: ignore
from pydantic import BaseModel, Field, conlist # type: ignore

# --- Configuration ---
DOCINTELLIGENCE_ENDPOINT = "https://quaddocintelligence1.cognitiveservices.azure.com/"
DOCINTELLIGENCE_KEY = "53uBovu34ZLs4HFKjFo3nW3qDUh8utA0gBY3Q8BlcjpTkPmefnBWJQQJ99BEACYeBjFXJ3w3AAALACOGSie3"

OPENAI_ENDPOINT = "https://nikhi-mb4qln04-swedencentral.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
OPENAI_DEPLOYMENT = "gpt-4o"
OPENAI_API_KEY = "4prHi16lJv4qDEATOl11M4f99KCcnntffozdHXm2Umfq8t3KeWVJJQQJ99BEACfhMk5XJ3w3AAAAACOGEJ7N"
OPENAI_API_VERSION = "2025-01-01-preview"

# ADI analysis features
ADI_ANALYSIS_FEATURES = ["ocrHighResolution"]

# Initialize Azure OpenAI Client
openai_client = AzureOpenAI(
    api_version=OPENAI_API_VERSION,
    azure_endpoint=OPENAI_ENDPOINT,
    api_key=OPENAI_API_KEY,
)

# --- Define Pydantic Models for Structured Output (Optional but highly recommended) ---
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
    list_of_items: conlist(Item) = Field(default_factory=list) # type: ignore
    total_amount: float = 0.0
    file_path: str = ""
    
    needs_review: dict = Field(default_factory=dict)
    error: str = ""

# --- Utility Functions ---
def get_filename_from_url(url: str) -> str:
    """Extracts filename from a URL."""
    return os.path.basename(urlparse(url).path)

def save_uploaded_file(uploaded_file):
    """Saves an uploaded file to a temporary location and returns its path."""
    try:
        # Use the original filename as suffix for better temp file recognition
        suffix = os.path.splitext(uploaded_file.name)[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error saving uploaded file: {e}")
        return None

# --- Document Intelligence and LLM Extraction ---
def extract_document_data(file_path: str):
    """
    Loads document using Azure AIDocumentIntelligenceLoader, extracts full text,
    and returns raw ADI analysis results.
    """
    loader = AzureAIDocumentIntelligenceLoader(
        api_endpoint=DOCINTELLIGENCE_ENDPOINT,
        api_key=DOCINTELLIGENCE_KEY,
        file_path=file_path,
        api_model="prebuilt-invoice",
        mode="page",
        analysis_features=ADI_ANALYSIS_FEATURES,
    )
    documents = loader.load()

    full_text = "\n\n".join([doc.page_content for doc in documents])
    
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

    For each field, **if the information is not explicitly and clearly found in the document, leave the string fields empty ("") and numerical fields as 0.0.** Do not invent or infer values.

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

def process_invoice(file_path: str, source_name: str):
    """Processes a single invoice document using LLM extraction and determines review needs."""
    st.write(f"**Processing:** {source_name}")
    
    display_file_path = os.path.basename(file_path)

    try:
        full_text, _ = extract_document_data(file_path)
        llm_extracted_data = extract_invoice_json_llm(full_text)
        
        final_invoice_data = InvoiceData(file_path=display_file_path)
        
        needs_review = {}

        fields_to_check = InvoiceData.schema()['properties'].keys()
        
        for field in fields_to_check:
            if field in ["file_path", "needs_review", "error"]:
                continue

            llm_value = llm_extracted_data.get(field)

            if field == "list_of_items":
                if llm_value:
                    try:
                        final_invoice_data.list_of_items = [Item(**item) for item in llm_value]
                    except Exception as e:
                        st.warning(f"Failed to parse LLM list_of_items for {source_name}: {e}. Using empty list.")
                        final_invoice_data.list_of_items = []
                        needs_review[field] = True
                else:
                    final_invoice_data.list_of_items = []
                
                if not final_invoice_data.list_of_items:
                    needs_review[field] = True
                else:
                    needs_review[field] = False
            else:
                if field == "total_amount":
                    try:
                        extracted_val = float(llm_value) if llm_value is not None and llm_value != "" else 0.0
                        setattr(final_invoice_data, field, extracted_val)
                        if extracted_val == 0.0:
                            needs_review[field] = True
                        else:
                            needs_review[field] = False
                    except ValueError:
                        setattr(final_invoice_data, field, 0.0)
                        needs_review[field] = True
                else:
                    extracted_val = str(llm_value) if llm_value is not None else ""
                    setattr(final_invoice_data, field, extracted_val)
                    if not extracted_val.strip():
                        needs_review[field] = True
                    else:
                        needs_review[field] = False

        final_invoice_data.needs_review = needs_review
        
        return {
            "final_data": final_invoice_data.dict(),
            "source_file_name": source_name,
            "local_file_path": file_path # Store the temp path for display
        }

    except Exception as e:
        st.error(f"Error processing {source_name}: {e}")
        error_data_model = InvoiceData(file_path=display_file_path, error=str(e))
        error_data_model.needs_review = {
            field: True for field in error_data_model.schema()['properties'].keys() 
            if field not in ["file_path", "needs_review", "error"]
        }
        
        return {
            "final_data": error_data_model.dict(),
            "source_file_name": source_name,
            "local_file_path": file_path
        }
    finally:
        # We will now delete the temporary file after it has been used for display as well
        pass


# --- Streamlit Application ---
st.set_page_config(layout="wide", page_title="Invoice Review Application")

st.markdown(
    """
    <style>
    /* Full background stripes */
    .stApp {
        background: repeating-linear-gradient(
            45deg,
            #1e1e1e,
            #1e1e1e 10px,
            #2a2a2a 10px,
            #2a2a2a 20px
        );
        color: white;
    }

    /* Container styling */
    .block-container {
        background-color: rgba(0, 0, 0, 0.6);
        padding: 2rem;
        border-radius: 12px;
    }

    /* Header and label text */
    h1, h2, h3, h4, h5, h6, p, label {
        color: white !important;
    }

    /* File uploader styling */
    .stFileUploader {
        background-color: #000000 !important;  /* Updated color */
        color: white !important;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 0 10px rgba(255, 255, 255, 0.05);
        border: 1px solid #2a2a2a;
    }

    /* Card or section styling */
    .css-1d391kg, .css-1v3fvcr {
        background-color: rgba(0, 0, 0, 0.5) !important;
        border-radius: 10px;
    }

    /* Unified button styling */
    .stButton > button, .stForm > button {
        background-color: #444444 !important;
        color: white !important;
        border: 1px solid #888888;
        border-radius: 8px;
        padding: 0.5rem 1.2rem;
        font-weight: bold;
        font-size: 16px;
        transition: background-color 0.3s ease;
    }

    .stButton > button:hover, .stForm > button:hover {
        background-color: #666666 !important;
        cursor: pointer;
    }
    </style>
    """,
    unsafe_allow_html=True
)


st.title("Invoice Processing System")

st.write("PDF, JPG, PNG,")

# Upload functionality
uploaded_files = st.file_uploader("Upload Invoices", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

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

    if uploaded_files:
        st.spinner(f"Processing {len(uploaded_files)} uploaded invoices...")
        for uploaded_file in uploaded_files:
            temp_path = save_uploaded_file(uploaded_file)
            if temp_path:
                processed_data = process_invoice(temp_path, uploaded_file.name)
                st.session_state.invoices_to_review.append(processed_data)
        st.success("Extraction complete. Ready for review!")
        st.rerun()

    else:
        st.warning("Please upload documents to start extraction.")

# Display current invoice for review
if st.session_state.invoices_to_review:
    if st.session_state.current_invoice_idx < len(st.session_state.invoices_to_review):
        current_invoice = st.session_state.invoices_to_review[st.session_state.current_invoice_idx]
        st.subheader(f"Review Invoice {st.session_state.current_invoice_idx + 1}/{len(st.session_state.invoices_to_review)}")
        
        display_file_name = current_invoice['source_file_name']
        st.markdown(f"**Source Document:** `{display_file_name}`")
        
        if current_invoice['final_data'].get('error'):
            st.error(f"Error encountered for this invoice: {current_invoice['final_data']['error']}")
            st.warning("Please review or skip this invoice.")
            if st.button("Skip Invoice"):
                # Clean up temp file on skip
                if os.path.exists(current_invoice['local_file_path']):
                    os.unlink(current_invoice['local_file_path'])
                st.session_state.current_invoice_idx += 1
                st.rerun() 
        else:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("### Original Invoice Document")
                file_path_to_display = current_invoice['local_file_path']
                file_extension = os.path.splitext(file_path_to_display)[1].lower()

                if file_extension == ".pdf":
                    try:
                        with open(file_path_to_display, "rb") as f:
                            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="900" type="application/pdf"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Could not display PDF: {e}")
                        st.info(f"The uploaded PDF is located at: `{display_file_name}`. You may need to open it manually.")
                elif file_extension in [".jpg", ".jpeg", ".png"]:
                    st.image(file_path_to_display, use_column_width=True)
                else:
                    st.info(f"File type '{file_extension}' cannot be directly displayed. You may need to open the original document: `{display_file_name}`.")
                
            with col2:
                st.markdown("### Extracted Data")
                st.write("Review and edit the extracted data below.")

                form_key = f"invoice_form_{st.session_state.current_invoice_idx}"
                with st.form(key=form_key):
                    current_invoice_full = current_invoice['final_data']
                    updated_data = {}
                    
                    fields_to_display = [f for f in InvoiceData.schema()['properties'].keys() if f not in ["file_path", "needs_review", "error"]]
                    
                    for field_name in fields_to_display:
                        field_value = current_invoice_full.get(field_name) 
                        needs_review = current_invoice_full.get('needs_review', {}).get(field_name, False)
                        
                        label_color = ":red" if needs_review else ""
                        label = f"{field_name.replace('_', ' ').title()}"
                        
                        if field_name == "list_of_items":
                            st.markdown(f"**{label_color}[{label}]**")
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
                                updated_data[field_name] = [Item(**item_dict).dict() for item_dict in parsed_items]
                            except (json.JSONDecodeError, TypeError, ValueError) as e:
                                st.warning(f"Invalid JSON for {field_name}. Please correct it. Error: {e}")
                                updated_data[field_name] = []
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
                        skip_button = st.form_submit_button("Skip (Discard Changes) & Next")

                    if submit_button:
                        final_output_for_reviewed = current_invoice.copy()
                        final_output_for_reviewed['final_data'] = current_invoice_full.copy()
                        for key, val in updated_data.items():
                            final_output_for_reviewed['final_data'][key] = val
                        
                        final_output_for_reviewed['final_data'].pop("needs_review", None)
                        final_output_for_reviewed['final_data'].pop("error", None)
                        
                        st.session_state.reviewed_invoices.append(final_output_for_reviewed)
                        # Clean up temp file on submit
                        if os.path.exists(current_invoice['local_file_path']):
                            os.unlink(current_invoice['local_file_path'])
                        st.session_state.current_invoice_idx += 1
                        st.success("Invoice submitted successfully!")
                        st.rerun() 
                    elif skip_button:
                        # Clean up temp file on skip
                        if os.path.exists(current_invoice['local_file_path']):
                            os.unlink(current_invoice['local_file_path'])
                        st.session_state.current_invoice_idx += 1
                        st.warning("Invoice skipped. Changes discarded.")
                        st.rerun() 

    else:
        st.subheader("All invoices reviewed!")
        st.json([invoice['final_data'] for invoice in st.session_state.reviewed_invoices], expanded=False)
        
        if st.button("Save All Reviewed Data"):
            output_reviewed_filename = "reviewed_invoice_data.json"
            with open(output_reviewed_filename, "w", encoding="utf-8") as f:
                json.dump([invoice['final_data'] for invoice in st.session_state.reviewed_invoices], f, indent=2)
            st.success(f"All reviewed data saved to '{output_reviewed_filename}'")
            st.download_button(
                label="Download Reviewed Data",
                data=json.dumps([invoice['final_data'] for invoice in st.session_state.reviewed_invoices], indent=2),
                file_name=output_reviewed_filename,
                mime="application/json"
            )

else:
    st.info("Upload documents to begin processing invoices.")