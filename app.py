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
from redlines import Redlines

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Custom UI Styling
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 10px; border: 1px solid #e0e0e0; }
    ins { background-color: #d4edda; text-decoration: none; color: #155724; padding: 2px; }
    del { background-color: #f8d7da; color: #721c24; padding: 2px; }
    </style>
    """, unsafe_allow_html=True)

APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")
api_key = st.secrets.get("GEMINI_API_KEY")

if "history" not in st.session_state:
    st.session_state.history = []
if "batch_log" not in st.session_state:
    st.session_state.batch_log = []

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter App Password", type="password")
    
    st.divider()
    st.header("⚙️ Audit Profile")
    focus_mode = st.radio("Sensitivity Level:", ["Strict Audit", "Logic Only", "Summary"])
    
    st.divider()
    if st.button("🗑️ Clear Current Batch"):
        st.session_state.batch_log = []
        st.rerun()

if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Locked. Please enter the App Password in the sidebar.")
    st.stop()

# --- 3. UTILITIES ---
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
    except Exception: return ""

def get_system_instruction(mode):
    base = "You are a Professional Document Auditor for Aviation Maintenance. Compare Original (A) and Revised (B)."
    if mode == "Strict Audit":
        return base + " Flag EVERY change including punctuation. Use 🟢[ADD], 🔴[DEL], 🟠[MOD]."
    elif mode == "Logic Only":
        return base + " ONLY flag changes in dates, numbers, part numbers, and instructions. Ignore grammar."
    return base + " Provide a high-level summary of intent and major changes only."

def run_audit(text_a, text_b, key, mode):
    client = genai.Client(api_key=key)
    model_id = "gemini-3.1-flash-lite-preview" 
    config = types.GenerateContentConfig(system_instruction=get_system_instruction(mode), temperature=0.0)
    prompt = f"Compare these texts. Provide 'Context Anchors' (5 words before/after) for MODs.\n\nORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"
    response = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return response.text

# --- 4. MAIN INTERFACE ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Optimized Auditor | Safety Guard Enabled")

col_orig, col_rev = st.columns(2)
with col_orig:
    master_file = st.file_uploader("📂 Master Document (Source)", type=['pdf', 'docx'])
with col_rev:
    rev_files = st.file_uploader("📂 Revised Batch (Comparison)", type=['pdf', 'docx'], accept_multiple_files=True)

st.divider()

if st.button("🚀 Run Full Safety Audit"):
    if not api_key:
        st.error("API Key missing.")
    elif master_file and rev_files:
        text_master = extract_text(master_file)[:35000]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, rev in enumerate(rev_files):
            percent = int(((index + 1) / len(rev_files)) * 100)
            progress_bar.progress(percent)
            status_text.info(f"Auditing {index + 1}/{len(rev_files)}: **{rev.name}**")
            
            with st.status(f"Processing {rev.name}...", expanded=False) as status:
                text_rev = extract_text(rev)[:35000]
                
                # FEATURE: Visual Redline (HTML tracked changes)
                redline = Redlines(text_master, text_rev)
                redline_html = redline.output_markdown
                
                # FEATURE: Similarity & Safety Guard
                score = fuzz.token_set_ratio(text_master, text_rev)
                
                try:
                    report = run_audit(text_master, text_rev, api_key, focus_mode)
                    
                    # Safety Logic: Does the change report contain numbers?
                    has_nums = any(char.isdigit() for char in report)
                    risk_tag = "🚨 HIGH (Numerical)" if has_nums else "🟡 MEDIUM (Text)" if score < 95 else "🟢 LOW"

                    st.session_state.batch_log.append({
                        "File": rev.name,
                        "Match %": f"{score}%",
                        "Risk": risk_tag,
                        "Summary": report[:200] + "..."
                    })
                    
                    st.subheader(f"📄 Result: {rev.name}")
                    tab1, tab2 = st.tabs(["📊 AI Audit Report", "🎨 Visual Redline"])
                    with tab1:
                        st.markdown(report)
                    with tab2:
                        st.markdown("##### Differences (Green = New, Red = Removed)")
                        st.markdown(redline_html, unsafe_allow_html=True)
                    
                    st.download_button(f"📥 Download {rev.name}", report, file_name=f"audit_{rev.name}.md", key=f"dl_{index}")
                    status.update(label=f"Completed: {rev.name}", state="complete")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        status_text.success("✅ Batch Audit Complete!")
    else:
        st.warning("Upload files to proceed.")

# --- 5. DATA DASHBOARD & EXCEL ---
if st.session_state.batch_log:
    st.divider()
    df = pd.DataFrame(st.session_state.batch_log)
    
    # Summary Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Files Processed", len(df))
    m2.metric("Critical Risks (🚨)", len(df[df['Risk'].str.contains("🚨")]))
    m3.metric("Avg Similarity", f"{int(df['Match %'].str.replace('%','').astype(int).mean())}%")
    
    st.dataframe(df, use_container_width=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Safety_Audit')
    
    st.download_button("📥 Export Audit Log to Excel", data=output.getvalue(), 
                       file_name=f"Safety_Audit_{datetime.now().strftime('%Y%m%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")