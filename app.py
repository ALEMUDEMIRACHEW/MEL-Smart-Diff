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
api_key = st.secrets.get("GEMINI_API_KEY")

if "history" not in st.session_state:
    st.session_state.history = []

# --- 2. SIDEBAR: SETTINGS & HISTORY ---
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter App Password", type="password")
    
    st.divider()
    st.header("⚙️ Audit Profile")
    # FEATURE 3: Custom Focus Profiles
    focus_mode = st.radio(
        "Select Sensitivity:",
        ["Strict Audit", "Logic Only", "Summary"],
        index=0,
        help="Strict: Every character | Logic: Dates/Numbers/Instructions | Summary: General vibe"
    )
    
    st.divider()
    st.header("📜 Session History")
    if st.session_state.history:
        for item in reversed(st.session_state.history):
            with st.expander(f"{item['time']} - {item['files']}"):
                st.markdown(item['result'])
    else:
        st.caption("No recent audits.")

# --- 3. LOGIN GATE ---
if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Locked. Please enter the App Password in the sidebar to unlock.")
    st.stop()

# --- 4. CORE UTILITIES ---
def extract_text(uploaded_file):
    try:
        content = uploaded_file.getvalue()
        if uploaded_file.name.endswith('.pdf'):
            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n".join([page.get_text() for page in doc])
        else:
            doc = Document(io.BytesIO(content))
            text = "\n".join([para.text for para in doc])
        return re.sub(r'\s+', ' ', text).strip()
    except Exception as e:
        st.error(f"Error reading {uploaded_file.name}: {e}")
        return ""

def get_system_instruction(mode):
    base = "You are a Professional Document Auditor. Compare File A (Original) and B (Revised)."
    if mode == "Strict Audit":
        return base + " Flag EVERY change including punctuation, commas, and formatting. Use 🟢[ADD], 🔴[DEL], 🟠[MOD]."
    elif mode == "Logic Only":
        return base + " Ignore grammar/style. ONLY flag changes in dates, monetary values, percentages, 'Yes/No' logic, and specific legal instructions."
    else: # Summary
        return base + " Provide a high-level narrative summary of what changed. Do not list line-by-line edits. Focus on the 'vibe' and intent."

def run_audit(text_a, text_b, key, mode):
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction=get_system_instruction(mode),
        temperature=0.0
    )
    model_id = "gemini-3.1-flash-lite-preview"
    prompt = f"AUDIT TASK:\n\nORIGINAL (A):\n{text_a}\n\nREVISED (B):\n{text_b}"
    
    response = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return response.text

# --- 5. MAIN UI ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Enterprise Auditor | Multi-File Support")

# FEATURE 2: Multi-File Batching Layout
col_orig, col_rev = st.columns([1, 1])

with col_orig:
    st.subheader("Master Document")
    file_a = st.file_uploader("Upload 'The Source of Truth'", type=['pdf', 'docx'], key="master")

with col_rev:
    st.subheader("Revised Files")
    files_b = st.file_uploader("Upload one or many files to check", type=['pdf', 'docx'], accept_multiple_files=True, key="batch")

# FEATURE 1: Side-by-Side Visualizer Toggle
show_raw = st.toggle("👁️ Show Side-by-Side Raw Text Viewer")

if show_raw and file_a:
    raw_col1, raw_col2 = st.columns(2)
    with raw_col1:
        st.info(f"Original: {file_a.name}")
        text_a_preview = extract_text(file_a)
        st.text_area("Source Text", text_a_preview, height=200)
    with raw_col2:
        if files_b:
            selected_b = st.selectbox("Select Revised File to Preview", [f.name for f in files_b])
            current_b = next(f for f in files_b if f.name == selected_b)
            st.text_area("Revised Text", extract_text(current_b), height=200)

st.divider()

# Execution Logic
if st.button("🚀 Run Batch Audit"):
    if not api_key:
        st.error("API Key missing.")
    elif file_a and files_b:
        raw_a = extract_text(file_a)[:35000]
        
        for file_b in files_b:
            with st.status(f"Auditing {file_b.name}...", expanded=True) as status:
                raw_b = extract_text(file_b)[:35000]
                try:
                    report = run_audit(raw_a, raw_b, api_key, focus_mode)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    # Store in history
                    st.session_state.history.append({
                        "time": timestamp,
                        "files": f"{file_a.name} vs {file_b.name}",
                        "result": report
                    })
                    
                    st.subheader(f"📋 Report: {file_b.name}")
                    st.markdown(report)
                    st.download_button(f"📥 Download Report for {file_b.name}", report, file_name=f"audit_{file_b.name}.md")
                    status.update(label=f"Completed: {file_b.name}", state="complete")
                except Exception as e:
                    st.error(f"Error processing {file_b.name}: {e}")
    else:
        st.warning("Please upload the Master file and at least one Revised file.")