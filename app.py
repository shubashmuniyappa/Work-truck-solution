import os
import json
import tempfile
import streamlit as st
from main import InvoiceProcessor
import base64
import shutil
from copy import deepcopy
from datetime import datetime

# Set page config (same as before)
st.set_page_config(
    page_title="Vehicle Invoice Processing Portal",
    page_icon=":car:",
    layout="wide"
)

# Custom CSS for styling (same as before)
st.markdown("""
    <style>
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .file-card {
        padding: 1rem;
        border-radius: 5px;
        background-color: #f0f2f6;
        margin-bottom: 0.5rem;
    }
    .success {
        color: #4CAF50;
    }
    .error {
        color: #f44336;
    }
    .processing {
        color: #FFA500;
    }
    .header {
        color: #2c3e50;
    }
    .pdf-container {
        height: 600px;
        border: 1px solid #ddd;
        border-radius: 5px;
    }
    .pdf-iframe {
        width: 100%;
        height: 600px;
        border: none;
    }
    .data-container {
        height: 600px;
        overflow-y: auto;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state (same as before)
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

# Define the exact field order we want in the JSON output
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
    """Ensure the JSON output follows our exact required structure"""
    structured_data = {}
    
    # Add fields in the exact order we want
    for field in JSON_FIELD_ORDER:
        if field in data:
            structured_data[field] = data[field]
        else:
            # Provide appropriate defaults
            structured_data[field] = "" if field != "components" else []
    
    # Ensure components structure exists
    if "components" not in structured_data:
        structured_data["components"] = []
    
    # Ensure documents structure exists with current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    if "documents" not in structured_data or not isinstance(structured_data["documents"], list):
        structured_data["documents"] = [{
            "date": current_date,
            "type": "Invoice",
            "path": f"img/invoices/bodyinvoices/-/{data.get('filename', '')}"
        }]
    else:
        # Update existing document entry
        if not isinstance(structured_data["documents"][0], dict):
            structured_data["documents"][0] = {}
        structured_data["documents"][0]["date"] = current_date
        structured_data["documents"][0]["type"] = "Invoice"
        if "path" not in structured_data["documents"][0]:
            structured_data["documents"][0]["path"] = f"img/invoices/bodyinvoices/-/{data.get('filename', '')}"
    
    return structured_data

def display_extracted_data(data, filename):
    """Display extracted data in a user-friendly format (same UI as before)"""
    # Initialize edited data for this file if not exists
    if filename not in st.session_state.edited_data:
        st.session_state.edited_data[filename] = enforce_json_structure({**data, "filename": filename})
    
    edited_data = st.session_state.edited_data[filename]
    
    st.subheader("Extracted Data")
    
    with st.container():
        # Basic Information (same layout as before)
        with st.expander("Basic Information", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
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
        
        # Body Information (same layout as before)
        with st.expander("Body Information"):
            col1, col2 = st.columns(2)
            with col1:
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
        
        # Distributor Information (same layout as before)
        with st.expander("Distributor Information"):
            col1, col2 = st.columns(2)
            with col1:
                edited_data['distributor'] = st.text_input(
                    "Distributor", 
                    edited_data.get('distributor', ''),
                    key=f"{filename}_distributor"
                )
            with col2:
                edited_data['distributor_location'] = st.text_input(
                    "Distributor Location", 
                    edited_data.get('distributor_location', ''),
                    key=f"{filename}_distributor_location"
                )
        
        # Invoice Information (same layout as before)
        with st.expander("Invoice Information"):
            edited_data['invoice_date'] = st.text_input(
                "Invoice Date", 
                edited_data.get('invoice_date', ''),
                key=f"{filename}_invoice_date"
            )
        
        # Components (same layout as before)
        if 'components' in edited_data and edited_data['components']:
            st.subheader("Components")
            for i, component in enumerate(edited_data['components']):
                with st.expander(f"Component: {component.get('name', 'Unnamed')}"):
                    if 'attributes' in component and component['attributes']:
                        for j, attr in enumerate(component['attributes']):
                            attr['value'] = st.text_input(
                                f"{attr.get('name', 'Attribute')}", 
                                attr.get('value', ''),
                                key=f"{filename}_comp_{i}_attr_{j}"
                            )
    
    return edited_data

def save_data(filename, edited_data):
    """Save the processed data to JSON file with exact structure"""
    try:
        output_dir = "processed_output"
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
        
        # Enforce the JSON structure before saving
        structured_data = enforce_json_structure({**edited_data, "filename": filename})
        
        with open(output_path, "w") as f:
            json.dump(structured_data, f, indent=2)
        
        st.session_state.saved_files.append(output_path)
        st.success(f"Data for {filename} saved successfully to {output_path}!")
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

def save_all_data():
    """Save all processed files that haven't been saved yet"""
    if not st.session_state.processed_data:
        st.warning("No files to save!")
        return False
    
    success_count = 0
    with st.spinner("Saving all files..."):
        # Create a list copy to avoid modification during iteration
        files_to_save = list(st.session_state.files_to_save)
        
        for filename in files_to_save:
            if filename in st.session_state.edited_data:
                if save_data(filename, st.session_state.edited_data[filename]):
                    success_count += 1
                    # Remove from set after successful save
                    st.session_state.files_to_save.discard(filename)
    
    if success_count > 0:
        st.success(f"Successfully saved {success_count} file(s)!")
    return success_count > 0

def reset_processing():
    """Reset the processing state to allow new files"""
    st.session_state.processed_data = {}
    st.session_state.uploaded_files = []
    st.session_state.current_file_index = 0
    st.session_state.processing_status = {}
    st.session_state.edited_data = {}
    if st.session_state.temp_dir and os.path.exists(st.session_state.temp_dir):
        shutil.rmtree(st.session_state.temp_dir)
    st.session_state.temp_dir = None
    st.session_state.files_to_save = set()
    st.rerun()

def main():
    st.title("Vehicle Invoice Processing Portal")
    st.markdown("Transform complex vehicle invoices into organized, actionable information.")

    # Initialize processor
    processor = InvoiceProcessor()

    # Step 1: Invoice Upload
    st.header("1. Invoice Upload")
    
    # If we have processed files, show option to add more
    if st.session_state.processed_data:
        if st.button("Add More Files"):
            reset_processing()
            return
    
    uploaded_files = st.file_uploader(
        "Upload Invoice PDF(s)", 
        type="pdf", 
        accept_multiple_files=True,
        help="Drag and drop or click to upload PDF invoices"
    )

    if uploaded_files and not st.session_state.processed_data:
        st.session_state.uploaded_files = uploaded_files
        st.success(f"{len(uploaded_files)} file(s) uploaded successfully!")
        
        # Display file list
        st.subheader("Files to Process")
        for file in uploaded_files:
            st.markdown(f"""
            <div class="file-card">
                <strong>{file.name}</strong> - <span class="processing">Ready to Process</span>
            </div>
            """, unsafe_allow_html=True)

        # Process button
        if st.button("Start Processing", key="process_btn"):
            with st.spinner("Processing invoices..."):
                # Create temp directory if it doesn't exist
                if not st.session_state.temp_dir:
                    st.session_state.temp_dir = tempfile.mkdtemp()
                
                file_paths = []
                
                for file in uploaded_files:
                    file_path = os.path.join(st.session_state.temp_dir, file.name)
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())
                    file_paths.append(file_path)
                    st.session_state.processing_status[file.name] = "Processing"
                
                # Process files and enforce structure immediately
                results = processor.process_invoices(file_paths)
                structured_results = {}
                for filename, data in results.items():
                    structured_results[filename] = enforce_json_structure({**data, "filename": filename})
                
                st.session_state.processed_data = structured_results
                st.session_state.files_to_save = set(structured_results.keys())
                st.session_state.edited_data = {k: deepcopy(v) for k, v in structured_results.items()}
                
                # Update status
                for filename in structured_results:
                    st.session_state.processing_status[filename] = "Completed"
                
                st.success("Processing completed!")
                st.session_state.current_file_index = 0
                st.rerun()

    # Step 2: Processing Progress
    if st.session_state.get('processing_status'):
        st.header("2. Processing Status")
        
        for filename, status in st.session_state.processing_status.items():
            saved_status = " (Saved)" if filename not in st.session_state.files_to_save else ""
            status_class = "success" if status == "Completed" else "processing"
            st.markdown(f"""
            <div class="file-card">
                <strong>{filename}</strong> - <span class="{status_class}">{status}{saved_status}</span>
            </div>
            """, unsafe_allow_html=True)

    # Step 3: Results Display
    if st.session_state.processed_data:
        st.header("3. Review Extracted Data")
        
        # Navigation controls
        filenames = list(st.session_state.processed_data.keys())
        current_index = st.session_state.current_file_index
        current_filename = filenames[current_index]
        current_data = st.session_state.processed_data[current_filename]
        
        col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
        with col1:
            if st.button("⏮ Previous") and current_index > 0:
                st.session_state.current_file_index -= 1
                st.rerun()
        with col2:
            if st.button("Next ⏭") and current_index < len(filenames) - 1:
                st.session_state.current_file_index += 1
                st.rerun()
        with col3:
            st.write(f"File {current_index + 1} of {len(filenames)}: {current_filename}")
        with col4:
            if st.button("Finish & Reset"):
                reset_processing()
                return
        
        # Split view - properly aligned
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("Original Invoice")
            st.markdown(f'<div class="pdf-container"><iframe class="pdf-iframe" src="data:application/pdf;base64,{base64.b64encode(open(os.path.join(st.session_state.temp_dir, current_filename), "rb").read()).decode("utf-8")}"></iframe></div>', unsafe_allow_html=True)
        
        with col_right:
            st.subheader("Extracted Data")
            with st.container():
                edited_data = display_extracted_data(current_data, current_filename)
            
            # Save buttons
            col_save1, col_save2 = st.columns(2)
            with col_save1:
                if st.button("💾 Save Current File", key=f"save_{current_filename}"):
                    if save_data(current_filename, edited_data):
                        st.rerun()
            with col_save2:
                if st.button("💾 Save All Files", key="save_all"):
                    if save_all_data():
                        st.rerun()

    # Show saved files section
    if st.session_state.saved_files:
        st.header("Saved Files")
        for saved_file in st.session_state.saved_files:
            st.markdown(f"""
            <div class="file-card">
                <strong>{os.path.basename(saved_file)}</strong> - <span class="success">Saved</span>
                <br><small>{saved_file}</small>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()