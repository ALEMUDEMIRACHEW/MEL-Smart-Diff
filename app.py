import streamlit as st
from google import genai
from google.genai import types
import time
import fitz  # PyMuPDF
from docx import Document
import io
import os
import shutil
import pandas as pd
from datetime import datetime
from thefuzz import fuzz
from redlines import Redlines

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# API & Security
api_key = st.secrets.get("GEMINI_API_KEY")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")

if not api_key:
    st.error("❌ API Key missing! Add 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

if "history" not in st.session_state: st.session_state.history = []
if "batch_log" not in st.session_state: st.session_state.batch_log = []

# --- 2. CORE UTILITIES ---

def run_audit(text_a, text_b, key, mode, max_retries=3):
    """
    Targets Gemini 3.1 Flash with built-in retry logic 
    to handle 'Resource Exhausted' or connection glitches.
    """
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction=f"Aviation Maintenance Auditor: {mode}. Flag 🟢[ADD], 🔴[DEL], 🟠[MOD]. Use 5-word anchors.",
        temperature=0.0
    )
    prompt = f"ORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"

    for attempt in range(max_retries):
        try:
            # FIXED: Explicitly using the 3.1 Flash Lite Preview string
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview", 
                contents=prompt, 
                config=config
            )
            return response.text
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str:
                wait_time = (attempt + 1) * 20 
                st.warning(f"⚠️ Quota hit. Waiting {wait_time}s to retry {file_name_placeholder}...")
                time.sleep(wait_time)
            else:
                return f"❌ Audit Error: {str(e)}"
    
    return "❌ Max retries reached. Quota is fully exhausted for now."

def archive_file(source_path):
    try:
        folder = os.path.dirname(source_path)
        archive_dir = os.path.join(folder, "Audited_Results")
        if not os.path.exists(archive_dir): os.makedirs(archive_dir)
        dest_path = os.path.join(archive_dir, os.path.basename(source_path))
        shutil.move(source_path, dest_path)
        return True
    except: return False

def extract_text(source):
    try:
        if isinstance(source, str):
            if source.lower().endswith('.pdf'):
                doc = fitz.open(source)
                return "\n".join([p.get_text() for p in doc])
            elif source.lower().endswith('.docx'):
                doc = Document(source)
                return "\n".join([p.text for p in doc.paragraphs])
        else:
            content = source.getvalue()
            if source.name.lower().endswith('.pdf'):
                doc = fitz.open(stream=content, filetype="pdf")
                return "\n".join([p.get_text() for p in doc])
            elif source.name.lower().endswith('.docx'):
                doc = Document(io.BytesIO(content))
                return "\n".join([p.text for p in doc.paragraphs])
        return ""
    except: return "Extraction Error"

# --- 3. UI ---
st.title("🔍 Smart-Diff Pro")
st.caption("Fleet-Master 2026 | Powered by Gemini 3.1 Flash")

with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Password", type="password")
    focus_mode = st.radio("Focus:", ["Strict Audit", "Logic Only", "Summary"])
    st.divider()
    if st.button("🗑️ Clear Logs"):
        st.session_state.batch_log = []
        st.rerun()

if pwd_input != APP_PASSWORD:
    st.warning("Please enter password.")
    st.stop()

# --- 4. SOURCES ---
st.subheader("1. Master Source")
m_up = st.file_uploader("Upload Master", type=['pdf', 'docx'])

st.subheader("2. Revised Documents (Batch)")
r_t1, r_t2 = st.tabs(["📤 Upload Batch", "📂 Local Folder"])
rev_queue = []

with r_t1:
    r_up = st.file_uploader("Upload Revised", type=['pdf', 'docx'], accept_multiple_files=True)
    if r_up: rev_queue.extend(r_up)

with r_t2:
    r_path = st.text_input("Local Folder Path (C:\\...):")
    if r_path:
        clean_r = os.path.normpath(r_path.strip().strip('"'))
        if os.path.exists(clean_r):
            r_found = [os.path.join(clean_r, f) for f in os.listdir(clean_r) if f.lower().endswith(('.pdf', '.docx'))]
            if r_found:
                r_choices = [os.path.basename(f) for f in r_found]
                sel_r = st.multiselect("Select Files:", r_choices, default=r_choices)
                rev_queue.extend([f for f in r_found if os.path.basename(f) in sel_r])

# --- 5. EXECUTION ---
if st.button("🚀 Run 3.1 Safety Audit"):
    if m_up and rev_queue:
        t_master = extract_text(m_up)[:35000]
        prog = st.progress(0)
        
        for i, file in enumerate(rev_queue):
            fname = file.name if hasattr(file, 'name') else os.path.basename(file)
            prog.progress(int(((i+1)/len(rev_queue))*100))
            
            with st.status(f"Auditing {fname}..."):
                t_rev = extract_text(file)[:35000]
                # Global name for retry warning
                global file_name_placeholder
                file_name_placeholder = fname
                
                report = run_audit(t_master, t_rev, api_key, focus_mode)
                red_html = Redlines(t_master, t_rev).output_markdown
                score = fuzz.token_set_ratio(t_master, t_rev)
                
                # Safety Guard Features
                has_num = any(c.isdigit() for c in report)
                risk = "🚨 HIGH" if has_num else "🟢 LOW"
                
                st.session_state.batch_log.append({"File": fname, "Match %": f"{score}%", "Risk": risk})
                st.session_state.history.append({"time": datetime.now().strftime("%H:%M"), "files": fname, "result": report})

                st.subheader(f"📄 Result: {fname}")
                if isinstance(file, str):
                    if st.button(f"📦 Archive {fname}", key=f"arc_{i}"):
                        if archive_file(file): st.success("Archived")
                
                t1, t2 = st.tabs(["📊 Audit", "🎨 Visual"])
                with t1: st.markdown(report)
                with t2: st.markdown(red_html, unsafe_allow_html=True)
                
                # Small wait to stay within Free Tier RPM
                time.sleep(3) 
    else:
        st.error("Upload Master and select Revised documents first.")

# --- 6. EXCEL LOG ---
if st.session_state.batch_log:
    st.divider()
    df = pd.DataFrame(st.session_state.batch_log)
    st.dataframe(df, use_container_width=True)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Export Results", out.getvalue(), "AuditLog.xlsx")