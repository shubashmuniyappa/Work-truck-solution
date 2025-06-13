import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

def extract_layout_details_from_url(document_url: str):
    """
    Extracts raw layout details (text, tables, selection marks, etc.) from a document URL
    using Azure Document Intelligence's prebuilt layout model.

    Args:
        document_url (str): The URL of the document (PDF or image) to analyze.
    """
    load_dotenv() # Load environment variables from .env file

    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint or not key:
        print("Error: AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY must be set in the .env file.")
        return

    try:
        document_analysis_client = DocumentAnalysisClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )

        print(f"Analyzing document from URL: {document_url} using 'prebuilt-layout' model...")

        # Begin analyzing the document using the prebuilt-layout model
        poller = document_analysis_client.begin_analyze_document_from_url(
            "prebuilt-layout", document_url
        )
        result = poller.result() # Wait for the analysis to complete

        print("\n--- Document Layout Analysis Results ---")

        # Iterate through each page of the document
        for page in result.pages:
            print(f"\nPage {page.page_number} (width: {page.width} {page.unit}, height: {page.height} {page.unit})")

            # Extract and print lines of text
            if page.lines:
                print(f"  Lines ({len(page.lines)} found):")
                for line in page.lines:
                    # REMOVED: line.confidence as it's not directly available on DocumentLine
                    print(f"    Line content: '{line.content}'")
                    # You can also access line.polygon for bounding box coordinates

            # Extract and print words
            if page.words:
                print(f"  Words ({len(page.words)} found on page):")
                # Showing first 5 words as an example, you can iterate all if needed
                for i, word in enumerate(page.words[:5]):
                    print(f"    Word: '{word.content}' (Confidence: {word.confidence:.2f})")
                if len(page.words) > 5:
                    print("    ... (and more words)")


            # Extract and print selection marks (checkboxes, radio buttons)
            if page.selection_marks:
                print(f"  Selection Marks ({len(page.selection_marks)} found):")
                for sm in page.selection_marks:
                    print(f"    Selection Mark State: {sm.state} (Confidence: {sm.confidence:.2f})")
                    # sm.polygon gives you the bounding box

        # Extract and print paragraphs (more structured text blocks)
        if result.paragraphs:
            print("\n--- Paragraphs ---")
            for para_idx, paragraph in enumerate(result.paragraphs):
                # Paragraphs often have a 'role' like 'title', 'pageHeader', etc.
                role_info = f" (Role: {paragraph.role})" if paragraph.role else ""
                print(f"  Paragraph {para_idx + 1}{role_info}: '{paragraph.content}' (Confidence: {paragraph.confidence:.2f})")
                # paragraph.bounding_regions gives you the location

        # Extract and print tables
        if result.tables:
            print("\n--- Tables ---")
            for table_idx, table in enumerate(result.tables):
                print(f"  Table {table_idx + 1} (Rows: {table.row_count}, Columns: {table.column_count})")
                for cell in table.cells:
                    # Print content for each cell, along with its row and column index
                    print(f"    Cell[{cell.row_index},{cell.column_index}] Content: '{cell.content}' (Confidence: {cell.confidence:.2f})")
                    # cell.bounding_regions gives you the cell's location

        # Key-Value Pairs (the layout model can sometimes detect these, but custom models are better for specific ones)
        if result.key_value_pairs:
            print("\n--- Key-Value Pairs (from layout) ---")
            for kvp in result.key_value_pairs:
                print(f"  Key: '{kvp.key.content}' | Value: '{kvp.value.content}' (Confidence: {kvp.confidence:.2f})")

        print("\n--- Analysis Complete ---")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    
    pdf_document_url = "https://images.worktrucksolutions.com/img/invoices/bodyinvoices/-/invoice-323d0700-7599-47a9-80e4-f10a4afc31c2.pdf"

    extract_layout_details_from_url(pdf_document_url)