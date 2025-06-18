import os
import json
import tempfile
import streamlit as st
from main import InvoiceProcessor
import base64
import shutil
from copy import deepcopy
from datetime import datetime

# Set page config with original blue theme
st.set_page_config(
    page_title="Auto Invoice Processor",
    page_icon=":car:",
    layout="wide"
)

# Updated CSS with improved PDF container styling
# Updated CSS with improved PDF container styling and white background for extracted text
st.markdown("""
    <style>
    /* ===== Main App Styles ===== */
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
    
    /* ===== Buttons ===== */
    .stButton>button {
        background: linear-gradient(135deg, #1e90ff, #0066cc);
        color: white !important;
        border-radius: 8px;
        padding: 0.6rem 1.6rem;
        border: none;
        font-weight: bold;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    /* ===== File Cards ===== */
    .file-card {
        padding: 1.2rem;
        border-radius: 8px;
        background-color: white;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        border-left: 4px solid #1e90ff;
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
    
    /* ===== PDF Container ===== */
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
    
    /* ===== Data Container ===== */
    .data-container {
        height: 600px;
        overflow-y: auto;
        padding: 20px;
        background-color: white;
        border-radius: 10px;
        border: 2px solid #b3d9ff;
    }
    
    /* ===== Extracted Text Elements ===== */
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
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
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

# Field order
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
    """Ensure JSON follows required structure"""
    structured_data = {}
    for field in JSON_FIELD_ORDER:
        structured_data[field] = data.get(field, "" if field != "components" else [])
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    if "documents" not in structured_data:
        structured_data["documents"] = [{
            "date": current_date,
            "type": "Invoice",
            "path": f"img/invoices/bodyinvoices/-/{data.get('filename', '')}"
        }]
    
    return structured_data

def display_extracted_data(data, filename):
    """Display and allow editing of extracted data"""
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
        
        # Components Section
        st.subheader("Components")
        
        if st.button("➕ Add New Component", key=f"{filename}_add_component"):
            if 'components' not in edited_data:
                edited_data['components'] = []
            edited_data['components'].append({
                'name': 'New Component',
                'attributes': [{'name': 'New Attribute', 'value': ''}]
            })
            st.rerun()
        
        if 'components' in edited_data:
            for i, component in enumerate(edited_data['components']):
                with st.expander(f"Component {i+1}: {component.get('name', 'Unnamed')}"):
                    component['name'] = st.text_input(
                        "Component Name",
                        component.get('name', ''),
                        key=f"{filename}_comp_{i}_name"
                    )
                    
                    st.markdown("**Attributes**")
                    
                    if 'attributes' in component:
                        for j, attr in enumerate(component['attributes']):
                            col_name, col_del = st.columns([4, 1])
                            with col_name:
                                attr['name'] = st.text_input(
                                    "Attribute Name",
                                    attr.get('name', ''),
                                    key=f"{filename}_comp_{i}_attr_{j}_name"
                                )
                            with col_del:
                                st.write("")
                                if st.button("🗑️", key=f"{filename}_comp_{i}_attr_{j}_delete"):
                                    component['attributes'].pop(j)
                                    st.rerun()
                            
                            attr['value'] = st.text_input(
                                "Value",
                                attr.get('value', ''),
                                key=f"{filename}_comp_{i}_attr_{j}_value"
                            )
                            
                            if j < len(component['attributes']) - 1:
                                st.markdown("---")
                    
                    if st.button("➕ Add Attribute", key=f"{filename}_comp_{i}_add_attr"):
                        if 'attributes' not in component:
                            component['attributes'] = []
                        component['attributes'].append({'name': 'New Attribute', 'value': ''})
                        st.rerun()
                    
                    if st.button("🗑️ Delete Component", key=f"{filename}_comp_{i}_delete"):
                        edited_data['components'].pop(i)
                        st.rerun()
    
    return edited_data

def save_data(filename, edited_data):
    """Save processed data to JSON file"""
    try:
        output_dir = "processed_output"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
        
        with open(output_path, "w") as f:
            json.dump(enforce_json_structure({**edited_data, "filename": filename}), f, indent=2)
        
        st.session_state.saved_files.append(output_path)
        st.session_state.files_to_save.discard(filename)
        st.success(f"Saved {filename} successfully!")
        return True
    except Exception as e:
        st.error(f"Error saving {filename}: {e}")
        return False

def save_all_data():
    """Save all processed files"""
    if not st.session_state.processed_data:
        st.warning("No files to save!")
        return False
    
    success_count = 0
    for filename in list(st.session_state.files_to_save):
        if save_data(filename, st.session_state.edited_data[filename]):
            success_count += 1
    
    if success_count > 0:
        st.success(f"Saved {success_count} file(s)!")
    return success_count > 0

def reset_processing():
    """Reset processing state"""
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

    processor = InvoiceProcessor()

    # Step 1: Upload
    st.header("1. Invoice Upload")
    if st.session_state.processed_data and st.button("Add More Files"):
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
        
        # Initialize status
        for file in uploaded_files:
            st.session_state.processing_status[file.name] = {
                'status': 'Ready to Process',
                'message': ''
            }

        # Display files
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

        if st.button("Start Processing", key="process_btn"):
            if not st.session_state.temp_dir:
                st.session_state.temp_dir = tempfile.mkdtemp()
            
            file_paths = []
            for file in uploaded_files:
                path = os.path.join(st.session_state.temp_dir, file.name)
                with open(path, "wb") as f:
                    f.write(file.getbuffer())
                file_paths.append(path)
            
            # Process files
            results = {}
            progress_bar = st.progress(0)
            for i, path in enumerate(file_paths):
                filename = os.path.basename(path)
                
                # Update status
                st.session_state.processing_status[filename] = {
                    'status': 'Processing',
                    'message': f'Processing file {i+1} of {len(file_paths)}'
                }
                progress_bar.progress(int((i+1)/len(file_paths)*100))
                
                # Update UI
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
                    # Process file using process_invoices()
                    file_results = processor.process_invoices([path])
                    if file_results and filename in file_results:
                        results[filename] = enforce_json_structure({
                            **file_results[filename],
                            "filename": filename
                        })
                        st.session_state.processing_status[filename] = {
                            'status': 'Completed',
                            'message': 'Extraction successful'
                        }
                    else:
                        raise Exception("No results returned")
                except Exception as e:
                    st.session_state.processing_status[filename] = {
                        'status': 'Error',
                        'message': f'Processing failed: {str(e)}'
                    }
                
                # Update UI
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
            
            st.session_state.processed_data = results
            st.session_state.files_to_save = set(results.keys())
            st.session_state.edited_data = {k: deepcopy(v) for k, v in results.items()}
            st.success("Processing completed!")
            st.session_state.current_file_index = 0
            st.rerun()

    # Step 2: Results
    if st.session_state.processed_data:
        st.header("2. Review Extracted Data")
        filenames = list(st.session_state.processed_data.keys())
        idx = st.session_state.current_file_index
        current_file = filenames[idx]
        current_data = st.session_state.processed_data[current_file]
        
        # Show current file status
        status_info = st.session_state.processing_status.get(current_file, {'status': 'Unknown', 'message': ''})
        status_class = "success" if status_info['status'] == "Completed" else "error" if status_info['status'] == "Error" else "processing"
        st.markdown(f"""
        <div class="file-card" style="margin-bottom: 20px;">
            <strong>Current File:</strong> {current_file} - 
            <span class="{status_class}">{status_info['status']}</span>
            {f"<br><small>{status_info['message']}</small>" if status_info['message'] else ""}
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation
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
            st.write(f"File {idx+1} of {len(filenames)}")
        with col4:
            if st.button("Finish Processing"):
                reset_processing()
                return
        
        # Display
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("Original Invoice")
            pdf_path = os.path.join(st.session_state.temp_dir, current_file)
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
            edited_data = display_extracted_data(current_data, current_file)
            
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                if st.button("💾 Save Current File", key=f"save_{current_file}"):
                    if save_data(current_file, edited_data):
                        st.rerun()
            with col_s2:
                if st.button("💾 Save All Files", key="save_all"):
                    if save_all_data():
                        st.rerun()

    # Saved files
    if st.session_state.saved_files:
        st.header("Saved Files")
        for path in st.session_state.saved_files:
            st.markdown(f"""
            <div class="file-card">
                <strong>{os.path.basename(path)}</strong> - 
                <span class="success">Saved</span>
                <br><small>{path}</small>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()