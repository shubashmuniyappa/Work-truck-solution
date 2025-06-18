import os
import json
import tempfile
import streamlit as st
from main import InvoiceProcessor
import base64
import shutil
from copy import deepcopy
from datetime import datetime

# Set page config with blue theme
st.set_page_config(
    page_title="Auto Invoice Processor",
    page_icon=":car:",
    layout="wide"
)

# Custom CSS for blue theme styling with improved upload section
st.markdown("""
    <style>
    /* ===== Main App Styles ===== */
    .stApp {
        background-color: #e6f2ff;  /* Light blue background */
    }
    
    /* ===== Typography ===== */
    h1, h2, h3, h4, h5, h6 {
        color: #003366 !important;  /* Dark blue headers */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #333333;
    }
    
    /* ===== Upload Section ===== */
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
    
    .stFileUploader>div>div>div>div>span {
        color: #003366 !important;
        font-weight: bold;
        font-size: 1.1rem;
    }
    
    .stFileUploader>div>div>div>div>small {
        color: #666666 !important;
        font-size: 0.9rem;
    }
    
    /* ===== Buttons ===== */
    .stButton>button {
        background: linear-gradient(135deg, #1e90ff, #0066cc);
        color: white !important;
        border-radius: 8px;
        padding: 0.6rem 1.6rem;
        border: none;
        font-weight: bold;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        font-size: 0.95rem;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #0066cc, #004d99);
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* ===== File Cards ===== */
    .file-card {
        padding: 1.2rem;
        border-radius: 8px;
        background-color: white;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        border-left: 4px solid #1e90ff;
        transition: all 0.3s ease;
    }
    
    .file-card:hover {
        transform: translateX(3px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    
    /* ===== Status Indicators ===== */
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
    
    /* ===== Containers ===== */
    .pdf-container {
        height: 600px;
        border: 2px solid #b3d9ff;
        border-radius: 10px;
        background-color: white;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
    }
    
    .pdf-iframe {
        width: 100%;
        height: 600px;
        border: none;
    }
    
    .data-container {
        height: 600px;
        overflow-y: auto;
        padding: 20px;
        background-color: white;
        border-radius: 10px;
        border: 2px solid #b3d9ff;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
    }
    
    /* ===== Expanders ===== */
    .streamlit-expanderHeader {
        background-color: #cce6ff !important;
        border-radius: 8px !important;
        padding: 0.7rem 1.2rem !important;
        font-weight: bold !important;
        color: #003366 !important;
    }
    
    .streamlit-expanderContent {
        background-color: #f5faff !important;
        border-radius: 0 0 8px 8px !important;
        padding: 1.2rem !important;
    }
    
    /* ===== Input Fields ===== */
    /* Text inputs */
    .stTextInput>div>div>input {
        background-color: white !important;
        border: 1px solid #99ccff !important;
        border-radius: 6px !important;
        color: #003366 !important;
        padding: 8px 12px !important;
    }
    
    .stTextInput>div>div>input:focus {
        border: 1px solid #0066cc !important;
        box-shadow: 0 0 0 2px rgba(0,102,204,0.2) !important;
    }
    
    /* Select boxes */
    .stSelectbox>div>div>select {
        background-color: white !important;
        border: 1px solid #99ccff !important;
        border-radius: 6px !important;
        color: #003366 !important;
        padding: 8px 12px !important;
    }
    
    /* Text areas */
    .stTextArea>div>div>textarea {
        background-color: white !important;
        border: 1px solid #99ccff !important;
        border-radius: 6px !important;
        color: #003366 !important;
        padding: 8px 12px !important;
    }
    
    /* Number inputs */
    .stNumberInput>div>div>input {
        background-color: white !important;
        border: 1px solid #99ccff !important;
        border-radius: 6px !important;
        color: #003366 !important;
        padding: 8px 12px !important;
    }
    
    /* Date inputs */
    .stDateInput>div>div>input {
        background-color: white !important;
        border: 1px solid #99ccff !important;
        border-radius: 6px !important;
        color: #003366 !important;
        padding: 8px 12px !important;
    }
    
    /* ===== Progress Bar ===== */
    .stProgress>div>div>div {
        background: linear-gradient(90deg, #1e90ff, #66b3ff) !important;
        border-radius: 4px;
    }
    
    /* ===== Section Headers ===== */
    .section-header {
        background: linear-gradient(90deg, #cce6ff, #e6f2ff);
        padding: 12px 18px;
        border-radius: 8px;
        margin-bottom: 18px;
        border-left: 5px solid #0066cc;
        font-weight: bold;
    }
    
    /* ===== Tooltips ===== */
    .stTooltip {
        background-color: #003366 !important;
        color: white !important;
        border-radius: 6px !important;
    }
    
    /* ===== Dataframe Styling ===== */
    .stDataFrame {
        border-radius: 8px !important;
        border: 1px solid #b3d9ff !important;
    }
    
    /* ===== Radio Buttons ===== */
    .stRadio>div>div>label>div {
        color: #003366 !important;
    }
    
    /* ===== Checkboxes ===== */
    .stCheckbox>div>div>label>div {
        color: #003366 !important;
    }
    
    /* ===== Sliders ===== */
    .stSlider>div>div>div>div {
        background-color: #1e90ff !important;
    }
    
    /* ===== Sidebar (if used) ===== */
    [data-testid="stSidebar"] {
        background-color: #003366 !important;
    }
    
    [data-testid="stSidebar"] .stButton>button {
        background: linear-gradient(135deg, #66b3ff, #1e90ff);
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
    """Display extracted data with dynamic attribute editing capabilities"""
    # Initialize edited data for this file if not exists
    if filename not in st.session_state.edited_data:
        st.session_state.edited_data[filename] = enforce_json_structure({**data, "filename": filename})
    
    edited_data = st.session_state.edited_data[filename]
    
    st.subheader("Extracted Data")
    
    with st.container():
        # Basic Information
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
        
        # Body Information
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
        
        # Distributor Information
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
        
        # Invoice Information
        with st.expander("Invoice Information"):
            edited_data['invoice_date'] = st.text_input(
                "Invoice Date", 
                edited_data.get('invoice_date', ''),
                key=f"{filename}_invoice_date"
            )
        
        # Components Section with dynamic editing
        st.subheader("Components")
        
        # Add New Component Button
        if st.button("➕ Add New Component", key=f"{filename}_add_component"):
            if 'components' not in edited_data:
                edited_data['components'] = []
            edited_data['components'].append({
                'name': 'New Component',
                'attributes': [{'name': 'New Attribute', 'value': ''}]
            })
            st.rerun()
        
        # Display and edit existing components
        if 'components' in edited_data and edited_data['components']:
            for i, component in enumerate(edited_data['components']):
                with st.expander(f"Component {i+1}: {component.get('name', 'Unnamed')}"):
                    # Component name editing
                    component['name'] = st.text_input(
                        "Component Name",
                        component.get('name', ''),
                        key=f"{filename}_comp_{i}_name"
                    )
                    
                    # Attributes section header
                    st.markdown("**Attributes**")
                    
                    # Display and edit existing attributes
                    if 'attributes' in component and component['attributes']:
                        for j, attr in enumerate(component['attributes']):
                            # Create columns for attribute name and delete button
                            col_name, col_del = st.columns([4, 1])
                            
                            with col_name:
                                # Attribute name editing
                                attr['name'] = st.text_input(
                                    "Attribute Name",
                                    attr.get('name', ''),
                                    key=f"{filename}_comp_{i}_attr_{j}_name"
                                )
                            
                            with col_del:
                                # Spacer for vertical alignment
                                st.write("")
                                # Delete button (trash icon only)
                                if st.button("🗑️", 
                                            key=f"{filename}_comp_{i}_attr_{j}_delete"):
                                    component['attributes'].pop(j)
                                    st.rerun()
                            
                            # Attribute value (full width below name+delete)
                            attr['value'] = st.text_input(
                                "Value",
                                attr.get('value', ''),
                                key=f"{filename}_comp_{i}_attr_{j}_value"
                            )
                            
                            # Divider between attributes (except after last one)
                            if j < len(component['attributes']) - 1:
                                st.markdown("---")
                    
                    # Add Attribute Button at the bottom of attributes section
                    if st.button("➕ Add Attribute", 
                                key=f"{filename}_comp_{i}_add_attr"):
                        if 'attributes' not in component:
                            component['attributes'] = []
                        component['attributes'].append({'name': 'New Attribute', 'value': ''})
                        st.rerun()
                    
                    # Delete component button at the bottom
                    if st.button("🗑️ Delete Component", 
                                key=f"{filename}_comp_{i}_delete"):
                        edited_data['components'].pop(i)
                        st.rerun()
    
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
            if st.button("Finish Processing"):
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