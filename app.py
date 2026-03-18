import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import re
from datetime import datetime

# --- 1. CONFIGURATION & SECURITY ---
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

# --- 2. LOGIN GATE ---
if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Locked. Please enter the App Password in the sidebar to unlock.")
    st.stop()

# --- 3. UNLOCKED AUDIT TOOL ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Enterprise Auditor | Gemini 3.1 Flash")

api_key = st.secrets.get("GEMINI_API_KEY")

def extract_text(uploaded_file):
    try:
        if uploaded_file.name.endswith('.pdf'):
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            text = "\n".join([page.get_text() for page in doc])
        else:
            doc = Document(io.BytesIO(uploaded_file.read()))
            text = "\n".join([para.text for para in doc])
        return re.sub(r'\s+', ' ', text).strip()
    except Exception as e:
        st.error(f"File Error: {e}")
        return ""

def run_audit(text_a, text_b, key):
    # NEW 2026 CLIENT ARCHITECTURE
    client = genai.Client(api_key=key)
    
    config = types.GenerateContentConfig(
        system_instruction="You are a Professional Document Auditor. Compare File A and B. Identify 🟢[ADD], 🔴[DEL], 🟠[MOD], 🔵[MOVE]. Ignore formatting.",
        temperature=0.0
    )
    
    # USING THE LATEST MARCH 2026 MODEL ID
    model_id = "gemini-3.1-flash-preview"
    
    prompt = f"AUDIT TASK:\n\nORIGINAL (A):\n{text_a}\n\nREVISED (B):\n{text_b}"
    
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=config
    )
    return response.text

# UI Layout
col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Upload Original", type=['pdf', 'docx'])
with col2:
    file_b = st.file_uploader("Upload Revised", type=['pdf', 'docx'])

if st.button("🚀 Run Semantic Audit"):
    if not api_key:
        st.error("API Key missing in Secrets.")
    elif file_a and file_b:
        with st.spinner("Analyzing changes via Gemini 3.1..."):
            raw_a = extract_text(file_a)[:35000]
            raw_b = extract_text(file_b)[:35000]
            
            try:
                report = run_audit(raw_a, raw_b, api_key)
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
                # Direct error printing to catch any API handshake issues
                st.error(f"Handshake Error: {e}")
    else:
        st.warning("Upload two files first.")