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

# Custom UI Styling (Fixed for Streamlit 2026)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    ins { background-color: #d4edda; text-decoration: none; color: #155724; padding: 2px; border-radius: 3px; }
    del { background-color: #f8d7da; color: #721c24; padding: 2px; border-radius: 3px; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
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
    st.header("📜 Session History")
    if st.session_state.history:
        for item in reversed(st.session_state.history[-5:]): # Show last 5
            with st.expander(f"{item['time']} - {item['files']}"):
                st.markdown(item['result'])
    
    if st.button("🗑️ Clear Batch Results"):
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

def run_audit(text_a, text_b, key, mode):
    client = genai.Client(api_key=key)
    model_id = "gemini-3.1-flash-lite-preview" 
    config = types.GenerateContentConfig(
        system_instruction=f"You are a Professional Auditor. Mode: {mode}. Use 🟢[ADD], 🔴[DEL], 🟠[MOD]. Include 5-word 'Context Anchors' for changes.",
        temperature=0.0
    )
    prompt = f"ORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"
    response = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return response.text

# --- 4. MAIN INTERFACE ---
st.title("🔍 Smart-Diff Pro")
st.caption("All-in-One Enterprise Auditor | 2026 Fleet Optimization")

col_orig, col_rev = st.columns(2)
with col_orig:
    master_file = st.file_uploader("📂 Master Document (Source)", type=['pdf', 'docx'])
with col_rev:
    rev_files = st.file_uploader("📂 Revised Batch (Comparison)", type=['pdf', 'docx'], accept_multiple_files=True)

# RESTORED: Side-by-Side Raw Text Visualizer
show_raw = st.toggle("👁️ Show Side-by-Side Raw Text Viewer")
if show_raw and master_file:
    v_col1, v_col2 = st.columns(2)
    raw_master = extract_text(master_file)
    with v_col1:
        st.info(f"Master: {master_file.name}")
        st.text_area("Master Content", raw_master, height=250)
    with v_col2:
        if rev_files:
            sel_rev = st.selectbox("Select File to Compare Raw Text", [f.name for f in rev_files])
            curr_rev_file = next(f for f in rev_files if f.name == sel_rev)
            st.text_area(f"Revised Content: {sel_rev}", extract_text(curr_rev_file), height=250)
        else:
            st.warning("Upload revised files to use side-by-side view.")

st.divider()

# --- 5. EXECUTION ---
if st.button("🚀 Run Full Safety Audit"):
    if not api_key:
        st.error("API Key missing in Secrets.")
    elif master_file and rev_files:
        text_master = extract_text(master_file)[:35000]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, rev in enumerate(rev_files):
            percent = int(((index + 1) / len(rev_files)) * 100)
            progress_bar.progress(percent)
            status_text.info(f"Auditing {index + 1}/{len(rev_files)}: **{rev.name}**")
            
            with st.status(f"Analyzing {rev.name}...", expanded=False) as status:
                text_rev = extract_text(rev)[:35000]
                
                # Visual Redline Generation
                redline = Redlines(text_master, text_rev)
                redline_html = redline.output_markdown
                
                # Similarity Scoring
                score = fuzz.token_set_ratio(text_master, text_rev)
                
                try:
                    report = run_audit(text_master, text_rev, api_key, focus_mode)
                    
                    # Safety Guard: Check for numerical changes in the AI text
                    has_nums = any(char.isdigit() for char in report)
                    risk_tag = "🚨 HIGH (Numerical)" if has_nums else "🟡 MEDIUM" if score < 95 else "🟢 LOW"

                    # Save to History and Batch Log
                    st.session_state.history.append({"time": datetime.now().strftime("%H:%M"), "files": rev.name, "result": report})
                    st.session_state.batch_log.append({
                        "Timestamp": datetime.now().strftime("%H:%M:%S"),
                        "File Name": rev.name,
                        "Match %": f"{score}%",
                        "Risk": risk_tag,
                        "AI Summary": report[:250].replace("\n", " ") + "..."
                    })
                    
                    # Display Results for this file
                    st.subheader(f"📄 Result: {rev.name} ({risk_tag})")
                    tab_ai, tab_red = st.tabs(["📊 AI Audit Report", "🎨 Visual Redline"])
                    with tab_ai:
                        st.markdown(report)
                    with tab_red:
                        st.markdown(redline_html, unsafe_allow_html=True)
                    
                    st.download_button(f"📥 Download MD: {rev.name}", report, file_name=f"audit_{rev.name}.md", key=f"dl_{index}")
                    status.update(label=f"Done: {rev.name}", state="complete")
                except Exception as e:
                    st.error(f"Error processing {rev.name}: {e}")
        
        status_text.success(f"✅ Batch Audit Complete! {len(rev_files)} files processed.")
    else:
        st.warning("Please upload both Master and Revised files.")

# --- 6. DATA DASHBOARD & EXPORT ---
if st.session_state.batch_log:
    st.divider()
    st.subheader("📊 Master Audit Trail")
    df = pd.DataFrame(st.session_state.batch_log)
    
    # Dash Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Audited", len(df))
    m2.metric("Safety Risks (🚨)", len(df[df['Risk'].str.contains("🚨")]))
    m3.metric("Avg Similarity", f"{int(df['Match %'].str.replace('%','').astype(int).mean())}%")
    
    st.dataframe(df, use_container_width=True)
    
    # Excel Download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Audit_Summary')
    
    st.download_button("📥 Export Full Audit Log to Excel", data=output.getvalue(), 
                       file_name=f"Audit_Log_{datetime.now().strftime('%Y%m%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")