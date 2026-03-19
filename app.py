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
        else: st.error("File not found.")
    except Exception as e: st.error(f"OS Error: {e}")

def archive_file(source_path):
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
    keywords = st.text_input("Watchlist:", "Caution, Warning, Note, Limit, Torque")
    keyword_list = [k.strip().lower() for k in keywords.split(",")]
    
    st.divider()
    st.header("📜 Session History")
    for item in reversed(st.session_state.history[-5:]):
        st.caption(f"{item['time']} - {item['files']}")

if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Locked. Please enter password.")
    st.stop()

# --- 4. MAIN INTERFACE ---
st.title("🔍 Smart-Diff Pro")

# SECTION 1: MASTER (FOLDER SUPPORT INTACT)
st.subheader("1. Master Source (Source of Truth)")
m_t1, m_t2 = st.tabs(["📤 Upload Master", "📂 Local Master Folder"])
master_to_use = None

with m_t1:
    m_up = st.file_uploader("Upload Master", type=['pdf', 'docx'])
    if m_up: master_to_use = m_up

with m_t2:
    m_path = st.text_input("Master Folder Path (C:\\...):")
    if m_path:
        clean_m = os.path.normpath(m_path.strip().strip('"'))
        if os.path.exists(clean_m):
            m_files = [os.path.join(clean_m, f) for f in os.listdir(clean_m) if f.lower().endswith(('.pdf', '.docx'))]
            if m_files:
                m_sel = st.selectbox("Select Master Card from Folder:", [os.path.basename(f) for f in m_files])
                master_to_use = next(f for f in m_files if os.path.basename(f) == m_sel)

# SECTION 2: REVISED (FOLDER SUPPORT INTACT)
st.subheader("2. Revised Documents (Batch Analysis)")
r_t1, r_t2 = st.tabs(["📤 Manual Upload", "📂 Local Revised Folder"])
rev_queue = []

with r_t1:
    r_up = st.file_uploader("Upload Revised", type=['pdf', 'docx'], accept_multiple_files=True)
    if r_up: rev_queue.extend(r_up)

with r_t2:
    r_path = st.text_input("Revised Folder Path (C:\\...):")
    if r_path:
        clean_r = os.path.normpath(r_path.strip().strip('"'))
        if os.path.exists(clean_r):
            r_found = [os.path.join(clean_r, f) for f in os.listdir(clean_r) if f.lower().endswith(('.pdf', '.docx'))]
            if r_found:
                st.success(f"✅ Found {len(r_found)} files.")
                rev_queue.extend(r_found)

# Previewer
if master_to_use and rev_queue:
    if st.toggle("👁️ Preview & Open Files"):
        v1, v2 = st.columns(2)
        v1.text_area("Master Source", extract_text(master_to_use), height=200)
        r_names = [f.name if hasattr(f, 'name') else os.path.basename(f) for f in rev_queue]
        sel_r = v2.selectbox("Select Revised to Preview:", r_names)
        target_r = rev_queue[r_names.index(sel_r)]
        v2.text_area(f"Preview: {sel_r}", extract_text(target_r), height=200)
        if isinstance(target_r, str):
            if v2.button(f"📂 Open '{sel_r}'"): open_local_file(target_r)

st.divider()

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
                
                # RESTORED SAFETY LOGIC
                has_num = any(c.isdigit() for c in report)
                alerts = [k.upper() for k in keyword_list if k in report.lower()]
                risk = "🚨 CRITICAL" if (has_num and alerts) else "🚨 HIGH" if has_num else "🟢 LOW"
                
                st.session_state.batch_log.append({"File": fname, "Match %": f"{score}%", "Risk": risk, "Alerts": ", ".join(alerts)})
                st.session_state.history.append({"time": datetime.now().strftime("%H:%M"), "files": fname, "result": report})

                st.subheader(f"📄 Result: {fname}")
                c1, c2 = st.columns(2)
                if isinstance(file, str):
                    if c1.button(f"📂 Open {fname}", key=f"o_{i}"): open_local_file(file)
                    if c2.button(f"📦 Archive {fname}", key=f"a_{i}"):
                        if archive_file(file): st.success("Moved to Audited_Results")
                
                if alerts: st.markdown(f'<div class="keyword-alert">⚠️ Keywords: {", ".join(alerts)}</div>', unsafe_allow_html=True)
                tab1, tab2 = st.tabs(["📊 AI Report", "🎨 Visual Redline"])
                with tab1: st.markdown(report)
                with tab2: st.markdown(red_html, unsafe_allow_html=True)
    else: st.warning("Inputs missing.")

# --- 6. DASHBOARD ---
if st.session_state.batch_log:
    st.divider()
    df = pd.DataFrame(st.session_state.batch_log)
    st.dataframe(df, use_container_width=True)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Export Audit Log", out.getvalue(), "Audit_Report.xlsx")