import streamlit as st
from google import genai
from google.genai import types
import fitz
from docx import Document
import io
import re
from datetime import datetime
import time

# --- 1. PERSISTENCE LAYER ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

if "history" not in st.session_state:
    st.session_state.history = []
if "content_a" not in st.session_state:
    st.session_state.content_a = ""
if "content_b" not in st.session_state:
    st.session_state.content_b = ""

# --- 2. ACCESS CONTROL ---
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123") 
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter Password", type="password")
    if st.button("🗑️ Full System Reset"):
        st.session_state.clear()
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

# --- 3. EXTRACTION (Verified Fixed) ---
def get_text_verified(uploaded_file):
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

# --- 4. INTERFACE ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Stable Build | Quota-Management Edition")

api_key = st.secrets.get("GEMINI_API_KEY")

col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Original (A)", type=['pdf', 'docx'], key="ua")
    if file_a: st.session_state.content_a = get_text_verified(file_a)
with col2:
    file_b = st.file_uploader("Revised (B)", type=['pdf', 'docx'], key="ub")
    if file_b: st.session_state.content_b = get_text_verified(file_b)

if st.session_state.content_a or st.session_state.content_b:
    with st.expander("👀 Verify Extracted Content", expanded=True):
        v1, v2 = st.columns(2)
        v1.text_area("Source A Data", st.session_state.content_a, height=150, disabled=True)
        v2.text_area("Source B Data", st.session_state.content_b, height=150, disabled=True)

# --- 5. THE QUOTA-AWARE AUDIT ---
if st.button("🚀 Run Semantic Audit"):
    if not api_key:
        st.error("Missing API Key.")
    elif st.session_state.content_a and st.session_state.content_b:
        status = st.empty()
        # Use the newest 2.0-flash which had the best 'handshake' result
        model_id = "gemini-2.0-flash"
        
        try:
            status.info(f"Connecting to {model_id}...")
            client = genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model=model_id,
                contents=f"Compare A and B. Mark 🟢[ADD], 🔴[DEL], 🟠[MOD].\n\nA: {st.session_state.content_a[:35000]}\n\nB: {st.session_state.content_b[:35000]}",
                config=types.GenerateContentConfig(temperature=0.0)
            )
            
            report = response.text
            timestamp = datetime.now().strftime("%H:%M:%S")
            st.session_state.history.append({"time": timestamp, "files": f"{file_a.name} vs {file_b.name}", "result": report})
            status.success("Audit Generated!")
            st.divider()
            st.markdown(report)
            
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                status.error("🚦 **Rate Limit Active.** The Google Free Tier allows only 2 audits per minute. **Please wait 60 seconds** before clicking again.")
            elif "404" in err:
                status.error("🌐 **Handshake Failed.** Please ensure your API Key is active in Google AI Studio.")
            else:
                status.error(f"Error: {err}")
    else:
        st.warning("Please upload both files first.")