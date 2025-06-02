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

The goal is to return the information in the following structured JSON format:
{
  "invoice_number": "",
  "dealer": "",
  "dealer_address": "",
  "Buyer name": "",
  "Buyer address": "",
  "vin": "",
  "condition": "",
  "model_year": "",
  "make": "",
  "model": "",
  "body_model": "",
  "invoice_date": "",
  "components": [
    {
      "description": "",
      "Amount": ""
      ]
    }
  ],
  "total": ""
}

- Extract the fields only if they are found in the input.
- If a field is missing, leave it blank or omit it.
- Ensure all `components` are correctly listed with their attributes.
- Extract clean text (no trailing whitespace or labels).
- Use exact field names and structure in the JSON format shown above.
"""

def get_filename_from_url(url):
    return os.path.basename(urlparse(url).path)

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

def is_invoice_start(text: str) -> bool:
    triggers = ["Invoice #", "Invoice Number", "Invoice Date"]
    return any(trigger.lower() in text.lower() for trigger in triggers)

def extract_invoice_groups(file_path):
    loader = AzureAIDocumentIntelligenceLoader(
        api_endpoint=docintelligence_endpoint,
        api_key=docintelligence_key,
        file_path=file_path,
        api_model="prebuilt-invoice",
        mode="page",
        analysis_features=analysis_features,
    )
    documents = loader.load()

    invoice_groups = []
    current_group = []

    for doc in documents:
        page_text = doc.page_content
        if is_invoice_start(page_text):
            if current_group:
                invoice_groups.append(current_group)
            current_group = [page_text]
        else:
            current_group.append(page_text)

    if current_group:
        invoice_groups.append(current_group)

    return invoice_groups

def extract_invoice_json(text: str):
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract the information from the following document text:\n\n{text}"},
        ],
        max_tokens=5000,
        temperature=1.0,
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
        return {"error": "JSON parsing failed", "raw_response": cleaned}

# --- URLs List ---

urls =[
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-0c5eedf1-02b7-43f7-8082-eb1a058e3a44.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-4da4b0e6-93bc-46b7-a34d-da8cc4c64ab9.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-7b1bf227-db86-4e9d-bb16-3f374a50cd2e.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-5a704c11-b3a7-4df8-b58d-0c69aab26f0f.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-8ad73279-2a32-4f43-9167-bbe134ae9d50.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-0037ad59-85a0-44c1-974e-404023255dee.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-181b0e40-9822-4430-b92b-40a7a0a86a1f.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-955af315-10b3-41bb-9875-485250cd6bd8.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-9492c5ed-0a9a-4d34-8ae5-b2063e75752c.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-ad6570bc-952d-4fa2-bc55-c7449ca955a9.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-b7857720-2e2e-44d5-b708-057e0eadca58.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-bb15df87-0dff-4f24-beca-4edda9ffc67f.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-c8ae41c4-0d29-48da-82ec-e7b84e9121b0.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-d591f427-3889-4bb4-af85-ffd5421e966a.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-e0ddf501-4a3e-44fd-9ad6-30afdc6e5dcc.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-e7d0f626-0d6b-4db7-9864-63bc7763ee8e.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-f1777fb9-f4f2-4952-bd96-9d96faac1493.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-2ef2390d-c8c9-4805-901b-21d4af7f46df.pdf",
   "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-1184053b-0914-42c9-b5af-ee337759564c.pdf"
]


# --- Main Processing ---
all_invoices = []

for url in urls:
    print(f"\nProcessing: {url}")
    try:
        filename = get_filename_from_url(url)
        local_file = download_file(url)

        invoice_groups = extract_invoice_groups(local_file)
        print(f"  -> Found {len(invoice_groups)} invoice(s)")

        for idx, group in enumerate(invoice_groups, start=1):
            full_text = "\n\n".join(group)
            print(f"    -> Extracting invoice {idx}")
            invoice_data = extract_invoice_json(full_text)
            invoice_data["source_file"] = filename
            all_invoices.append(invoice_data)

        os.unlink(local_file)

    except Exception as e:
        print(f"Error processing {url}: {e}")
        all_invoices.append({
            "source_file": get_filename_from_url(url),
            "error": str(e)
        })

# --- Save Final Output ---
with open("josn_of_20_files.json", "w", encoding="utf-8") as f:
    json.dump(all_invoices, f, indent=2)

print("\n All done! Extracted data saved to 'josn_of_20_files.json'")
