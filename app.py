import streamlit as st
from google import genai
from google.genai import types
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

# API Setup from Streamlit Cloud Secrets
api_key = st.secrets.get("GEMINI_API_KEY")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")

if not api_key:
    st.error("❌ API Key missing in Secrets. Please add 'GEMINI_API_KEY'.")
    st.stop()

if "history" not in st.session_state: st.session_state.history = []
if "batch_log" not in st.session_state: st.session_state.batch_log = []

# --- 2. CORE UTILITIES ---

def archive_file(source_path):
    """Moves audited files to a sub-folder."""
    try:
        folder = os.path.dirname(source_path)
        archive_dir = os.path.join(folder, "Audited_Results")
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
        dest_path = os.path.join(archive_dir, os.path.basename(source_path))
        shutil.move(source_path, dest_path)
        return True
    except Exception as e:
        st.error(f"Archive failed: {e}")
        return False

def extract_text(source):
    """Universal Text Extraction (PDF/DOCX)."""
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

def run_audit(text_a, text_b, key, mode):
    """
    Standard Gemini Call. 
    Using 'gemini-2.0-flash' for maximum stability on Streamlit Cloud.
    """
    client = genai.Client(api_key=key)
    
    config = types.GenerateContentConfig(
        system_instruction=f"Aviation Maintenance Auditor: {mode}. Flag 🟢[ADD], 🔴[DEL], 🟠[MOD]. Use 5-word anchors.",
        temperature=0.0
    )
    
    prompt = f"ORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"
    
    # Using the most stable high-performance model to avoid ClientError
    return client.models.generate_content(
        model="gemini-2.0-flash", 
        contents=prompt, 
        config=config
    ).text

# --- 3. UI LAYOUT ---
st.title("🔍 Smart-Diff Pro")
st.caption("Fleet-Master 2026 | Optimized for Ethiopian MRO")

with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Password", type="password")
    st.divider()
    st.header("⚙️ Audit Profile")
    focus_mode = st.radio("Sensitivity:", ["Strict Audit", "Logic Only", "Summary"])
    keywords = st.text_input("Watchlist:", "Caution, Warning, Note, Limit, Torque")
    keyword_list = [k.strip().lower() for k in keywords.split(",")]
    
    st.divider()
    st.header("📜 History")
    for item in reversed(st.session_state.history[-5:]):
        st.caption(f"{item['time']} - {item['files']}")

if pwd_input != APP_PASSWORD:
    st.warning("Please enter your password to continue.")
    st.stop()

# --- 4. DATA SOURCES ---
# SECTION 1: MASTER
st.subheader("1. Master Source (Source of Truth)")
m_t1, m_t2 = st.tabs(["📤 Upload", "📂 Local Folder"])
master_to_use = None

with m_t1:
    m_up = st.file_uploader("Upload Master", type=['pdf', 'docx'])
    if m_up: master_to_use = m_up

with m_t2:
    m_path = st.text_input("Master Path (C:\\...):", key="master_path_input")
    if m_path:
        clean_m = os.path.normpath(m_path.strip().strip('"'))
        if os.path.exists(clean_m):
            m_files = [os.path.join(clean_m, f) for f in os.listdir(clean_m) if f.lower().endswith(('.pdf', '.docx'))]
            if m_files:
                m_sel = st.selectbox("Select Master:", [os.path.basename(f) for f in m_files])
                master_to_use = next(f for f in m_files if os.path.basename(f) == m_sel)

# SECTION 2: REVISED
st.subheader("2. Revised Documents (Batch Analysis)")
r_t1, r_t2 = st.tabs(["📤 Upload Batch", "📂 Local Folder"])
rev_queue = []

with r_t1:
    r_up = st.file_uploader("Upload Revised", type=['pdf', 'docx'], accept_multiple_files=True)
    if r_up: rev_queue.extend(r_up)

with r_t2:
    r_path = st.text_input("Revised Path (C:\\...):", key="rev_path_input")
    if r_path:
        clean_r = os.path.normpath(r_path.strip().strip('"'))
        if os.path.exists(clean_r):
            r_found = [os.path.join(clean_r, f) for f in os.listdir(clean_r) if f.lower().endswith(('.pdf', '.docx'))]
            if r_found:
                r_choices = [os.path.basename(f) for f in r_found]
                selected_r = st.multiselect("Select Files for Audit:", r_choices, default=r_choices)
                rev_queue.extend([f for f in r_found if os.path.basename(f) in selected_r])

# --- 5. EXECUTION ---
if st.button("🚀 Run Full Safety Audit"):
    if master_to_use and rev_queue:
        t_master = extract_text(master_to_use)[:35000]
        prog = st.progress(0)
        
        for i, file in enumerate(rev_queue):
            fname = file.name if hasattr(file, 'name') else os.path.basename(file)
            prog.progress(int(((i+1)/len(rev_queue))*100))
            
            with st.status(f"Auditing {fname}..."):
                t_rev = extract_text(file)[:35000]
                report = run_audit(t_master, t_rev, api_key, focus_mode)
                red_html = Redlines(t_master, t_rev).output_markdown
                score = fuzz.token_set_ratio(t_master, t_rev)
                
                # Safety Guard Features Intact
                has_num = any(c.isdigit() for c in report)
                alerts = [k.upper() for k in keyword_list if k in report.lower()]
                risk = "🚨 CRITICAL" if (has_num and alerts) else "🚨 HIGH" if has_num else "🟢 LOW"
                
                st.session_state.batch_log.append({"File": fname, "Match %": f"{score}%", "Risk": risk, "Alerts": ", ".join(alerts)})
                st.session_state.history.append({"time": datetime.now().strftime("%H:%M"), "files": fname, "result": report})

                st.subheader(f"📄 Result: {fname}")
                if isinstance(file, str):
                    if st.button(f"📦 Archive {fname}", key=f"arch_{i}"):
                        if archive_file(file): st.success("Moved to Audited_Results")
                
                res_t1, res_t2 = st.tabs(["📊 Audit Report", "🎨 Visual Redline"])
                with res_t1: st.markdown(report)
                with res_t2: st.markdown(red_html, unsafe_allow_html=True)
    else:
        st.warning("Please ensure both Master and Revised sources are set.")

# --- 6. EXPORT ---
if st.session_state.batch_log:
    st.divider()
    df = pd.DataFrame(st.session_state.batch_log)
    st.dataframe(df, use_container_width=True)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Export Results to Excel", out.getvalue(), "Audit_Report.xlsx")