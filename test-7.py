<<<<<<< HEAD
import os
import json
import requests
import tempfile
from urllib.parse import urlparse
from openai import AzureOpenAI  # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader  # type: ignore

# --- Azure configuration ---
docintelligence_endpoint = "https://quaddocintelligence1.cognitiveservices.azure.com/"
docintelligence_key = "53uBovu34ZLs4HFKjFo3nW3qDUh8utA0gBY3Q8BlcjpTkPmefnBWJQQJ99BEACYeBjFXJ3w3AAALACOGSie3"

openai_endpoint = "https://nikhi-mb4qln04-swedencentral.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
deployment = "gpt-4o"
subscription_key = "4prHi16lJv4qDEATOl11M4f99KCcnntffozdHXm2Umfq8t3KeWVJJQQJ99BEACfhMk5XJ3w3AAAAACOGEJ7N"
api_version = "2025-01-01-preview"

# Using a more standard and common analysis feature for document intelligence
# 'prebuilt-invoice' already extracts text and tables, so 'ocrHighResolution' might be redundant
# for general text extraction unless specifically needed for very low-quality scans.
# I'll keep it for now as it was in your original code, but if you notice
# slower processing, it's something to consider.
analysis_features = ["ocrHighResolution"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=openai_endpoint,
    api_key=subscription_key,
)

# --- UPDATED SYSTEM PROMPT ---
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
  "total_amount": 0.0,
  "file_path": ""
}

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

- **file_path**:
    - This field will be filled by the system, derived from the input URL. Do NOT attempt to extract this from the document content. The format will be "img/invoices/bodyinvoices/-/invoice-example.pdf".

- Extract clean text (no trailing whitespace or labels).
- Ensure the output strictly adheres to the JSON structure and field names specified above.
- Be very precise and thorough in extracting all available information based on these guidelines.
"""

def get_filename_from_url(url):
    return os.path.basename(urlparse(url).path)

def get_relative_path_from_url(url):
    parsed_url = urlparse(url)
    path_segments = parsed_url.path.split('/')
    try:
        img_index = path_segments.index('img')
        relative_path = '/'.join(path_segments[img_index:])
        return relative_path
    except ValueError:
        return parsed_url.path.lstrip('/') # Fallback if 'img' isn't found at the start

def download_file(url):
    response = requests.get(url)
    if response.status_code == 200:
        suffix = os.path.splitext(get_filename_from_url(url))[-1] or ".pdf"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(response.content)
        tmp.close()
        return tmp.name
    else:
        raise Exception(f"Failed to download file: {url}")

def extract_document_text(file_path):
    loader = AzureAIDocumentIntelligenceLoader(
        api_endpoint=docintelligence_endpoint,
        api_key=docintelligence_key,
        file_path=file_path,
        api_model="prebuilt-invoice",
        mode="page",  # Keep "page" mode to get content per page, then join them
        analysis_features=analysis_features,
    )
    documents = loader.load()
    # Join all page contents into a single string for the entire document
    full_text = "\n\n".join([doc.page_content for doc in documents])
    return full_text

def extract_invoice_json(text: str):
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract the information from the following document text:\n\n{text}"},
        ],
        max_tokens=5000,
        temperature=0.0, # Lower temperature for more deterministic output based on prompt
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        model=deployment,
    )

    content = response.choices[0].message.content
    cleaned = content.strip().strip("```").replace("json", "", 1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"JSON parsing failed for response: {cleaned}")
        return {"error": "JSON parsing failed", "raw_response": cleaned}

# --- URLs List ---
urls =[
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-419bb7b3-26ef-487f-8319-0fb753b0b179.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-8ad73279-2a32-4f43-9167-bbe134ae9d50.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-4ce8b538-e524-4040-86b1-e6373c444d61.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-0c5eedf1-02b7-43f7-8082-eb1a058e3a44.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-c8ae41c4-0d29-48da-82ec-e7b84e9121b0.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-181b0e40-9822-4430-b92b-40a7a0a86a1f.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-bc0c8b1a-84a2-4cd6-a1d2-0a8cc7476580.pdf"
]

# Remove any empty strings from the URL list if present
urls = [url for url in urls if url]

# --- Main Processing ---
all_invoices = []

for url in urls:
    print(f"\nProcessing: {url}")
    try:
        relative_file_path = get_relative_path_from_url(url)
        local_file = download_file(url)

        full_document_text = extract_document_text(local_file)
        
        print(f"  -> Extracting invoice data from document text.")
        invoice_data = extract_invoice_json(full_document_text)
        
        invoice_data["file_path"] = relative_file_path
        
        all_invoices.append(invoice_data)

        os.unlink(local_file)

    except Exception as e:
        print(f"Error processing {url}: {e}")
        all_invoices.append({
            "file_path": get_relative_path_from_url(url), # Still try to get file path even on error
            "error": str(e),
            "invoice_number": "", # Default empty fields for error entries
            "bill_to": "",
            "ship_to": "",
            "vin": "",
            "distributor": "",
            "make": "",
            "model": "",
            "year": "",
            "invoice_date": "",
            "list_of_items": [],
            "total_amount": 0.0
        })

# --- Save Final Output ---
output_filename = "extracted_invoice_data.json" 
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(all_invoices, f, indent=2)

=======
import os
import json
import requests
import tempfile
from urllib.parse import urlparse
from openai import AzureOpenAI  # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader  # type: ignore

# --- Azure configuration ---
docintelligence_endpoint = "https://quaddocintelligence1.cognitiveservices.azure.com/"
docintelligence_key = "53uBovu34ZLs4HFKjFo3nW3qDUh8utA0gBY3Q8BlcjpTkPmefnBWJQQJ99BEACYeBjFXJ3w3AAALACOGSie3"

openai_endpoint = "https://nikhi-mb4qln04-swedencentral.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
deployment = "gpt-4o"
subscription_key = "4prHi16lJv4qDEATOl11M4f99KCcnntffozdHXm2Umfq8t3KeWVJJQQJ99BEACfhMk5XJ3w3AAAAACOGEJ7N"
api_version = "2025-01-01-preview"

# Using a more standard and common analysis feature for document intelligence
# 'prebuilt-invoice' already extracts text and tables, so 'ocrHighResolution' might be redundant
# for general text extraction unless specifically needed for very low-quality scans.
# I'll keep it for now as it was in your original code, but if you notice
# slower processing, it's something to consider.
analysis_features = ["ocrHighResolution"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=openai_endpoint,
    api_key=subscription_key,
)

# --- UPDATED SYSTEM PROMPT ---
# --- UPDATED SYSTEM PROMPT ---
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
  "total_amount": 0.0,
  "file_path": ""
}

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
    - **Crucial VIN Rule**: The characters 'I', 'O', and 'Q' are **never** used in a VIN to avoid confusion with '1', '0', and '0' (or '9'). If you encounter what appears to be a VIN, and it contains 'O' or 'I' or 'Q', assume it's a '0' or '1' respectively, and correct it during extraction. Specifically, if an 'O' is found, it should be treated as a '0' (zero).
    - Vin number follows following conventions,1–3    Letters/Digits  Manufacturer & region (WMI), 4–8    Letters/Digits  Vehicle details (VDS), 9    Digit or X  Check digit, 10 Letter or Digit Model year (e.g., R = 2024, S = 2025), 11   Letter or Digit Plant code, 12–17    Digits only Sequential serial number
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

- **file_path**:
    - This field will be filled by the system, derived from the input URL. Do NOT attempt to extract this from the document content. The format will be "img/invoices/bodyinvoices/-/invoice-example.pdf".

- Extract clean text (no trailing whitespace or labels).
- Ensure the output strictly adheres to the JSON structure and field names specified above.
- Be very precise and thorough in extracting all available information based on these guidelines.
"""

def get_filename_from_url(url):
    return os.path.basename(urlparse(url).path)

def get_relative_path_from_url(url):
    parsed_url = urlparse(url)
    path_segments = parsed_url.path.split('/')
    try:
        img_index = path_segments.index('img')
        relative_path = '/'.join(path_segments[img_index:])
        return relative_path
    except ValueError:
        return parsed_url.path.lstrip('/') # Fallback if 'img' isn't found at the start

def download_file(url):
    response = requests.get(url)
    if response.status_code == 200:
        suffix = os.path.splitext(get_filename_from_url(url))[-1] or ".pdf"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(response.content)
        tmp.close()
        return tmp.name
    else:
        raise Exception(f"Failed to download file: {url}")

def extract_document_text(file_path):
    loader = AzureAIDocumentIntelligenceLoader(
        api_endpoint=docintelligence_endpoint,
        api_key=docintelligence_key,
        file_path=file_path,
        api_model="prebuilt-invoice",
        mode="page",  # Keep "page" mode to get content per page, then join them
        analysis_features=analysis_features,
    )
    documents = loader.load()
    # Join all page contents into a single string for the entire document
    full_text = "\n\n".join([doc.page_content for doc in documents])
    return full_text

def extract_invoice_json(text: str):
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract the information from the following document text:\n\n{text}"},
        ],
        max_tokens=5000,
        temperature=0.0, # Lower temperature for more deterministic output based on prompt
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        model=deployment,
    )

    content = response.choices[0].message.content
    cleaned = content.strip().strip("```").replace("json", "", 1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"JSON parsing failed for response: {cleaned}")
        return {"error": "JSON parsing failed", "raw_response": cleaned}

# --- URLs List ---
urls =[
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-419bb7b3-26ef-487f-8319-0fb753b0b179.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-8ad73279-2a32-4f43-9167-bbe134ae9d50.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-4ce8b538-e524-4040-86b1-e6373c444d61.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-0c5eedf1-02b7-43f7-8082-eb1a058e3a44.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-c8ae41c4-0d29-48da-82ec-e7b84e9121b0.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-181b0e40-9822-4430-b92b-40a7a0a86a1f.pdf",
    "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-bc0c8b1a-84a2-4cd6-a1d2-0a8cc7476580.pdf"
]

# Remove any empty strings from the URL list if present
urls = [url for url in urls if url]

# --- Main Processing ---
all_invoices = []

for url in urls:
    print(f"\nProcessing: {url}")
    try:
        relative_file_path = get_relative_path_from_url(url)
        local_file = download_file(url)

        full_document_text = extract_document_text(local_file)
        
        print(f"  -> Extracting invoice data from document text.")
        invoice_data = extract_invoice_json(full_document_text)
        
        invoice_data["file_path"] = relative_file_path
        
        all_invoices.append(invoice_data)

        os.unlink(local_file)

    except Exception as e:
        print(f"Error processing {url}: {e}")
        all_invoices.append({
            "file_path": get_relative_path_from_url(url), # Still try to get file path even on error
            "error": str(e),
            "invoice_number": "", # Default empty fields for error entries
            "bill_to": "",
            "ship_to": "",
            "vin": "",
            "distributor": "",
            "make": "",
            "model": "",
            "year": "",
            "invoice_date": "",
            "list_of_items": [],
            "total_amount": 0.0
        })

# --- Save Final Output ---
output_filename = "extracted_invoice_data.json" 
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(all_invoices, f, indent=2)

>>>>>>> ab43846 (accepeted backend code)
print(f"\nAll done! Extracted data saved to '{output_filename}'")