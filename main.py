import os
from openai import AzureOpenAI # type: ignore
import json
from azure.core.credentials import AzureKeyCredential # type: ignore
from azure.ai.documentintelligence import DocumentIntelligenceClient # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader # type: ignore
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader # type: ignore
import uuid
from guidelines import guidelines
# Replace with your actual endpoint and key
endpoint = "https://quaddocintelligence1.cognitiveservices.azure.com/"
key = "53uBovu34ZLs4HFKjFo3nW3qDUh8utA0gBY3Q8BlcjpTkPmefnBWJQQJ99BEACYeBjFXJ3w3AAALACOGSie3"
file_path="Training-pdf\invoice-0c5eedf1-02b7-43f7-8082-eb1a058e3a44.pdf"

analysis_features = ["ocrHighResolution"]

document_intelligence_client = AzureAIDocumentIntelligenceLoader(
    api_endpoint=endpoint,
    api_key=key, 
    file_path=file_path, 
    api_model="prebuilt-invoice",
    mode="page",
    analysis_features=analysis_features,
    
)

documents = document_intelligence_client.load()
print(documents)
endpoint = "https://nikhi-mb4qln04-swedencentral.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
model_name = "gpt-4o"
deployment = "gpt-4o"
subscription_key = "4prHi16lJv4qDEATOl11M4f99KCcnntffozdHXm2Umfq8t3KeWVJJQQJ99BEACfhMk5XJ3w3AAAAACOGEJ7N"
api_version = "2025-01-01-preview"

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
    
)


response = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": """
You are an intelligent invoice parser that extracts structured data from unstructured truck invoice text.

Your task is to identify and extract all **components installed on the truck** and present them in a structured JSON format.

The goal is to return the information in the following structured JSON format:
{
  "inventory_arrival_date": "",
  "stock_number": "",
  "vin": "",
  "condition": "",
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
  "components": [
    {
      "id": 1,
      "name": "Component Name",
      "attributes": [
        { "name": "Attribute Name", "value": "Attribute Value" }
      ]
    }
  ]
}
"""
        },
        {
            "role": "user",
            "content": f"""
Extract the information from the following document text and return it in the required JSON format:

{documents}

{guidelines}
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
# print(raw_content)
cleaned_content = raw_content.strip().strip("```").replace("json", "", 1).strip()
# print(cleaned_content)
# Step 3: Parse it into a Python dictionary (optional but good for validation)
data = json.loads(cleaned_content)

# Step 5: Save it to a JSON file
with open("data2.json", "w") as f:
    json.dump(data, f, indent=2)