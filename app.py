import os
import json
import tempfile
import streamlit as st
from main import InvoiceProcessor
import base64
import shutil
from copy import deepcopy
from datetime import datetime

# Configure the Streamlit page settings
st.set_page_config(
    page_title="Auto Invoice Processor",
    page_icon=":car:",
    layout="wide"
)

# Apply custom CSS for styling the Streamlit application elements
st.markdown("""
    <style>
    /* Main App Styles */
    .stApp {
        background-color: #e6f2ff;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #003366 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #333333;
    }
    
    /* Upload Section Styling */
    .stFileUploader {
        background-color: white;
        border-radius: 10px;
        padding: 25px;
        border: 2px dashed #4da6ff;
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    
    .stFileUploader:hover {
        border-color: #0066cc;
        box-shadow: 0 4px 12px rgba(0, 102, 204, 0.1);
    }
    
    /* Button Styling */
    .stButton>button {
        background: linear-gradient(135deg, #1e90ff, #0066cc);
        color: white !important;
        border-radius: 8px;
        padding: 0.6rem 1.6rem;
        border: none;
        font-weight: bold;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    /* File Card Display */
    .file-card {
        padding: 1.2rem;
        border-radius: 8px;
        background-color: white;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        border-left: 4px solid #1e90ff;
    }
    
    /* Status Indicators (success, error, processing) */
    .success {
        color: #00aa55 !important;
        font-weight: bold;
    }
    
    .error {
        color: #ff3333 !important;
        font-weight: bold;
    }
    
    .processing {
        color: #ff9900 !important;
        font-weight: bold;
    }
    
    /* PDF Container and Iframe */
    .pdf-container-wrapper {
        width: 100%;
        height: 600px;
        border: 2px solid #b3d9ff;
        border-radius: 10px;
        background-color: white;
        overflow: hidden;
    }
    
    .pdf-iframe {
        width: 100%;
        height: 100%;
        border: none;
    }
    
    /* Data Display Container */
    .data-container {
        height: 600px;
        overflow-y: auto;
        padding: 20px;
        background-color: white;
        border-radius: 10px;
        border: 2px solid #b3d9ff;
    }
    
    /* Styling for Extracted Text Input Fields */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        background-color: white !important;
    }
    
    .st-expander {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
        border: 1px solid #b3d9ff;
    }
    
    .st-expander .streamlit-expanderHeader {
        color: #003366 !important;
        font-weight: bold;
    }
    
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background-color: white !important;
    }
    
    /* Styles for the completion screen */
    .completion-screen {
        text-align: center;
        padding: 3rem;
        background-color: white;
        border-radius: 15px;
        margin: 2rem 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    .completion-title {
        color: #00aa55;
        font-size: 2.5rem;
        margin-bottom: 1.5rem;
    }
    
    .completion-button {
        margin: 1rem auto;
        min-width: 200px;
        max-width: 300px;
    }
    
    /* Save confirmation message style */
    .save-confirmation {
        padding: 12px;
        background-color: #f0fff4;
        border-radius: 8px;
        border-left: 4px solid #00aa55;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize Streamlit session state variables if they don't exist
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = {}
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'current_file_index' not in st.session_state:
    st.session_state.current_file_index = 0
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = {}
if 'temp_dir' not in st.session_state:
    st.session_state.temp_dir = None
if 'saved_files' not in st.session_state:
    st.session_state.saved_files = []
if 'files_to_save' not in st.session_state:
    st.session_state.files_to_save = set()
if 'edited_data' not in st.session_state:
    st.session_state.edited_data = {}
if 'processing_completed' not in st.session_state:
    st.session_state.processing_completed = False
if 'last_saved_file' not in st.session_state:
    st.session_state.last_saved_file = None
if 'last_save_time' not in st.session_state:
    st.session_state.last_save_time = None

# Define the desired order of fields for the output JSON
JSON_FIELD_ORDER = [
    "inventory_arrival_date",
    "stock_number",
    "vin",
    "condition",
    "model_year",
    "make",
    "model",
    "body_type",
    "body_line",
    "body_manufacturer",
    "body_model",
    "distributor",
    "distributor_location",
    "invoice_date",
    "components",
    "documents"
]

def enforce_json_structure(data):
    # Create a new dictionary to enforce the predefined JSON field order
    structured_data = {}
    for field in JSON_FIELD_ORDER:
        # Populate fields, providing default empty string or list for missing ones
        structured_data[field] = data.get(field, "" if field != "components" else [])
    
    # Ensure the "documents" array is properly structured with current date and path
    current_date = datetime.now().strftime('%Y-%m-%d')
    if "documents" not in structured_data or not structured_data["documents"]:
        structured_data["documents"] = [{
            "date": current_date,
            "type": "Invoice",
            "path": f"img/invoices/bodyinvoices/-/{data.get('filename', '')}"
        }]
    
    return structured_data

def display_extracted_data(data, filename):
    # Initialize edited_data for the current file if not already present in session state
    if filename not in st.session_state.edited_data:
        st.session_state.edited_data[filename] = enforce_json_structure({**data, "filename": filename})
    
    edited_data = st.session_state.edited_data[filename]
    
    st.subheader("Extracted Data")
    
    # Use a container to group input fields
    with st.container():
        # Expander for basic vehicle information
        with st.expander("Basic Information", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                # Text input fields for basic vehicle details
                edited_data['inventory_arrival_date'] = st.text_input(
                    "Inventory Arrival Date", 
                    edited_data.get('inventory_arrival_date', ''),
                    key=f"{filename}_arrival_date"
                )
                edited_data['stock_number'] = st.text_input(
                    "Stock Number", 
                    edited_data.get('stock_number', ''),
                    key=f"{filename}_stock_number"
                )
                edited_data['vin'] = st.text_input(
                    "VIN", 
                    edited_data.get('vin', ''),
                    key=f"{filename}_vin"
                )
                edited_data['condition'] = st.text_input(
                    "Condition", 
                    edited_data.get('condition', 'New'),
                    key=f"{filename}_condition"
                )
            with col2:
                # More text input fields for basic vehicle details
                edited_data['model_year'] = st.text_input(
                    "Model Year", 
                    edited_data.get('model_year', ''),
                    key=f"{filename}_model_year"
                )
                edited_data['make'] = st.text_input(
                    "Make", 
                    edited_data.get('make', ''),
                    key=f"{filename}_make"
                )
                edited_data['model'] = st.text_input(
                    "Model", 
                    edited_data.get('model', ''),
                    key=f"{filename}_model"
                )
        
        # Expander for body-related information
        with st.expander("Body Information"):
            col1, col2 = st.columns(2)
            with col1:
                # Text inputs for body specifications
                edited_data['body_type'] = st.text_input(
                    "Body Type", 
                    edited_data.get('body_type', ''),
                    key=f"{filename}_body_type"
                )
                edited_data['body_line'] = st.text_input(
                    "Body Line", 
                    edited_data.get('body_line', ''),
                    key=f"{filename}_body_line"
                )
            with col2:
                # Text inputs for body manufacturer and model
                edited_data['body_manufacturer'] = st.text_input(
                    "Body Manufacturer", 
                    edited_data.get('body_manufacturer', ''),
                    key=f"{filename}_body_manufacturer"
                )
                edited_data['body_model'] = st.text_input(
                    "Body Model", 
                    edited_data.get('body_model', ''),
                    key=f"{filename}_body_model"
                )
        
        # Expander for distributor information
        with st.expander("Distributor Information"):
            col1, col2 = st.columns(2)
            with col1:
                # Text input for distributor name
                edited_data['distributor'] = st.text_input(
                    "Distributor", 
                    edited_data.get('distributor', ''),
                    key=f"{filename}_distributor"
                )
            with col2:
                # Text input for distributor location
                edited_data['distributor_location'] = st.text_input(
                    "Distributor Location", 
                    edited_data.get('distributor_location', ''),
                    key=f"{filename}_distributor_location"
                )
        
        # Expander for invoice-specific information
        with st.expander("Invoice Information"):
            # Text input for invoice date
            edited_data['invoice_date'] = st.text_input(
                "Invoice Date", 
                edited_data.get('invoice_date', ''),
                key=f"{filename}_invoice_date"
            )
        
        # Section for dynamic components
        st.subheader("Components")
        
        # Button to add a new component
        if st.button("➕ Add New Component", key=f"{filename}_add_component"):
            if 'components' not in edited_data:
                edited_data['components'] = []
            # Append a new default component structure
            edited_data['components'].append({
                'name': 'New Component',
                'attributes': [{'name': 'New Attribute', 'value': ''}]
            })
            st.rerun() # Rerun to update the UI with the new component
        
        # Display existing components if any
        if 'components' in edited_data:
            for i, component in enumerate(edited_data['components']):
                # Expander for each component to manage its details
                with st.expander(f"Component {i+1}: {component.get('name', 'Unnamed')}"):
                    # Text input for component name
                    component['name'] = st.text_input(
                        "Component Name",
                        component.get('name', ''),
                        key=f"{filename}_comp_{i}_name"
                    )
                    
                    st.markdown("**Attributes**")
                    
                    # Display attributes for the current component
                    if 'attributes' in component:
                        for j, attr in enumerate(component['attributes']):
                            col_name, col_del = st.columns([4, 1])
                            with col_name:
                                # Text input for attribute name
                                attr['name'] = st.text_input(
                                    "Attribute Name",
                                    attr.get('name', ''),
                                    key=f"{filename}_comp_{i}_attr_{j}_name"
                                )
                            with col_del:
                                st.write("") # Spacer for alignment
                                # Button to delete an attribute
                                if st.button("🗑️", key=f"{filename}_comp_{i}_attr_{j}_delete"):
                                    component['attributes'].pop(j)
                                    st.rerun() # Rerun to update UI after deletion
                                
                            # Text input for attribute value
                            attr['value'] = st.text_input(
                                "Value",
                                attr.get('value', ''),
                                key=f"{filename}_comp_{i}_attr_{j}_value"
                            )
                            
                            # Add a separator between attributes
                            if j < len(component['attributes']) - 1:
                                st.markdown("---")
                    
                    # Button to add a new attribute to the current component
                    if st.button("➕ Add Attribute", key=f"{filename}_comp_{i}_add_attr"):
                        if 'attributes' not in component:
                            component['attributes'] = []
                        component['attributes'].append({'name': 'New Attribute', 'value': ''})
                        st.rerun() # Rerun to update UI with new attribute
                    
                    # Button to delete the entire component
                    if st.button("🗑️ Delete Component", key=f"{filename}_comp_{i}_delete"):
                        edited_data['components'].pop(i)
                        st.rerun() # Rerun to update UI after component deletion
    
    return edited_data

def save_data(filename, edited_data):
    # Save the processed and edited data to a JSON file
    try:
        output_dir = "processed_output"
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        # Construct the output file path
        output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
        
        # Write the data to the JSON file with pretty printing
        with open(output_path, "w") as f:
            json.dump(enforce_json_structure({**edited_data, "filename": filename}), f, indent=2)
        
        # Update session state to track saved files and last save info
        st.session_state.saved_files.append(output_path)
        st.session_state.files_to_save.discard(filename)
        st.session_state.last_saved_file = filename
        st.session_state.last_save_time = datetime.now().strftime("%H:%M:%S")
        
        # Show a success toast notification
        st.toast(f"✅ File saved successfully at: {output_path}", icon="✅")
        
        return True
    except Exception as e:
        # Display an error message if saving fails
        st.error(f"Error saving {filename}: {e}")
        return False

def reset_processing():
    # Reset all session state variables related to current processing, preserving saved files list
    st.session_state.processed_data = {}
    st.session_state.uploaded_files = []
    st.session_state.current_file_index = 0
    st.session_state.processing_status = {}
    st.session_state.edited_data = {}
    st.session_state.files_to_save = set()
    st.session_state.last_saved_file = None
    st.session_state.last_save_time = None
    # Clean up the temporary directory if it exists
    if st.session_state.temp_dir and os.path.exists(st.session_state.temp_dir):
        shutil.rmtree(st.session_state.temp_dir)
    st.session_state.temp_dir = None
    st.session_state.processing_completed = False

def show_completion_screen():
    # Display the completion message and a button to start new processing
    st.markdown("""
    <div class="completion-screen">
        <h1 class="completion-title">✅ Processing Complete!</h1>
        <p style="font-size: 1.2rem;">All files have been processed and saved successfully.</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 Start New Processing Session", key="process_more", use_container_width=True, 
                 type="primary", help="Click to process another batch of files"):
        reset_processing() # Reset the application state
        st.rerun() # Rerun Streamlit to show the initial upload screen

def main():
    st.title("Work Truck Solution's Invoice Processing")
    st.markdown("Transform complex vehicle invoices into organized, actionable information.")

    # Show the completion screen if all files have been processed and saved
    if st.session_state.processing_completed:
        show_completion_screen()
        return # Exit main function to prevent further processing logic

    # Initialize the InvoiceProcessor
    processor = InvoiceProcessor()

    # Step 1: File Upload Section
    st.header("1. Invoice Upload")
    
    uploaded_files = st.file_uploader(
        "Upload Invoice", 
        type="pdf", 
        accept_multiple_files=True,
        help="Drag and drop or click to upload PDF invoices"
    )

    # Handle newly uploaded files
    if uploaded_files and not st.session_state.processed_data:
        st.session_state.uploaded_files = uploaded_files
        st.success(f"{len(uploaded_files)} file(s) uploaded successfully!")
        
        # Initialize processing status for each uploaded file
        for file in uploaded_files:
            st.session_state.processing_status[file.name] = {
                'status': 'Ready to Process',
                'message': ''
            }

        # Display initial status of uploaded files
        status_container = st.container()
        with status_container:
            st.subheader("Processing Status")
            status_placeholders = {}
            for file in uploaded_files:
                status_placeholders[file.name] = st.empty()
                with status_placeholders[file.name]:
                    status = st.session_state.processing_status[file.name]
                    st.markdown(f"""
                    <div class="file-card">
                        <strong>{file.name}</strong> - 
                        <span class="success">{status['status']}</span>
                        {f"<br><small>{status['message']}</small>" if status['message'] else ""}
                    </div>
                    """, unsafe_allow_html=True)

        # Button to start the processing of uploaded files
        if st.button("Start Processing", key="process_btn"):
            # Create a temporary directory to store uploaded PDFs
            if not st.session_state.temp_dir:
                st.session_state.temp_dir = tempfile.mkdtemp()
            
            file_paths = []
            # Save uploaded files to the temporary directory
            for file in uploaded_files:
                path = os.path.join(st.session_state.temp_dir, file.name)
                with open(path, "wb") as f:
                    f.write(file.getbuffer())
                file_paths.append(path)
            
            # Process files one by one with a progress bar
            results = {}
            progress_bar = st.progress(0)
            for i, path in enumerate(file_paths):
                filename = os.path.basename(path)
                
                # Update status to "Processing" and refresh UI
                st.session_state.processing_status[filename] = {
                    'status': 'Processing',
                    'message': f'Processing file {i+1} of {len(file_paths)}'
                }
                progress_bar.progress(int((i+1)/len(file_paths)*100))
                
                with status_container:
                    with status_placeholders[filename]:
                        status = st.session_state.processing_status[filename]
                        st.markdown(f"""
                        <div class="file-card">
                            <strong>{filename}</strong> - 
                            <span class="processing">{status['status']}</span>
                            <br><small>{status['message']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                
                try:
                    # Call the invoice processor for the current file
                    file_results = processor.process_invoices([path])
                    if file_results and filename in file_results:
                        # Store processed data, ensuring consistent structure
                        results[filename] = enforce_json_structure({
                            **file_results[filename],
                            "filename": filename
                        })
                        # Update status to "Completed" on success
                        st.session_state.processing_status[filename] = {
                            'status': 'Completed',
                            'message': 'Extraction successful'
                        }
                    else:
                        raise Exception("No results returned")
                except Exception as e:
                    # Update status to "Error" if processing fails
                    st.session_state.processing_status[filename] = {
                        'status': 'Error',
                        'message': f'Processing failed: {str(e)}'
                    }
                
                # Update UI with final status for the current file
                with status_container:
                    with status_placeholders[filename]:
                        status = st.session_state.processing_status[filename]
                        status_class = "success" if status['status'] == "Completed" else "error"
                        st.markdown(f"""
                        <div class="file-card">
                            <strong>{filename}</strong> - 
                            <span class="{status_class}">{status['status']}</span>
                            <br><small>{status['message']}</small>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Store all processed data in session state
            st.session_state.processed_data = results
            # Keep track of files that need saving
            st.session_state.files_to_save = set(results.keys())
            # Create a deep copy for editable data
            st.session_state.edited_data = {k: deepcopy(v) for k, v in results.items()}
            st.success("Processing completed!")
            st.session_state.current_file_index = 0
            st.rerun() # Rerun to display the review section

    # Step 2: Review and Edit Results
    if st.session_state.processed_data:
        st.header("2. Review Extracted Data")
        filenames = list(st.session_state.processed_data.keys())
        idx = st.session_state.current_file_index
        current_file = filenames[idx]
        current_data = st.session_state.processed_data[current_file]
        
        # Display the status of the currently viewed file
        status_info = st.session_state.processing_status.get(current_file, {'status': 'Unknown', 'message': ''})
        status_class = "success" if status_info['status'] == "Completed" else "error" if status_info['status'] == "Error" else "processing"
        st.markdown(f"""
        <div class="file-card" style="margin-bottom: 20px;">
            <strong>Current File:</strong> {current_file} - 
            <span class="{status_class}">{status_info['status']}</span>
            {f"<br><small>{status_info['message']}</small>" if status_info['message'] else ""}
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation buttons for cycling through files
        col1, col2, col3, col4 = st.columns([1,1,2,1])
        with col1:
            if st.button("⏮ Previous") and idx > 0:
                st.session_state.current_file_index -= 1
                st.rerun()
        with col2:
            if st.button("Next ⏭") and idx < len(filenames)-1:
                st.session_state.current_file_index += 1
                st.rerun()
        with col3:
            st.write(f"File {idx+1} of {len(filenames)}") # Display current file number
        with col4:
            # Button to mark processing as complete and show final screen
            if st.button("Finish Processing"):
                st.session_state.processing_completed = True
                st.rerun()
        
        # Display PDF and Extracted Data side-by-side
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("Original Invoice")
            # Construct path to the temporary PDF file
            pdf_path = os.path.join(st.session_state.temp_dir, current_file)
            # Read PDF, encode to base64, and embed in an iframe for display
            with open(pdf_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            
            pdf_display = f"""
            <div class="pdf-container-wrapper">
                <iframe class="pdf-iframe" src="data:application/pdf;base64,{base64_pdf}"></iframe>
            </div>
            """
            st.markdown(pdf_display, unsafe_allow_html=True)
        
        with col_right:
            st.subheader("Extracted Data")
            # Display and allow editing of the extracted data
            edited_data = display_extracted_data(current_data, current_file)
            
            # Show last save confirmation if the current file was recently saved
            if st.session_state.last_saved_file == current_file and st.session_state.last_save_time:
                st.markdown(f"""
                <div class="save-confirmation">
                    ✅ Last saved at {st.session_state.last_save_time}
                </div>
                """, unsafe_allow_html=True)
            
            # Button to save the currently edited file
            if st.button("💾 Save Current File", key=f"save_{current_file}"):
                if save_data(current_file, edited_data):
                    st.success(f"✅ '{current_file}' saved successfully!")
                    st.rerun() # Rerun to update the save confirmation message

if __name__ == "__main__":
    main()