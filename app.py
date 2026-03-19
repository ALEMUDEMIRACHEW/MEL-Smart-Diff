import streamlit as st
from google import genai
from google.genai import types
import time
import fitz  # PyMuPDF
from docx import Document
from docx.shared import Pt
import io
import os
import shutil
import pandas as pd
from datetime import datetime
from thefuzz import fuzz
from redlines import Redlines

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Professional UI Styling
st.markdown("""
    <style>
    .report-card { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #007bff; margin-bottom: 20px; }
    .diff-box { background-color: #ffffff; padding: 15px; border: 1px solid #ddd; border-radius: 5px; font-family: monospace; }
    ins { background-color: #d4edda; color: #155724; text-decoration: none; }
    del { background-color: #f8d7da; color: #721c24; }
    </style>
    """, unsafe_allow_html=True)

# API & Session State
api_key = st.secrets.get("GEMINI_API_KEY")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")

if "history" not in st.session_state: st.session_state.history = []
if "batch_log" not in st.session_state: st.session_state.batch_log = []

# --- 2. CORE ENGINES ---

def create_word_report(filename, score, report_text):
    """FEATURE: Professional Word Export."""
    doc = Document()
    doc.add_heading(f'Comparison Report: {filename}', 0)
    doc.add_paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph(f"Similarity Match Score: {score}")
    doc.add_heading('Analysis Results', level=1)
    doc.add_paragraph(report_text)
    target = io.BytesIO()
    doc.save(target)
    return target.getvalue()

def run_audit(text_a, text_b, key, mode, context_type):
    """FEATURE: Gemini 3.1 Flash with Context Switching."""
    client = genai.Client(api_key=key)
    
    # Dynamic System Instruction based on your needs
    if context_type == "Technical/Aviation":
        instruction = f"Aviation Auditor: {mode}. Flag 🟢[ADD], 🔴[DEL], 🟠[MOD]. Focus on Torque, Part#s, and Safety Steps."
    else:
        instruction = f"General Analyst: {mode}. Compare documents and list all additions, deletions, and value changes clearly."

    config = types.GenerateContentConfig(system_instruction=instruction, temperature=0.0)
    prompt = f"ORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"

    for attempt in range(3):
        try:
            return client.models.generate_content(model="gemini-3.1-flash-lite-preview", contents=prompt, config=config).text
        except Exception as e:
            if "429" in str(e): time.sleep(20) # Auto-retry for Quota
            else: return f"Error: {e}"
    return "Quota Exceeded."

def extract_text(source):
    """FEATURE: Universal PDF/DOCX Extractor."""
    try:
        if isinstance(source, str): # Path string
            if source.lower().endswith('.pdf'): return "\n".join([p.get_text() for p in fitz.open(source)])
            if source.lower().endswith('.docx'): return "\n".join([p.text for p in Document(source).paragraphs])
        else: # UploadedFile object
            if source.name.lower().endswith('.pdf'): return "\n".join([p.get_text() for p in fitz.open(stream=source.getvalue(), filetype="pdf")])
            if source.name.lower().endswith('.docx'): return "\n".join([p.text for p in Document(io.BytesIO(source.getvalue())).paragraphs])
        return ""
    except: return "Extraction Error"

# --- 3. SIDEBAR (All Features Intact) ---
with st.sidebar:
    st.header("🔐 App Access")
    pwd_input = st.text_input("Password", type="password")
    
    st.divider()
    st.header("⚙️ Audit Profile")
    context_type = st.selectbox("Document Context:", ["General Purpose", "Technical/Aviation"])
    focus_mode = st.radio("Detail Level:", ["Granular", "Summary"])
    
    st.header("🚨 Safety Watchlist")
    keywords = st.text_input("Flag Keywords (comma separated):", "Caution, Warning, Torque, Limit")
    kw_list = [k.strip().lower() for k in keywords.split(",")]

    if st.button("🗑️ Reset All Logs"):
        st.session_state.batch_log = []
        st.session_state.history = []
        st.rerun()

if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.info("Enter password in the sidebar to unlock.")
    st.stop()

# --- 4. DATA INPUTS (Local Folder + Upload) ---
st.title("🔍 Smart-Diff Pro v3.1")
st.caption(f"Status: Authorized | Engine: Gemini 3.1 Flash | Mode: {context_type}")

# MASTER SELECTION
st.subheader("1. Master / Original Document")
m_t1, m_t2 = st.tabs(["📤 Upload Master", "📂 Local Master Folder"])
master_to_use = None

with m_t1:
    m_up = st.file_uploader("Upload Master File", type=['pdf', 'docx'])
    if m_up: master_to_use = m_up
with m_t2:
    m_path = st.text_input("Master PC Folder Path:", key="m_folder")
    if m_path and os.path.exists(m_path):
        m_files = [f for f in os.listdir(m_path) if f.lower().endswith(('.pdf', '.docx'))]
        if m_files:
            m_sel = st.selectbox("Select Master from Folder:", m_files)
            master_to_use = os.path.join(m_path, m_sel)

# REVISED SELECTION
st.subheader("2. Revised / New Documents")
r_t1, r_t2 = st.tabs(["📤 Upload Batch", "📂 Local Batch Folder"])
rev_queue = []

with r_t1:
    r_up = st.file_uploader("Upload New Files", type=['pdf', 'docx'], accept_multiple_files=True)
    if r_up: rev_queue.extend(r_up)
with r_t2:
    r_path = st.text_input("Revised PC Folder Path:", key="r_folder")
    if r_path and os.path.exists(r_path):
        r_f = [f for f in os.listdir(r_path) if f.lower().endswith(('.pdf', '.docx'))]
        if r_f:
            r_sel = st.multiselect("Select Files for Batch Audit:", r_f, default=r_f)
            rev_queue.extend([os.path.join(r_path, f) for f in r_sel])

# --- 5. PREVIEW FEATURE ---
if master_to_use and rev_queue:
    if st.checkbox("👁️ Show Quick Preview before Audit"):
        c1, c2 = st.columns(2)
        c1.text_area("Master Preview", extract_text(master_to_use)[:500], height=150)
        c2.text_area("First Revised Preview", extract_text(rev_queue[0])[:500], height=150)

# --- 6. EXECUTION & DISPLAY ---
if st.button("🚀 Execute Smart-Diff Audit"):
    if master_to_use and rev_queue:
        t_master = extract_text(master_to_use)[:40000]
        prog = st.progress(0)
        
        for i, file in enumerate(rev_queue):
            fname = file.name if hasattr(file, 'name') else os.path.basename(file)
            prog.progress(int(((i+1)/len(rev_queue))*100))
            
            with st.status(f"Analyzing {fname}..."):
                t_rev = extract_text(file)[:40000]
                
                # AI Logic
                report = run_audit(t_master, t_rev, api_key, focus_mode, context_type)
                
                # Visual Diff Logic
                red_html = Redlines(t_master, t_rev).output_markdown
                score = f"{fuzz.token_set_ratio(t_master, t_rev)}%"
                
                # Keyword Check
                found_kw = [k.upper() for k in kw_list if k in report.lower()]
                
                # Log Data
                st.session_state.batch_log.append({"File": fname, "Similarity": score, "Alerts": ", ".join(found_kw)})
                
                # Display Result
                st.divider()
                st.subheader(f"📄 Result: {fname} (Match: {score})")
                
                # Download Buttons
                word_data = create_word_report(fname, score, report)
                st.download_button(f"📥 Download Word Report ({fname})", word_data, f"{fname}_Report.docx")
                
                col_left, col_right = st.columns([1, 1])
                with col_left:
                    st.markdown("**AI Technical Analysis:**")
                    st.info(report)
                with col_right:
                    st.markdown("**Visual Changes:**")
                    st.markdown(f'<div class="report-card">{red_html}</div>', unsafe_allow_html=True)
                
                # Feature: Local Archiving
                if isinstance(file, str):
                    if st.button(f"📦 Archive {fname} to 'Processed'", key=f"arch_{i}"):
                        arc_dir = os.path.join(os.path.dirname(file), "Processed_Audits")
                        if not os.path.exists(arc_dir): os.makedirs(arc_dir)
                        shutil.move(file, os.path.join(arc_dir, fname))
                        st.success("Archived.")
                
                time.sleep(2) # Keep quota safe
    else:
        st.error("Please ensure Master and Revised documents are selected.")

# --- 7. EXPORT DASHBOARD ---
if st.session_state.batch_log:
    st.divider()
    st.header("📊 Batch Audit Summary")
    df = pd.DataFrame(st.session_state.batch_log)
    st.table(df)
    
    # EXCEL EXPORT
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='AuditSummary')
    st.download_button("📥 Export Batch Summary (Excel)", out.getvalue(), "Audit_Batch_Summary.xlsx")