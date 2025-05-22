import os
from azure.core.credentials import AzureKeyCredential # type: ignore
from azure.ai.documentintelligence import DocumentIntelligenceClient # type: ignore
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest # type: ignore
import json

from dotenv import load_dotenv # This import is there
load_dotenv()
 
DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") # Corrected variable name
DOCUMENT_INTELLIGENCE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
 
# sample document
formUrl = "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-ae96c1bb-2724-4206-9e73-4ce4724b685a.pdf"
document_intelligence_client = DocumentIntelligenceClient(
endpoint=DOCUMENT_INTELLIGENCE_ENDPOINT, credential=AzureKeyCredential(DOCUMENT_INTELLIGENCE_KEY)
)

poller = document_intelligence_client.begin_analyze_document(
"prebuilt-invoice", AnalyzeDocumentRequest(url_source=formUrl)
)
invoices = poller.result()
print(invoices)