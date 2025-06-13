import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient, AnalyzeDocumentOptions, DocumentAnalysisFeature

def extract_fields_with_query_fields(document_url: str, fields_to_query: list):
    """
    Extracts specified fields from a document URL using the 'prebuilt-layout' model
    with the 'queryFields' add-on capability.

    Args:
        document_url (str): The URL of the document (PDF or image).
        fields_to_query (list): A list of strings representing the names of the fields to extract.
                                Example: ["Invoice Number", "Total Amount", "Customer Name"]
    """
    load_dotenv()

    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint or not key:
        print("Error: AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY must be set in the .env file.")
        return

    if not fields_to_query:
        print("Warning: No fields specified for queryFields. Proceeding with standard layout analysis.")

    try:
        document_analysis_client = DocumentAnalysisClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )

        print(f"Analyzing document from URL: {document_url} using 'prebuilt-layout' with query fields: {fields_to_query}...")

        poller = document_analysis_client.begin_analyze_document_from_url(
            "prebuilt-layout",
            document_url,
            features=[DocumentAnalysisFeature.QUERY_FIELDS], # Enable the queryFields feature
            query_fields=fields_to_query # Provide the list of fields to query
        )
        result = poller.result()

        print("\n--- Document Layout Analysis Results (with Query Fields) ---")

        if result.documents:
            for idx, doc in enumerate(result.documents):
                print(f"--------Document #{idx + 1}--------")
                if doc.fields:
                    print("  Extracted Query Fields:")
                    for field_name, field in doc.fields.items():
                        if field_name in [f.replace(" ", "") for f in fields_to_query]: # Check against normalized query field names
                            if field.value is not None:
                                print(f"    {field_name}: {field.value} (Confidence: {field.confidence:.2f})")
                            else:
                                print(f"    {field_name}: (No value extracted - Confidence: {field.confidence:.2f})")
                else:
                    print("  No query fields extracted for this document.")
                print("------------------------------------------")
        else:
            print("No documents found in the analysis result.")

        # You still get all the regular layout information (lines, tables, etc.)
        # from the result object alongside the queried fields.
        print("\n--- Additional Layout Information (e.g., first 5 lines of Page 1) ---")
        if result.pages and result.pages[0].lines:
            for i, line in enumerate(result.pages[0].lines[:5]):
                print(f"  Line {i+1}: '{line.content}'")
        else:
            print("No lines found on page 1.")

    except Exception as e:
        print(f"An error occurred: {e}")

# Example Usage
if __name__ == "__main__":
    # Replace with the public URL of your document
    document_url_to_analyze = "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-323d0700-7599-47a9-80e4-f10a4afc31c2.pdf"

    # Define the fields you want to extract.
    # The names here are natural language and the model will try to map them.
    desired_fields = [
        "Invoice Number",
        "Invoice Date",
        "Due Date",
        "Total Amount",
        "Customer Name",
        "Shipping Address",
        "Service Description", # Example of a field not typically in prebuilt invoice model
        "VIN", # Another example of a custom field
        "Make",
        "Model"
    ]

    extract_fields_with_query_fields(document_url_to_analyze, desired_fields)