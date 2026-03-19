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

# --- 1. SETTINGS & CSS ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

st.markdown("""
    <style>
    .report-card { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e6e9ef; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .status-low { color: #28a745; font-weight: bold; }
    .status-high { color: #dc3545; font-weight: bold; }
    ins { background-color: #d4edda; color: #155724; text-decoration: none; }
    del { background-color: #f8d7da; color: #721c24; }
    </style>
    """, unsafe_allow_html=True)

# API Setup
api_key = st.secrets.get("GEMINI_API_KEY")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")

if "history" not in st.session_state: st.session_state.history = []
if "batch_log" not in st.session_state: st.session_state.batch_log = []

# --- 2. CORE ENGINES ---
def run_audit(text_a, text_b, key, mode, fname="Task"):
    """Gemini 3.1 Flash with Smart Retry for Quota."""
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction=(
            f"Aviation Auditor Mode: {mode}. Compare original vs revised. "
            "Highlight changes with 🟢[ADD], 🔴[DEL], 🟠[MOD]. "
            "Focus on Torque values, Part numbers, and Safety steps."
        ),
        temperature=0.0
    )
    prompt = f"ORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview", 
                contents=prompt, 
                config=config
            )
            return response.text
        except Exception as e:
            if "429" in str(e):
                st.warning(f"🕒 Quota full. Retrying {fname} in {(attempt+1)*20}s...")
                time.sleep((attempt + 1) * 20)
            else:
                return f"❌ API Error: {str(e)}"
    return "❌ Resource Exhausted. Try again in 1 minute."

def extract_text(source):
    """Universal Extractor for PDF/DOCX."""
    try:
        if isinstance(source, str): # Local Path
            if source.lower().endswith('.pdf'):
                return "\n".join([p.get_text() for p in fitz.open(source)])
            elif source.lower().endswith('.docx'):
                return "\n".join([p.text for p in Document(source).paragraphs])
        else: # Uploaded File
            if source.name.lower().endswith('.pdf'):
                return "\n".join([p.get_text() for p in fitz.open(stream=source.getvalue(), filetype="pdf")])
            elif source.name.lower().endswith('.docx'):
                return "\n".join([p.text for p in Document(io.BytesIO(source.getvalue())).paragraphs])
        return ""
    except: return "Extraction Failed"

# --- 3. SIDEBAR (Full Feature Restore) ---
with st.sidebar:
    st.header("🔐 Safety Access")
    pwd_input = st.text_input("Enter App Password", type="password")
    
    st.divider()
    st.header("⚙️ Audit Preferences")
    focus_mode = st.radio("Audit Depth:", ["Strict (Step-by-Step)", "Logic Only", "Executive Summary"])
    st.header("🚨 Safety Watchlist")
    keywords = st.text_input("Flag Keywords:", "Caution, Warning, Note, Limit, Torque, AMM")
    kw_list = [k.strip().lower() for k in keywords.split(",")]
    
    st.divider()
    st.header("📜 Recent Audits")
    for item in reversed(st.session_state.history[-5:]):
        with st.expander(f"{item['time']} - {item['files'][:15]}..."):
            st.write(item['result'][:200] + "...")

if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.info("Please enter the password in the sidebar to begin auditing.")
    st.stop()

# --- 4. MASTER SELECTION (Full Restore) ---
st.title("🔍 Smart-Diff Pro: Fleet Master")
st.subheader("1. Identify Master Document")
m_t1, m_t2 = st.tabs(["📤 Manual Master Upload", "📂 Browse Local PC Folder"])
master_to_use = None

with m_t1:
    m_up = st.file_uploader("Drop Master File Here", type=['pdf', 'docx'])
    if m_up: master_to_use = m_up

with m_t2:
    m_path = st.text_input("Enter PC Folder Path (e.g. C:\\Users\\...):", key="m_path_ui")
    if m_path:
        path = os.path.normpath(m_path.strip().strip('"'))
        if os.path.exists(path):
            files = [f for f in os.listdir(path) if f.lower().endswith(('.pdf', '.docx'))]
            if files:
                m_sel = st.selectbox("Select Master File from this folder:", files)
                master_to_use = os.path.join(path, m_sel)
                st.success(f"✅ Master Set: {m_sel}")
        else: st.error("Directory not found.")

# --- 5. REVISED BATCH SELECTION ---
st.subheader("2. Select Revised Documents for Audit")
r_t1, r_t2 = st.tabs(["📤 Manual Batch Upload", "📂 Local Batch Folder"])
rev_queue = []

with r_t1:
    r_up = st.file_uploader("Upload Multiple Revised Files", type=['pdf', 'docx'], accept_multiple_files=True)
    if r_up: rev_queue.extend(r_up)

with r_t2:
    r_path = st.text_input("Enter Folder Path for Revised Files:", key="r_path_ui")
    if r_path:
        path = os.path.normpath(r_path.strip().strip('"'))
        if os.path.exists(path):
            files = [f for f in os.listdir(path) if f.lower().endswith(('.pdf', '.docx'))]
            if files:
                r_sel = st.multiselect("Select Files to Include in Audit:", files, default=files)
                rev_queue.extend([os.path.join(path, f) for f in r_sel])
                st.info(f"📁 {len(rev_queue)} files queued from local folder.")

# --- 6. PREVIEW ENGINE ---
if master_to_use and rev_queue:
    if st.checkbox("👁️ Show Content Preview (Master vs Selected Revised)"):
        p1, p2 = st.columns(2)
        p1.info("Master Preview")
        p1.code(extract_text(master_to_use)[:500] + "...", language="text")
        
        selected_rev_name = st.selectbox("Preview which revised file?", [f.name if hasattr(f, 'name') else os.path.basename(f) for f in rev_queue])
        p2.info(f"Previewing: {selected_rev_name}")
        # Find the actual object/path for extraction
        target = next(f for f in rev_queue if (f.name if hasattr(f, 'name') else os.path.basename(f)) == selected_rev_name)
        p2.code(extract_text(target)[:500] + "...", language="text")

st.divider()

# --- 7. AUDIT EXECUTION ---
if st.button("🚀 Start Full Safety Audit"):
    if master_to_use and rev_queue:
        t_master = extract_text(master_to_use)[:40000]
        prog = st.progress(0)
        
        for i, file in enumerate(rev_queue):
            fname = file.name if hasattr(file, 'name') else os.path.basename(file)
            prog.progress(int(((i+1)/len(rev_queue))*100))
            
            with st.status(f"Auditing {fname}..."):
                t_rev = extract_text(file)[:40000]
                report = run_audit(t_master, t_rev, api_key, focus_mode, fname)
                red_html = Redlines(t_master, t_rev).output_markdown
                score = fuzz.token_set_ratio(t_master, t_rev)
                
                # Safety Detection
                found_kw = [k.upper() for k in kw_list if k in report.lower()]
                has_num_change = any(c.isdigit() for c in report)
                risk_lvl = "🚨 HIGH" if has_num_change else "🟢 LOW"
                
                st.session_state.batch_log.append({"File": fname, "Match": f"{score}%", "Risk": risk_lvl, "Keywords": ", ".join(found_kw)})
                st.session_state.history.append({"time": datetime.now().strftime("%H:%M"), "files": fname, "result": report})

                st.markdown(f"### 📄 Audit: {fname}")
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    st.markdown("**AI Audit Findings:**")
                    st.write(report)
                with col_b:
                    st.markdown("**Visual Redline (Differences):**")
                    st.markdown(f'<div class="report-card">{red_html}</div>', unsafe_allow_html=True)
                st.divider()
                time.sleep(2) # Prevent 429 trigger
    else:
        st.error("Missing Data. Please select Master and Revised documents.")

# --- 8. DASHBOARD & EXPORT ---
if st.session_state.batch_log:
    st.header("📊 Fleet Audit Dashboard")
    df = pd.DataFrame(st.session_state.batch_log)
    st.table(df)
    
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='AuditLog')
    st.download_button("📥 Export Results to Excel", out.getvalue(), "Fleet_Audit_Report.xlsx")