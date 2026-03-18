import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import re
import pandas as pd
from datetime import datetime
from thefuzz import fuzz

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Password & API Keys from Secrets
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")
api_key = st.secrets.get("GEMINI_API_KEY")

if "history" not in st.session_state:
    st.session_state.history = []
if "batch_log" not in st.session_state:
    st.session_state.batch_log = []

# --- 2. SIDEBAR: CONTROLS & HISTORY ---
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter App Password", type="password")
    
    st.divider()
    st.header("⚙️ Audit Profile")
    focus_mode = st.radio(
        "Select Sensitivity:",
        ["Strict Audit", "Logic Only", "Summary"],
        help="Strict: Every char | Logic: Dates/Numbers | Summary: General intent"
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
    st.warning("Locked. Enter password in sidebar.")
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
    except Exception:
        return ""

def get_system_instruction(mode):
    base = "You are a Professional Auditor. Compare Original (A) and Revised (B)."
    if mode == "Strict Audit":
        return base + " Flag EVERY change including punctuation. Use 🟢[ADD], 🔴[DEL], 🟠[MOD]."
    elif mode == "Logic Only":
        return base + " Only flag changes in dates, numbers, part numbers, and 'Yes/No' instructions."
    return base + " Provide a high-level summary of intent and major changes."

def run_audit(text_a, text_b, key, mode):
    client = genai.Client(api_key=key)
    # Using the 2026 stable model ID you requested
    model_id = "gemini-3.1-flash-lite-preview" 
    
    config = types.GenerateContentConfig(
        system_instruction=get_system_instruction(mode),
        temperature=0.0
    )
    
    prompt = f"AUDIT TASK: Compare Original vs Revised. Provide 'Context Anchors' (5 words before/after) for MODs.\n\nORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"
    
    response = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return response.text

# --- 5. MAIN UI ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Enterprise Auditor | Batch Processing | Zero-Cost Optimization")

col_orig, col_rev = st.columns(2)
with col_orig:
    master_file = st.file_uploader("📂 Upload Master (Source)", type=['pdf', 'docx'])
with col_rev:
    rev_files = st.file_uploader("📂 Upload Revised (Batch)", type=['pdf', 'docx'], accept_multiple_files=True)

# Side-by-Side Visualizer Toggle (From Version 1)
show_raw = st.toggle("👁️ Open Side-by-Side Raw Text Viewer")
if show_raw and master_file:
    v_col1, v_col2 = st.columns(2)
    raw_master = extract_text(master_file)
    with v_col1:
        st.caption(f"Master: {master_file.name}")
        st.text_area("Master Content", raw_master, height=200)
    with v_col2:
        if rev_files:
            sel_rev = st.selectbox("Select File to Compare", [f.name for f in rev_files])
            curr_rev = next(f for f in rev_files if f.name == sel_rev)
            st.text_area("Revised Content", extract_text(curr_rev), height=200)

st.divider()

if st.button("🚀 Run Semantic Batch Audit"):
    if not api_key:
        st.error("API Key missing in Secrets.")
    elif master_file and rev_files:
        text_master = extract_text(master_file)[:35000]
        
        for rev in rev_files:
            with st.status(f"Auditing {rev.name}...", expanded=True) as status:
                text_rev = extract_text(rev)[:35000]
                
                # Similarity Score (Free logic)
                score = fuzz.token_set_ratio(text_master, text_rev)
                risk = "Low" if score > 90 else "Medium" if score > 75 else "High"
                
                try:
                    report = run_audit(text_master, text_rev, api_key, focus_mode)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    # Store in History & Batch Log
                    st.session_state.history.append({"time": timestamp, "files": rev.name, "result": report})
                    st.session_state.batch_log.append({
                        "File": rev.name, "Match %": f"{score}%", "Risk": risk, "Audit Summary": report[:200] + "..."
                    })
                    
                    st.subheader(f"📋 Report: {rev.name} ({score}% Match)")
                    st.markdown(report)
                    st.download_button(f"📥 Download {rev.name} Report", report, file_name=f"audit_{rev.name}.md")
                    status.update(label=f"Done: {rev.name}", state="complete")
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.warning("Upload Master and at least one Revised file.")

# --- 6. EXCEL EXPORT (From Version 2) ---
if st.session_state.batch_log:
    st.divider()
    st.subheader("📊 Master Audit Trail")
    df = pd.DataFrame(st.session_state.batch_log)
    st.dataframe(df, use_container_width=True)
    
    # Export logic
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Audit_Summary')
    
    st.download_button(
        "📥 Download Full Audit Log (Excel)",
        data=output.getvalue(),
        file_name=f"Master_Audit_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )