# from azure.ai.documentintelligence import DocumentIntelligenceClient
# from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
# from azure.core.credentials import AzureKeyCredential

# # Setup
# endpoint = "https://quaddocintelligence.cognitiveservices.azure.com/"
# key = "B04YgUBj0FVsbrvqA4GZ8svZZZD5NWYEFpGwQwzJnn7f2S52NRNnJQQJ99BEACYeBjFXJ3w3AAALACOG077f"
# model = "prebuilt-layout"

# client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# # Create the request body
# request_body = AnalyzeDocumentRequest(
#     url_source="https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-ae96c1bb-2724-4206-9e73-4ce4724b685a.pdf"
# )

# # Call the service (note: request_body is passed positionally)
# poller = client.begin_analyze_document(
#     model,
#     request_body,
#     features=["keyValuePairs"]
# )

# result = poller.result()

# # Extract key-value pairs
# if result.key_value_pairs:
#     for kvp in result.key_value_pairs:
#         key_text = kvp.key.content if kvp.key else ""
#         value_text = kvp.value.content if kvp.value else ""
#         confidence = kvp.confidence if hasattr(kvp, 'confidence') else "N/A"
#         print(f"{key_text} : {value_text} (Confidence: {confidence})")
# else:
#     print("No key-value pairs found.")





import json
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

# Setup
endpoint = "https://quaddocintelligence.cognitiveservices.azure.com/"
key = "B04YgUBj0FVsbrvqA4GZ8svZZZD5NWYEFpGwQwzJnn7f2S52NRNnJQQJ99BEACYeBjFXJ3w3AAALACOG077f"
model = "prebuilt-layout"

client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# Request body
request_body = AnalyzeDocumentRequest(
    url_source="https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-ae96c1bb-2724-4206-9e73-4ce4724b685a.pdf"
)

# Send for analysis
poller = client.begin_analyze_document(
    model,
    request_body,
    features=["keyValuePairs"]
)

result = poller.result()

# Convert result to dictionary format for JSON serialization
def extract_kvp_data(result):
    extracted_data = []
    for kvp in result.key_value_pairs:
        key_text = kvp.key.content if kvp.key else ""
        value_text = kvp.value.content if kvp.value else ""
        confidence = kvp.confidence if hasattr(kvp, 'confidence') else None
        extracted_data.append({
            "key": key_text,
            "value": value_text,
            "confidence": confidence
        })
    return extracted_data

# Extract and save as JSON
extracted_kvps = extract_kvp_data(result)

# Save to file
with open("extracted_kvps.json", "w", encoding="utf-8") as f:
    json.dump(extracted_kvps, f, indent=4, ensure_ascii=False)

print("Key-value pairs saved to extracted_kvps.json")
