import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import re
from datetime import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123") 

if "history" not in st.session_state:
    st.session_state.history = []

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

# --- 2. SECURITY GATE ---
if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Locked. Enter the password in the sidebar to unlock.")
    st.stop()

# --- 3. AUDIT TOOL ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Enterprise Auditor | Stable Build")

api_key = st.secrets.get("GEMINI_API_KEY")

def extract_text(uploaded_file):
    """Safely extracts text and resets file pointer to prevent empty stream errors."""
    try:
        # Reset file pointer to the beginning
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        if uploaded_file.name.endswith('.pdf'):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n".join([page.get_text() for page in doc])
        else:
            doc = Document(io.BytesIO(file_bytes))
            text = "\n".join([para.text for para in doc])
            
        return re.sub(r'\s+', ' ', text).strip()
    except Exception as e:
        st.error(f"Extraction Error: {e}")
        return ""

def run_audit(text_a, text_b, key):
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction="Compare File A and B. Identify 🟢[ADD], 🔴[DEL], 🟠[MOD], 🔵[MOVE]. Ignore formatting. Focus on data/logic.",
        temperature=0.0
    )
    # Using the stable 2026 production model
    model_id = "gemini-2.0-flash" 
    
    prompt = f"AUDIT TASK:\n\nORIGINAL (A):\n{text_a}\n\nREVISED (B):\n{text_b}"
    response = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return response.text

# --- UI LAYOUT ---
col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Upload Original (A)", type=['pdf', 'docx'], key="file_a")
with col2:
    file_b = st.file_uploader("Upload Revised (B)", type=['pdf', 'docx'], key="file_b")

# Extract text once to avoid multiple reads
content_a = extract_text(file_a) if file_a else ""
content_b = extract_text(file_b) if file_b else ""

if file_a or file_b:
    with st.expander("👀 View Extracted Raw Text (Side-by-Side Review)"):
        v_col1, v_col2 = st.columns(2)
        with v_col1:
            st.info(f"Source A: {file_a.name if file_a else 'Empty'}")
            st.text_area("A", content_a, height=200, disabled=True, key="area_a")
        with v_col2:
            st.info(f"Source B: {file_b.name if file_b else 'Empty'}")
            st.text_area("B", content_b, height=200, disabled=True, key="area_b")

if st.button("🚀 Run Semantic Audit"):
    if not api_key:
        st.error("API Key missing.")
    elif content_a and content_b:
        with st.spinner("Analyzing..."):
            try:
                # Use the pre-extracted content
                report = run_audit(content_a[:35000], content_b[:35000], api_key)
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                st.session_state.history.append({
                    "time": timestamp,
                    "files": f"{file_a.name} vs {file_b.name}",
                    "result": report
                })
                
                st.divider()
                st.subheader("📋 Audit Report")
                st.markdown(report)
                st.download_button("📥 Download (.md)", report, file_name=f"audit_{timestamp}.md")
            except Exception as e:
                st.error(f"API Error: {e}")
    else:
        st.warning("Please upload both files.")