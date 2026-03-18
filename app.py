import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import re
from datetime import datetime
import time # Added for wait logic

# --- 1. MEMORY SETUP ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

if "history" not in st.session_state:
    st.session_state.history = []
if "content_a" not in st.session_state:
    st.session_state.content_a = ""
if "content_b" not in st.session_state:
    st.session_state.content_b = ""

# --- 2. SIDEBAR SECURITY ---
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123") 
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter Password", type="password")
    if st.button("🗑️ Reset All"):
        st.session_state.content_a = ""
        st.session_state.content_b = ""
        st.session_state.history = []
        st.rerun()
    st.divider()
    st.header("📜 Session History")
    for item in reversed(st.session_state.history):
        with st.expander(f"{item['time']} - {item['files']}"):
            st.markdown(item['result'])

if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Please unlock in the sidebar.")
    st.stop()

# --- 3. EXTRACTION (Source B Fix) ---
def get_text(uploaded_file):
    if not uploaded_file: return ""
    try:
        uploaded_file.seek(0)
        fb = uploaded_file.read()
        if uploaded_file.name.endswith('.pdf'):
            doc = fitz.open(stream=fb, filetype="pdf")
            text = "\n".join([page.get_text() for page in doc])
        else:
            doc = Document(io.BytesIO(fb))
            text = "\n".join([para.text for para in doc])
        return re.sub(r'\s+', ' ', text).strip()
    except Exception as e:
        st.error(f"Read Error: {e}")
        return ""

# --- 4. UI ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Enterprise Auditor | Auto-Retry Enabled")

api_key = st.secrets.get("GEMINI_API_KEY")

col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Original (A)", type=['pdf', 'docx'], key="ua")
    if file_a: st.session_state.content_a = get_text(file_a)
with col2:
    file_b = st.file_uploader("Revised (B)", type=['pdf', 'docx'], key="ub")
    if file_b: st.session_state.content_b = get_text(file_b)

if st.session_state.content_a or st.session_state.content_b:
    with st.expander("👀 Verify Extracted Content", expanded=True):
        v1, v2 = st.columns(2)
        v1.text_area("A", st.session_state.content_a, height=200, disabled=True)
        v2.text_area("B", st.session_state.content_b, height=200, disabled=True)

# --- 5. THE AUTO-RETRY AUDIT ---
if st.button("🚀 Run Semantic Audit"):
    if not api_key:
        st.error("Missing API Key.")
    elif st.session_state.content_a and st.session_state.content_b:
        status_box = st.empty()
        client = genai.Client(api_key=api_key)
        
        # We try these in order
        models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash"]
        success = False
        
        for model_id in models_to_try:
            if success: break
            
            # Auto-Retry Loop (3 attempts per model)
            for attempt in range(3):
                try:
                    status_box.info(f"Connecting to {model_id} (Attempt {attempt+1}/3)...")
                    response = client.models.generate_content(
                        model=model_id,
                        contents=f"Compare A and B. Mark 🟢[ADD], 🔴[DEL], 🟠[MOD].\n\nA: {st.session_state.content_a[:30000]}\n\nB: {st.session_state.content_b[:30000]}",
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    report = response.text
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    st.session_state.history.append({"time": timestamp, "files": f"{file_a.name} vs {file_b.name}", "result": report})
                    status_box.success(f"Audit Complete using {model_id}")
                    st.divider()
                    st.markdown(report)
                    success = True
                    break 
                except Exception as e:
                    err = str(e)
                    if "429" in err or "RESOURCE_EXHAUSTED" in err:
                        wait_time = (attempt + 1) * 10
                        status_box.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        status_box.error(f"{model_id} failed: {err}")
                        break # Try the next model
        
        if not success:
            st.error("❌ Critical: All model attempts failed. Please wait 2 minutes for the API quota to reset.")
    else:
        st.warning("Upload both files first.")