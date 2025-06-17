import os
import json
import tempfile
import streamlit as st
from main import InvoiceProcessor
from PIL import Image
import base64
import time

# Set page config
st.set_page_config(
    page_title="Vehicle Invoice Processing Portal",
    page_icon=":car:",
    layout="wide"
)

# Initialize session state
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = {}
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'current_file_index' not in st.session_state:
    st.session_state.current_file_index = 0
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = {}

# Custom CSS for styling
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
    </style>
    """, unsafe_allow_html=True)

def display_pdf(file_path):
    """Display PDF in Streamlit"""
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def display_extracted_data(data):
    """Display extracted data in a user-friendly format"""
    st.subheader("Extracted Data")
    
    # Basic Information
    with st.expander("Basic Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Inventory Arrival Date", data.get('inventory_arrival_date', ''))
            st.text_input("Stock Number", data.get('stock_number', ''))
            st.text_input("VIN", data.get('vin', ''))
            st.text_input("Condition", data.get('condition', ''))
        with col2:
            st.text_input("Model Year", data.get('model_year', ''))
            st.text_input("Make", data.get('make', ''))
            st.text_input("Model", data.get('model', ''))
    
    # Body Information
    with st.expander("Body Information"):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Body Type", data.get('body_type', ''))
            st.text_input("Body Line", data.get('body_line', ''))
        with col2:
            st.text_input("Body Manufacturer", data.get('body_manufacturer', ''))
            st.text_input("Body Model", data.get('body_model', ''))
    
    # Distributor Information
    with st.expander("Distributor Information"):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Distributor", data.get('distributor', ''))
        with col2:
            st.text_input("Distributor Location", data.get('distributor_location', ''))
    
    # Invoice Information
    with st.expander("Invoice Information"):
        st.text_input("Invoice Date", data.get('invoice_date', ''))
    
    # Components
    if data.get('components'):
        st.subheader("Components")
        for component in data['components']:
            with st.expander(f"Component: {component.get('name', 'Unnamed')}"):
                if component.get('attributes'):
                    for attr in component['attributes']:
                        st.text_input(f"{attr.get('name', 'Attribute')}", 
                                    attr.get('value', ''),
                                    key=f"{component['id']}_{attr['id']}")

def save_data(filename, data):
    """Save the processed data"""
    try:
        # In a real application, you would save to a database or file system
        # Here we'll just update the session state
        st.session_state.processed_data[filename] = data
        st.success(f"Data for {filename} saved successfully!")
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

def main():
    st.title("Vehicle Invoice Processing Portal")
    st.markdown("Transform complex vehicle invoices into organized, actionable information.")

    # Initialize processor
    processor = InvoiceProcessor()

    # Step 1: Invoice Upload
    st.header("1. Invoice Upload")
    uploaded_files = st.file_uploader(
        "Upload Invoice PDF(s)", 
        type="pdf", 
        accept_multiple_files=True,
        help="Drag and drop or click to upload PDF invoices"
    )

    if uploaded_files:
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
                # Save files temporarily
                temp_dir = tempfile.mkdtemp()
                file_paths = []
                
                for file in uploaded_files:
                    file_path = os.path.join(temp_dir, file.name)
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())
                    file_paths.append(file_path)
                    st.session_state.processing_status[file.name] = "Processing"
                
                # Process files
                results = processor.process_invoices(file_paths)
                st.session_state.processed_data = results
                
                # Update status
                for filename in results:
                    st.session_state.processing_status[filename] = "Completed"
                
                st.success("Processing completed!")
                st.session_state.current_file_index = 0

    # Step 2: Processing Progress
    if st.session_state.get('processing_status'):
        st.header("2. Processing Status")
        
        for filename, status in st.session_state.processing_status.items():
            status_class = "success" if status == "Completed" else "processing"
            st.markdown(f"""
            <div class="file-card">
                <strong>{filename}</strong> - <span class="{status_class}">{status}</span>
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
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("Previous") and current_index > 0:
                st.session_state.current_file_index -= 1
                st.rerun()
        with col2:
            if st.button("Next") and current_index < len(filenames) - 1:
                st.session_state.current_file_index += 1
                st.rerun()
        with col3:
            st.write(f"File {current_index + 1} of {len(filenames)}: {current_filename}")
        
        # Split view
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Original Invoice")
            # Display PDF (for demo, we'll just show the filename)
            # In a real app, you'd use a PDF viewer component
            st.warning("PDF viewer would be displayed here in production")
            st.write(f"Displaying: {current_filename}")
        
        with col2:
            display_extracted_data(current_data)
            
            # Save button
            if st.button("Save Data", key=f"save_{current_filename}"):
                save_data(current_filename, current_data)

if __name__ == "__main__":
    main()