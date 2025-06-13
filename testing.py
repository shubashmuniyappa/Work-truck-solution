import os
import json
from openai import AzureOpenAI  # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader  # type: ignore

# Azure Document Intelligence endpoint and key
endpoint = "https://quaddocintelligence1.cognitiveservices.azure.com/"
key = "53uBovu34ZLs4HFKjFo3nW3qDUh8utA0gBY3Q8BlcjpTkPmefnBWJQQJ99BEACYeBjFXJ3w3AAALACOGSie3"
file_path = "Training-pdf/invoice-4da4b0e6-93bc-46b7-a34d-da8cc4c64ab9.pdf"

analysis_features = ["ocrHighResolution"]

# Load and analyze document using Azure Document Intelligence Loader
document_intelligence_client = AzureAIDocumentIntelligenceLoader(
    api_endpoint=endpoint,
    api_key=key,
    file_path=file_path,
    api_model="prebuilt-invoice",
    mode="page",
    analysis_features=analysis_features,
)

documents = document_intelligence_client.load()

# Azure OpenAI configuration
openai_endpoint = "https://nikhi-mb4qln04-swedencentral.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
model_name = "gpt-4o"
deployment = "gpt-4o"
subscription_key = "4prHi16lJv4qDEATOl11M4f99KCcnntffozdHXm2Umfq8t3KeWVJJQQJ99BEACfhMk5XJ3w3AAAAACOGEJ7N"
api_version = "2025-01-01-preview"

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=openai_endpoint,
    api_key=subscription_key,
)

# Send the extracted document text to GPT model for structured JSON extraction
response = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": """
You are an intelligent and detail-oriented assistant specialized in vehicle inventory data extraction.

Your task is to extract structured information from unstructured text content of vehicle inventory documents (such as invoices, delivery sheets, or build sheets).

The goal is to return the information in the following structured JSON format:
{
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
      "attributes": [
        {
          "Amount": ""
        }
      ]
    }
    "total": ""
  ]
}

- Extract the fields only if they are found in the input.
- If a field is missing, leave it blank or omit it.
- Ensure all `components` are correctly listed with their attributes.
- Extract clean text (no trailing whitespace or labels).
- Use exact field names and structure in the JSON format shown above.
"""
        },
        {
            "role": "user",
            "content": f"""
Extract the information from the following document text and return it in the required JSON format:

{documents}
"""
        }
    ],
    max_tokens=5000,
    temperature=1.0,
    top_p=1.0,
    frequency_penalty=0.0,
    presence_penalty=0.0,
    model=deployment
)

raw_content = response.choices[0].message.content

cleaned_content = raw_content.strip().strip("```").replace("json", "", 1).strip()

# Parse response JSON string into Python dict
data = json.loads(cleaned_content)

# Save extracted JSON data to file
output_filename = "invoice-181b0e40-9822-4430-b92b-40a7a0a86a1f.pdf.json"
with open(output_filename, "w") as f:
    json.dump(data, f, indent=2)

print(f"JSON saved to {output_filename}")
