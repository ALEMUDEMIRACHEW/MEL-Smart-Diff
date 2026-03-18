import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from docx import Document
import io

# --- Page Configuration ---
st.set_page_config(page_title="MEL-Smart-Diff", layout="wide", page_icon="✈️")

st.title("✈️ MEL-Smart-Diff")
st.markdown("### AI-Powered Semantic Comparison for Aviation Documents")

# --- Sidebar: API Configuration ---
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Google Gemini API Key", type="password")
    st.info("Get a free key at [aistudio.google.com](https://aistudio.google.com/)")
    
    st.divider()
    st.markdown("""
    **Legend:**
    - 🟢 **Added:** New requirements/items.
    - 🔴 **Eliminated:** Removed from Master.
    - 🟠 **Modified/Displaced:** Content moved or changed.
    """)

# --- Helper Functions ---
def extract_text(uploaded_file):
    if uploaded_file.name.endswith('.pdf'):
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        return "\n".join([page.get_text() for page in doc])
    elif uploaded_file.name.endswith('.docx'):
        doc = Document(io.BytesIO(uploaded_file.read()))
        return "\n".join([para.text for para in doc])
    return ""

def analyze_diffs(master_text, operator_text, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an Aviation Regulatory Auditor. Compare the following two document excerpts:
    
    FILE A (MMEL - Master):
    {master_text} 
    
    FILE B (OMEL - Operator):
    {operator_text}
    
    TASK: Identify semantic differences. Ignore formatting, page numbers, and headers/footers.
    Focus on:
    1. Additions: New items or stricter requirements in File B.
    2. Eliminations: Items in File A missing from File B.
    3. Displacements: Content moved to incorrect ATA chapters or sections.
    4. Modifications: Changes in wording, numbers, or rectification intervals (A, B, C, D).
    
    OUTPUT FORMAT: Return a structured Markdown report. Use 🟢 for Additions, 🔴 for Eliminations, and 🟠 for Modifications/Displacements.
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- Main UI ---
col1, col2 = st.columns(2)

with col1:
    file_a = st.file_uploader("Upload File A: MMEL (Master)", type=['pdf', 'docx'])

with col2:
    file_b = st.file_uploader("Upload File B: OMEL (Customized)", type=['pdf', 'docx'])

if st.button("🚀 Run Smart Analysis"):
    if not api_key:
        st.error("Please enter your Gemini API Key in the sidebar.")
    elif file_a and file_b:
        with st.spinner("AI is analyzing documents for semantic differences..."):
            try:
                # 1. Extract
                text_a = extract_text(file_a)
                text_b = extract_text(file_b)
                
                # 2. Analyze (Using Gemini)
                report = analyze_diffs(text_a, text_b, api_key)
                
                # 3. Display Result
                st.divider()
                st.subheader("Comparison Report")
                st.markdown(report)
                
                # Download Option
                st.download_button("Download Report", report, file_name="MEL_Diff_Report.md")
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
    else:
        st.warning("Please upload both files to proceed.")