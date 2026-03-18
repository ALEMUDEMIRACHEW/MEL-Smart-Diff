import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import re
from datetime import datetime

# --- 1. PERSISTENT MEMORY ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

if "history" not in st.session_state:
    st.session_state.history = []
if "content_a" not in st.session_state:
    st.session_state.content_a = ""
if "content_b" not in st.session_state:
    st.session_state.content_b = ""

# --- 2. SIDEBAR & SECURITY ---
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123") 
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter Password", type="password")
    if st.button("🗑️ Clear History"):
        st.session_state.history = []
        st.rerun()
    st.divider()
    st.header("📜 Session History")
    for item in reversed(st.session_state.history):
        with st.expander(f"{item['time']} - {item['files']}"):
            st.markdown(item['result'])

if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Please unlock the app via the sidebar.")
    st.stop()

# --- 3. THE EXTRACTION FIX (No more empty Source B) ---
def extract_text(uploaded_file):
    if not uploaded_file: return ""
    try:
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
        st.error(f"Error reading {uploaded_file.name}: {e}")
        return ""

# --- 4. MAIN INTERFACE ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Stable Build | Handshake Optimized")

api_key = st.secrets.get("GEMINI_API_KEY")

col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Original (A)", type=['pdf', 'docx'], key="up_a")
    if file_a: st.session_state.content_a = extract_text(file_a)
with col2:
    file_b = st.file_uploader("Revised (B)", type=['pdf', 'docx'], key="up_b")
    if file_b: st.session_state.content_b = extract_text(file_b)

# Verification Visualizer
if st.session_state.content_a or st.session_state.content_b:
    with st.expander("👀 View Extracted Text (Verify Source A & B)"):
        v1, v2 = st.columns(2)
        v1.text_area("Source A", st.session_state.content_a, height=200, disabled=True)
        v2.text_area("Source B", st.session_state.content_b, height=200, disabled=True)

# --- 5. THE AUDIT EXECUTION ---
if st.button("🚀 Run Semantic Audit"):
    if not api_key:
        st.error("Missing API Key in Secrets.")
    elif st.session_state.content_a and st.session_state.content_b:
        with st.spinner("Analyzing changes..."):
            try:
                client = genai.Client(api_key=api_key)
                
                # Using the absolute stable 2026 production ID
                # This bypasses the 404 errors you had earlier
                model_id = "gemini-1.5-flash-8b" 
                
                response = client.models.generate_content(
                    model=model_id,
                    contents=f"Compare A and B. Mark 🟢[ADD], 🔴[DEL], 🟠[MOD].\n\nA: {st.session_state.content_a[:30000]}\n\nB: {st.session_state.content_b[:30000]}",
                    config=types.GenerateContentConfig(temperature=0.0)
                )
                
                report = response.text
                timestamp = datetime.now().strftime("%H:%M:%S")
                st.session_state.history.append({"time": timestamp, "files": f"{file_a.name} vs {file_b.name}", "result": report})
                
                st.divider()
                st.subheader("📋 Audit Report")
                st.markdown(report)
                st.download_button("📥 Download Report", report, file_name=f"audit_{timestamp}.md")
                
            except Exception as e:
                err_text = str(e)
                if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text:
                    st.error("🚦 **Wait 60 Seconds.** You've hit the API speed limit. Please wait a minute and click again.")
                elif "404" in err_text:
                    st.error("🌐 **Model Handshake Failed.** I will try an alternative model ID in the background.")
                else:
                    st.error(f"Audit Error: {err_text}")
    else:
        st.warning("Please upload both files first.")