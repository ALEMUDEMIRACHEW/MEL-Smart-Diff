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

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    ins { background-color: #d4edda; text-decoration: none; color: #155724; padding: 2px; border-radius: 3px; }
    del { background-color: #f8d7da; color: #721c24; padding: 2px; border-radius: 3px; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    .keyword-alert { background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; border: 1px solid #ffeeba; margin-bottom: 10px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

api_key = st.secrets.get("GEMINI_API_KEY", "YOUR_KEY_HERE")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")

if "history" not in st.session_state: st.session_state.history = []
if "batch_log" not in st.session_state: st.session_state.batch_log = []

# --- 2. CORE UTILITIES ---
def open_local_file(path):
    try:
        if os.path.exists(path):
            os.startfile(path)
        else:
            st.error(f"Path no longer valid: {path}")
    except Exception as e:
        st.error(f"System error opening file: {e}")

def extract_text(source):
    try:
        if isinstance(source, str): # Path string
            if source.lower().endswith('.pdf'):
                doc = fitz.open(source)
                return "\n".join([p.get_text() for p in doc])
            elif source.lower().endswith('.docx'):
                doc = Document(source)
                return "\n".join([p.text for p in doc.paragraphs])
        else: # UploadedFile object
            content = source.getvalue()
            if source.name.lower().endswith('.pdf'):
                doc = fitz.open(stream=content, filetype="pdf")
                return "\n".join([p.get_text() for p in doc])
            elif source.name.lower().endswith('.docx'):
                doc = Document(io.BytesIO(content))
                return "\n".join([p.text for p in doc.paragraphs])
        return ""
    except: return ""

def run_audit(text_a, text_b, key, mode):
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction=f"Aviation Auditor: {mode}. Flag 🟢[ADD], 🔴[DEL], 🟠[MOD]. Use 5-word anchors.",
        temperature=0.0
    )
    prompt = f"ORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"
    return client.models.generate_content(model="gemini-3.1-flash-lite-preview", contents=prompt, config=config).text

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Password", type="password")
    st.divider()
    st.header("⚙️ Audit Profile")
    focus_mode = st.radio("Sensitivity:", ["Strict Audit", "Logic Only", "Summary"])
    st.header("🚨 Keywords")
    keywords = st.text_input("Watchlist:", "Caution, Warning, Note, Limit, Torque")
    keyword_list = [k.strip().lower() for k in keywords.split(",")]
    if st.button("🗑️ Reset All Data"):
        st.session_state.batch_log = []
        st.session_state.history = []
        st.rerun()

if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Please enter the App Password in the sidebar to unlock.")
    st.stop()

# --- 4. MAIN INTERFACE ---
st.title("🔍 Smart-Diff Pro")
st.caption("Fleet-Master 2026 | Safety Guard | Omni-Source Processing")

st.subheader("1. Master Document (Source of Truth)")
master_file = st.file_uploader("Upload Master File", type=['pdf', 'docx'])

st.subheader("2. Revised Documents (Batch Analysis)")
tab_man, tab_loc = st.tabs(["📤 Manual Upload", "📂 Local Folder Watcher"])

all_files_queue = [] # This is the "Omni-Source" Collector

with tab_man:
    rev_manual = st.file_uploader("Select files to upload", type=['pdf', 'docx'], accept_multiple_files=True)
    if rev_manual: all_files_queue.extend(rev_manual)

with tab_loc:
    local_path = st.text_input("Paste Local Folder Path (Press Enter):", key="loc_input")
    if local_path:
        clean_p = os.path.normpath(local_path.strip().strip('"'))
        if os.path.exists(clean_p) and os.path.isdir(clean_p):
            local_found = [os.path.join(clean_p, f) for f in os.listdir(clean_p) if f.lower().endswith(('.pdf', '.docx'))]
            if local_found:
                st.success(f"✅ Found {len(local_found)} local files.")
                all_files_queue.extend(local_found)
            else: st.warning("No valid files in this folder.")
        else: st.error("❌ Path not found.")

# Previewer
if master_file and all_files_queue:
    show_raw = st.toggle("👁️ Preview & Open Files Before Audit")
    if show_raw:
        v1, v2 = st.columns(2)
        v1.text_area("Master Source", extract_text(master_file), height=250)
        
        # Friendly names for the dropdown
        names = [f.name if hasattr(f, 'name') else os.path.basename(f) for f in all_files_queue]
        sel = v2.selectbox("Choose File to Preview:", names)
        idx = names.index(sel)
        target = all_files_queue[idx]
        
        v2.text_area(f"Preview: {sel}", extract_text(target), height=250)
        if isinstance(target, str):
            if v2.button(f"📂 Open '{sel}' on PC"):
                open_local_file(target)

st.divider()

# --- 5. EXECUTION ---
if st.button("🚀 Run Full Safety Audit"):
    if master_file and all_files_queue:
        text_master = extract_text(master_file)[:35000]
        prog = st.progress(0)
        
        for i, file in enumerate(all_files_queue):
            fname = file.name if hasattr(file, 'name') else os.path.basename(file)
            prog.progress(int(((i+1)/len(all_files_queue))*100))
            
            with st.status(f"Auditing {fname}..."):
                text_rev = extract_text(file)[:35000]
                report = run_audit(text_master, text_rev, api_key, focus_mode)
                red_html = Redlines(text_master, text_rev).output_markdown
                score = fuzz.token_set_ratio(text_master, text_rev)
                
                # Risk Logic
                has_num = any(c.isdigit() for c in report)
                alerts = [k.upper() for k in keyword_list if k in report.lower()]
                risk = "🚨 CRITICAL" if (has_num and alerts) else "🚨 HIGH" if has_num else "🟢 LOW"
                
                st.session_state.batch_log.append({"File": fname, "Match %": f"{score}%", "Risk": risk, "Alerts": ", ".join(alerts)})
                st.session_state.history.append({"time": datetime.now().strftime("%H:%M"), "files": fname, "result": report})

                st.subheader(f"📄 Result: {fname}")
                if isinstance(file, str):
                    if st.button(f"Open File: {fname}", key=f"btn_{i}"):
                        open_local_file(file)
                
                if alerts: st.markdown(f'<div class="keyword-alert">⚠️ Keywords: {", ".join(alerts)}</div>', unsafe_allow_html=True)
                
                r1, r2 = st.tabs(["📊 AI Audit Report", "🎨 Visual Redline"])
                with r1: st.markdown(report)
                with r2: st.markdown(red_html, unsafe_allow_html=True)
    else: st.warning("Ensure Master file and at least one Revised source (Upload or Local) is provided.")

# --- 6. DASHBOARD ---
if st.session_state.batch_log:
    st.divider()
    df = pd.DataFrame(st.session_state.batch_log)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Batch", len(df))
    c2.metric("Critical Alerts", len(df[df['Risk'].str.contains("🚨")]))
    c3.metric("Avg Match %", f"{int(df['Match %'].str.replace('%','').astype(int).mean())}%")
    st.dataframe(df, use_container_width=True)
    
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Export Results to Excel", out.getvalue(), "Audit_Report.xlsx")