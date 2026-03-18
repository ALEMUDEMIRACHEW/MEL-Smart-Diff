import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import os
import re
import pandas as pd
from datetime import datetime
from thefuzz import fuzz
from redlines import Redlines

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Enterprise styling with Redline & Safety Guard support
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    ins { background-color: #d4edda; text-decoration: none; color: #155724; padding: 2px; border-radius: 3px; }
    del { background-color: #f8d7da; color: #721c24; padding: 2px; border-radius: 3px; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    .keyword-alert { background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; border: 1px solid #ffeeba; margin-bottom: 10px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")
api_key = st.secrets.get("GEMINI_API_KEY")

if "history" not in st.session_state: st.session_state.history = []
if "batch_log" not in st.session_state: st.session_state.batch_log = []

# --- 2. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter App Password", type="password")
    
    st.divider()
    st.header("⚙️ Audit Profile")
    focus_mode = st.radio("Sensitivity Level:", ["Strict Audit", "Logic Only", "Summary"])
    
    st.divider()
    st.header("🚨 Keyword Watchlist")
    keywords = st.text_input("Alert on (comma separated):", "Caution, Warning, Note, Limit, Torque, Task")
    keyword_list = [k.strip().lower() for k in keywords.split(",")]

    st.divider()
    st.header("📜 Session History")
    if st.session_state.history:
        for item in reversed(st.session_state.history[-5:]):
            with st.expander(f"{item['time']} - {item['files']}"):
                st.markdown(item['result'])
    
    if st.button("🗑️ Reset All Results"):
        st.session_state.batch_log = []
        st.session_state.history = []
        st.rerun()

if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Locked. Please enter the App Password in the sidebar.")
    st.stop()

# --- 3. CORE UTILITIES ---
def extract_text(uploaded_file):
    try:
        if isinstance(uploaded_file, str): # Local Path Logic
            if uploaded_file.endswith('.pdf'):
                doc = fitz.open(uploaded_file)
                text = "\n".join([page.get_text() for page in doc])
            else:
                doc = Document(uploaded_file)
                text = "\n".join([para.text for para in doc])
        else: # Uploaded File Logic
            content = uploaded_file.getvalue()
            if uploaded_file.name.endswith('.pdf'):
                doc = fitz.open(stream=content, filetype="pdf")
                text = "\n".join([page.get_text() for page in doc])
            else:
                doc = Document(io.BytesIO(content))
                text = "\n".join([para.text for para in doc])
        return re.sub(r'\s+', ' ', text).strip()
    except Exception: return ""

def run_audit(text_a, text_b, key, mode):
    client = genai.Client(api_key=key)
    model_id = "gemini-3.1-flash-lite-preview" 
    config = types.GenerateContentConfig(
        system_instruction=f"Aviation Auditor Mode: {mode}. Flag 🟢[ADD], 🔴[DEL], 🟠[MOD]. Use 5-word anchors.",
        temperature=0.0
    )
    prompt = f"ORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"
    return client.models.generate_content(model=model_id, contents=prompt, config=config).text

# --- 4. MAIN INTERFACE ---
st.title("🔍 Smart-Diff Pro")
st.caption("Fleet-Master 2026 | Safety Guard | Multi-Mode Auditor")

tab_man, tab_loc = st.tabs(["📤 Manual Batch Upload", "📂 Local Folder Watcher"])

with tab_man:
    m_col1, m_col2 = st.columns(2)
    with m_col1: master_file = st.file_uploader("📂 Master File (Source)", type=['pdf', 'docx'], key="manual_m")
    with m_col2: rev_files = st.file_uploader("📂 Revised Files (Batch)", type=['pdf', 'docx'], accept_multiple_files=True, key="manual_r")

with tab_loc:
    st.info("⚠️ Only works if running Streamlit locally on your PC. Cloud apps cannot see your C: drive.")
    local_path = st.text_input("Enter Local Folder Path (e.g. C:\\Updates):", "")
    if local_path and not os.path.exists(local_path):
        st.error("Directory not found. Use 'Manual Batch' if on the web.")

# RESTORED: Side-by-Side Raw Text Visualizer
show_raw = st.toggle("👁️ Show Side-by-Side Raw Text Viewer")
if show_raw and master_file:
    v_col1, v_col2 = st.columns(2)
    raw_master = extract_text(master_file)
    with v_col1:
        st.info(f"Master: {master_file.name}")
        st.text_area("Master Source Text", raw_master, height=250)
    with v_col2:
        preview_list = rev_files if rev_files else []
        if preview_list:
            sel_rev = st.selectbox("Compare With:", [f.name for f in preview_list])
            curr_f = next(f for f in preview_list if f.name == sel_rev)
            st.text_area(f"Revised: {sel_rev}", extract_text(curr_f), height=250)
        else:
            st.warning("Upload files to enable preview.")

st.divider()

# --- 5. EXECUTION ENGINE ---
if st.button("🚀 Run Full Safety Audit"):
    to_process = []
    if rev_files: to_process = rev_files
    elif local_path and os.path.exists(local_path):
        to_process = [os.path.join(local_path, f) for f in os.listdir(local_path) if f.lower().endswith(('.pdf', '.docx'))]

    if not api_key:
        st.error("API Key missing.")
    elif master_file and to_process:
        text_master = extract_text(master_file)[:35000]
        prog_bar = st.progress(0)
        prog_status = st.empty()
        
        for idx, file in enumerate(to_process):
            fname = file.name if hasattr(file, 'name') else os.path.basename(file)
            prog_status.info(f"Auditing {idx+1}/{len(to_process)}: **{fname}**")
            prog_bar.progress(int(((idx + 1) / len(to_process)) * 100))
            
            with st.status(f"Processing {fname}...", expanded=False) as status:
                text_rev = extract_text(file)[:35000]
                
                # Visual Redline & Similarity
                redline_html = Redlines(text_master, text_rev).output_markdown
                score = fuzz.token_set_ratio(text_master, text_rev)
                
                try:
                    report = run_audit(text_master, text_rev, api_key, focus_mode)
                    
                    # Safety Analysis (Numerical & Keyword Alerts)
                    has_nums = any(char.isdigit() for char in report)
                    alerts = [k.upper() for k in keyword_list if k in report.lower()]
                    risk = "🚨 CRITICAL" if has_nums and alerts else "🚨 HIGH" if has_nums else "🟡 MEDIUM" if score < 95 else "🟢 LOW"
                    
                    st.session_state.history.append({"time": datetime.now().strftime("%H:%M"), "files": fname, "result": report})
                    st.session_state.batch_log.append({
                        "File": fname, "Match %": f"{score}%", "Risk": risk, "Alerts": ", ".join(alerts) if alerts else "None", "Summary": report[:250] + "..."
                    })
                    
                    st.subheader(f"📄 Result: {fname}")
                    if alerts: st.markdown(f'<div class="keyword-alert">⚠️ Keywords Found: {", ".join(alerts)}</div>', unsafe_allow_html=True)
                    
                    t1, t2 = st.tabs(["📊 AI Audit Report", "🎨 Visual Redline"])
                    with t1: st.markdown(report)
                    with t2: st.markdown(redline_html, unsafe_allow_html=True)
                    
                    status.update(label=f"Done: {fname}", state="complete")
                except Exception as e:
                    st.error(f"Error on {fname}: {e}")
        prog_status.success("✅ Batch Audit Complete!")
    else:
        st.warning("Ensure Master and Revised files are provided.")

# --- 6. DATA DASHBOARD & EXCEL ---
if st.session_state.batch_log:
    st.divider()
    df = pd.DataFrame(st.session_state.batch_log)
    c1, c2, c3 = st.columns(3)
    c1.metric("Batch Size", len(df))
    c2.metric("Critical Alerts (🚨)", len(df[df['Risk'].str.contains("🚨")]))
    c3.metric("Avg Match %", f"{int(df['Match %'].str.replace('%','').astype(int).mean())}%")
    
    st.dataframe(df, use_container_width=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Safety_Audit')
    st.download_button("📥 Export Audit Log to Excel", data=output.getvalue(), file_name=f"Audit_Report_{datetime.now().strftime('%Y%m%d')}.xlsx")