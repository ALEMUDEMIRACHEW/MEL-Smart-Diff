import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from docx import Document
import io
import re
from datetime import datetime

# --- 1. Page & Security Configuration ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Password Protection: Looks for 'APP_PASSWORD' in Streamlit Secrets. 
# Defaults to 'admin123' if not set in the dashboard.
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123") 

# --- 2. Sidebar Access Control & History ---
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter App Password", type="password")
    
    st.divider()
    if "history" not in st.session_state:
        st.session_state.history = []
        
    st.header("📜 Session History")
    if st.session_state.history:
        for idx, item in enumerate(reversed(st.session_state.history)):
            with st.expander(f"{item['time']} - {item['files']}"):
                st.markdown(item['result'])
    else:
        st.write("No comparisons in this session.")

# --- 3. Login Gate ---
# If password doesn't match, stop execution here.
if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Please enter the correct App Password in the sidebar to unlock the tool.")
    st.stop()

# --- 4. Main App Logic (Only visible after login) ---
st.title("🔍 Smart-Diff Pro")
st.caption("Advanced Semantic Document Auditor powered by Gemini 1.5 Flash")

# API Key Retrieval
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    with st.sidebar:
        api_key = st.text_input("Enter Gemini API Key", type="password")
        st.info("Get a key at aistudio.google.com")

# --- Helper Functions ---
def clean_text(text):
    """Removes noise and excessive whitespace to save tokens."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_text(uploaded_file):
    """Extracts text from PDF or DOCX."""
    try:
        if uploaded_file.name.endswith('.pdf'):
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            return clean_text("\n".join([page.get_text() for page in doc]))
        elif uploaded_file.name.endswith('.docx'):
            doc = Document(io.BytesIO(uploaded_file.read()))
            return clean_text("\n".join([para.text for para in doc]))
    except Exception as e:
        st.error(f"Error parsing {uploaded_file.name}: {e}")
    return ""

def analyze_diffs(text_a, text_b, key):
    """Sends text to Gemini with high-precision system instructions."""
    genai.configure(api_key=key)
    
    system_instr = """
    ROLE: Professional Document Auditor.
    OBJECTIVE: Conduct a high-precision semantic comparison.
    
    STRICT RULES:
    1. Ignore all formatting, page numbers, and headers/footers.
    2. Identify 🟢[ADDITIONS], 🔴[ELIMINATIONS], 🟠[MODIFICATIONS], 🔵[DISPLACEMENTS].
    3. For Modifications, show 'Old Value -> New Value'.
    4. Be technical and concise. No fluff.
    """

    # FIX: Using 'models/gemini-1.5-flash' to prevent 404 errors
    model = genai.GenerativeModel(
        model_name='models/gemini-1.5-flash',
        system_instruction=system_instr,
        generation_config={"temperature": 0, "max_output_tokens": 4096}
    )
    
    prompt = f"AUDIT TASK:\n\nORIGINAL (A):\n{text_a}\n\nREVISED (B):\n{text_b}"
    response = model.generate_content(prompt)
    return response.text

# --- 5. Main UI Layout ---
col1, col2 = st.columns(2)

with col1:
    file_a = st.file_uploader("Upload File A (Original)", type=['pdf', 'docx'])

with col2:
    file_b = st.file_uploader("Upload File B (Revised)", type=['pdf', 'docx'])

if st.button("🚀 Run Semantic Analysis"):
    if not api_key:
        st.error("Missing API Key. Provide it in the sidebar or Streamlit Secrets.")
    elif file_a and file_b:
        with st.spinner("Analyzing semantic differences..."):
            # Extraction & Limit (35k chars for max precision)
            raw_a = extract_text(file_a)[:35000]
            raw_b = extract_text(file_b)[:35000]
            
            try:
                report = analyze_diffs(raw_a, raw_b, api_key)
                
                # Save to History
                timestamp = datetime.now().strftime("%H:%M:%S")
                st.session_state.history.append({
                    "time": timestamp,
                    "files": f"{file_a.name} vs {file_b.name}",
                    "result": report
                })
                
                # Display Current Result
                st.divider()
                st.subheader("📋 Audit Report")
                st.markdown(report)
                
                st.download_button(
                    "📥 Download Report (.md)", 
                    report, 
                    file_name=f"audit_{timestamp}.md"
                )
                
            except Exception as e:
                st.error(f"Analysis Failed: {str(e)}")
    else:
        st.warning("Please upload both files to proceed.")