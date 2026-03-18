import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import re
from datetime import datetime

# --- 1. SETUP & PERSISTENCE ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Password Gate
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123") 

# Initialize storage so data doesn't disappear on rerun
if "history" not in st.session_state:
    st.session_state.history = []
if "content_a" not in st.session_state:
    st.session_state.content_a = ""
if "content_b" not in st.session_state:
    st.session_state.content_b = ""

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

# --- 2. LOGIN CHECK ---
if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Locked. Please enter the App Password in the sidebar.")
    st.stop()

# --- 3. EXTRACTION ENGINE ---
api_key = st.secrets.get("GEMINI_API_KEY")

def get_text(uploaded_file):
    """The 'Careful' Extraction: Resets pointer and reads bytes into memory immediately."""
    if not uploaded_file:
        return ""
    try:
        uploaded_file.seek(0)  # REQUIRED: Reset to start of file
        fb = uploaded_file.read()
        
        if uploaded_file.name.endswith('.pdf'):
            doc = fitz.open(stream=fb, filetype="pdf")
            text = "\n".join([page.get_text() for page in doc])
        else:
            doc = Document(io.BytesIO(fb))
            text = "\n".join([para.text for para in doc])
            
        return re.sub(r'\s+', ' ', text).strip()
    except Exception as e:
        st.error(f"Error in {uploaded_file.name}: {e}")
        return ""

# --- 4. UI & FILE HANDLING ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Stable Build | Memory-Mapped Extraction")

col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Upload Original (A)", type=['pdf', 'docx'], key="up_a")
    if file_a:
        # Save to session_state so it stays visible
        st.session_state.content_a = get_text(file_a)

with col2:
    file_b = st.file_uploader("Upload Revised (B)", type=['pdf', 'docx'], key="up_b")
    if file_b:
        # Save to session_state so it stays visible
        st.session_state.content_b = get_text(file_b)

# --- 5. VISUALIZER (Safe from 'Empty Stream') ---
if st.session_state.content_a or st.session_state.content_b:
    with st.expander("👀 View Extracted Raw Text (Review Source A & B)"):
        v_col1, v_col2 = st.columns(2)
        with v_col1:
            st.info("Source A Content")
            st.text_area("A_View", st.session_state.content_a, height=250, disabled=True, label_visibility="collapsed")
        with v_col2:
            st.info("Source B Content")
            st.text_area("B_View", st.session_state.content_b, height=250, disabled=True, label_visibility="collapsed")

# --- 6. AUDIT EXECUTION ---
if st.button("🚀 Run Semantic Audit"):
    if not api_key:
        st.error("Missing API Key.")
    elif st.session_state.content_a and st.session_state.content_b:
        with st.spinner("AI is analyzing technical changes..."):
            try:
                client = genai.Client(api_key=api_key)
                config = types.GenerateContentConfig(
                    system_instruction="Analyze changes between File A and B. Flag 🟢[ADD], 🔴[DEL], 🟠[MOD]. Ignore formatting.",
                    temperature=0.0
                )
                
                # Using 2.0-flash as the stable 2026 production anchor
                report = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=f"AUDIT:\n\nA:\n{st.session_state.content_a[:35000]}\n\nB:\n{st.session_state.content_b[:35000]}",
                    config=config
                ).text
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                st.session_state.history.append({
                    "time": timestamp,
                    "files": f"{file_a.name} vs {file_b.name}",
                    "result": report
                })
                
                st.divider()
                st.subheader("📋 Audit Report")
                st.markdown(report)
            except Exception as e:
                st.error(f"Audit Error: {e}")
    else:
        st.warning("Please upload both files first.")