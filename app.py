import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import re
from datetime import datetime

# --- 1. CONFIGURATION & PERSISTENT STATE ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Password Security
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123") 

# Initialize storage for history and extracted text
if "history" not in st.session_state:
    st.session_state.history = []
if "extracted_a" not in st.session_state:
    st.session_state.extracted_a = ""
if "extracted_b" not in st.session_state:
    st.session_state.extracted_b = ""

with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter App Password", type="password")
    st.divider()
    st.header("📜 Session History")
    if st.session_state.history:
        for item in reversed(st.session_state.history):
            with st.expander(f"{item['time']} - {item['files']}"):
                st.markdown(item['result'])
    else:
        st.caption("No recent audits.")

# --- 2. LOGIN GATE ---
if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Locked. Please enter the App Password in the sidebar.")
    st.stop()

# --- 3. CORE LOGIC ---
api_key = st.secrets.get("GEMINI_API_KEY")

def extract_text_safely(uploaded_file):
    """Extracts text once and handles file pointer resets to prevent 404/Empty errors."""
    if not uploaded_file:
        return ""
    try:
        uploaded_file.seek(0) # Reset pointer to start
        file_bytes = uploaded_file.read()
        
        if uploaded_file.name.endswith('.pdf'):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n".join([page.get_text() for page in doc])
        else:
            doc = Document(io.BytesIO(file_bytes))
            text = "\n".join([para.text for para in doc])
            
        return re.sub(r'\s+', ' ', text).strip()
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {e}")
        return ""

def run_audit(text_a, text_b, key):
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction="Compare File A and B. Identify 🟢[ADD], 🔴[DEL], 🟠[MOD], 🔵[MOVE]. Ignore formatting changes. Focus on technical data.",
        temperature=0.0
    )
    # Using the most stable 2026 production-ready model
    model_id = "gemini-2.0-flash" 
    
    prompt = f"AUDIT TASK:\n\nORIGINAL (A):\n{text_a}\n\nREVISED (B):\n{text_b}"
    response = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return response.text

# --- 4. UI DESIGN ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Engineering Edition | Safe-Stream Architecture")

col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Upload Original (A)", type=['pdf', 'docx'], key="u_a")
with col2:
    file_b = st.file_uploader("Upload Revised (B)", type=['pdf', 'docx'], key="u_b")

# Update extracted text state only when files change
if file_a:
    st.session_state.extracted_a = extract_text_safely(file_a)
if file_b:
    st.session_state.extracted_b = extract_text_safely(file_b)

# Visualizer (Using the persistent state)
if st.session_state.extracted_a or st.session_state.extracted_b:
    with st.expander("👀 View Extracted Raw Text (Side-by-Side Review)"):
        v_col1, v_col2 = st.columns(2)
        with v_col1:
            st.info("Source A")
            st.text_area("A_Content", st.session_state.extracted_a, height=200, disabled=True, label_visibility="collapsed")
        with v_col2:
            st.info("Source B")
            st.text_area("B_Content", st.session_state.extracted_b, height=200, disabled=True, label_visibility="collapsed")

# --- 5. EXECUTION ---
if st.button("🚀 Run Semantic Audit"):
    if not api_key:
        st.error("API Key missing in Secrets.")
    elif st.session_state.extracted_a and st.session_state.extracted_b:
        with st.spinner("Analyzing maintenance logic..."):
            try:
                # Use pre-extracted text to avoid "Empty Stream" errors
                report = run_audit(st.session_state.extracted_a[:40000], st.session_state.extracted_b[:40000], api_key)
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                st.session_state.history.append({
                    "time": timestamp,
                    "files": f"{file_a.name} vs {file_b.name}",
                    "result": report
                })
                
                st.divider()
                st.subheader("📋 Audit Report")
                st.markdown(report)
                st.download_button("📥 Save Audit (.md)", report, file_name=f"audit_{timestamp}.md")
            except Exception as e:
                st.error(f"Audit Failed: {e}")
    else:
        st.warning("Please upload both files to begin.")