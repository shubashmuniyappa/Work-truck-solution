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
analysis_features = ["ocrHighResolution"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=openai_endpoint,
    api_key=subscription_key,
)

system_prompt = """
You are an intelligent and detail-oriented assistant specialized in vehicle inventory data extraction.

Your task is to extract structured information from unstructured text content of vehicle inventory documents (such as invoices, delivery sheets, or build sheets).

The goal is to return the information in the following structured JSON format. For each field, if the information is not present, leave the field empty ("") or 0.0 for numerical values.

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

Here are the specific guidelines for extracting each field:
- **invoice_number**: Look for keywords like "invoice", "invoice no", "invoice #". If not found, leave empty.
- **bill_to**: Look for keywords like "bill to", "sold to". If not found, leave empty.
- **ship_to**: Look for keywords like "ship to", "deliver to". If not found, leave empty.
- **vin**: Extract the Vehicle Identification Number.
- **distributor**: Get the name from the brokerage/invoice heading/invoice logo.
- **make**: Look for the keyword "make". If not present, find the car company mentioned somewhere in the invoice. Else, leave empty.
- **model**: Look for the keyword "model". If not present, leave empty.
- **year**: Look for the keyword "year". If not present, try to extract the year from the "invoice_date". Else, leave empty.
- **invoice_date**: Look for keywords like "date", "invoice date".
- **list_of_items**: Extract all line items with their "description" and "amount". If "amount" is not present for an item, leave it empty.
- **total_amount**: Look for keywords like "total", "total amount". If not found, default to 0.0.
- **file_path**: This will be provided by the system based on the input URL, in the format "img/invoices/bodyinvoices/-/invoice-8ad73279-2a32-4f43-9167-bbe134ae9d50.pdf". Do not try to extract this from the document content.

- Extract clean text (no trailing whitespace or labels).
- Use exact field names and structure in the JSON format shown above.
"""

def get_filename_from_url(url):
    return os.path.basename(urlparse(url).path)

def get_relative_path_from_url(url):
    parsed_url = urlparse(url)
    path_segments = parsed_url.path.split('/')
    # Assuming the path starts with /img/ and we need everything from 'img' onwards
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
        # Extract the relative file path as required
        relative_file_path = get_relative_path_from_url(url)
        local_file = download_file(url)

        # Treat the entire document as one invoice
        full_document_text = extract_document_text(local_file)
        
        print(f"  -> Extracting invoice data from document text.")
        invoice_data = extract_invoice_json(full_document_text)
        
        # Add the file_path to the extracted invoice data
        invoice_data["file_path"] = relative_file_path
        
        all_invoices.append(invoice_data)

        os.unlink(local_file)

    except Exception as e:
        print(f"Error processing {url}: {e}")
        all_invoices.append({
            "file_path": get_relative_path_from_url(url),
            "error": str(e)
        })

# --- Save Final Output ---
output_filename = "6_template_data.json" # Changed output filename for clarity
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(all_invoices, f, indent=2)

print(f"\nAll done! Extracted data saved to '{output_filename}'")