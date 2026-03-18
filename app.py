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

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Custom CSS for a cleaner look
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stStatus { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Credentials from st.secrets
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")
api_key = st.secrets.get("GEMINI_API_KEY")

if "history" not in st.session_state:
    st.session_state.history = []
if "batch_log" not in st.session_state:
    st.session_state.batch_log = []

# --- 2. SIDEBAR: SETTINGS & HISTORY ---
with st.sidebar:
    st.header("🔐 Access Control")
    pwd_input = st.text_input("Enter App Password", type="password")
    
    st.divider()
    st.header("⚙️ Audit Profile")
    focus_mode = st.radio(
        "Sensitivity Level:",
        ["Strict Audit", "Logic Only", "Summary"],
        help="Strict: Every char | Logic: Dates/Numbers | Summary: Intent only"
    )
    
    st.divider()
    st.header("📜 Session History")
    if st.session_state.history:
        for item in reversed(st.session_state.history):
            with st.expander(f"{item['time']} - {item['files']}"):
                st.markdown(item['result'])
    else:
        st.caption("No recent audits in this session.")

# --- 3. LOGIN GATE ---
if pwd_input != APP_PASSWORD:
    st.title("🔍 Smart-Diff Pro")
    st.warning("Please enter the App Password in the sidebar to unlock the tool.")
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
    base = "You are a Professional Document Auditor. Compare Original (A) and Revised (B)."
    if mode == "Strict Audit":
        return base + " Flag EVERY change including punctuation. Use 🟢[ADD], 🔴[DEL], 🟠[MOD]."
    elif mode == "Logic Only":
        return base + " ONLY flag changes in dates, numbers, part numbers, and Yes/No instructions."
    return base + " Provide a high-level summary of intent and major changes without line-by-line technicalities."

def run_audit(text_a, text_b, key, mode):
    client = genai.Client(api_key=key)
    model_id = "gemini-3.1-flash-lite-preview" 
    
    config = types.GenerateContentConfig(
        system_instruction=get_system_instruction(mode),
        temperature=0.0
    )
    
    prompt = f"AUDIT TASK: Compare Original vs Revised. Provide 'Context Anchors' (5 words before/after) for MODs.\n\nORIGINAL:\n{text_a}\n\nREVISED:\n{text_b}"
    
    response = client.models.generate_content(model=model_id, contents=prompt, config=config)
    return response.text

# --- 5. MAIN INTERFACE ---
st.title("🔍 Smart-Diff Pro")
st.caption("2026 Enterprise Auditor | Batch Processing | Zero-Cost Optimization")

# File Upload Section
col_orig, col_rev = st.columns(2)
with col_orig:
    master_file = st.file_uploader("📂 Upload Master Document", type=['pdf', 'docx'])
with col_rev:
    rev_files = st.file_uploader("📂 Upload Revised Batch", type=['pdf', 'docx'], accept_multiple_files=True)

# Side-by-Side Raw Text Visualizer
show_raw = st.toggle("👁️ Show Side-by-Side Raw Text Viewer")
if show_raw and master_file:
    v_col1, v_col2 = st.columns(2)
    raw_master = extract_text(master_file)
    with v_col1:
        st.info(f"Master: {master_file.name}")
        st.text_area("Master Source Text", raw_master, height=200)
    with v_col2:
        if rev_files:
            sel_rev = st.selectbox("Select Revised File to Preview", [f.name for f in rev_files])
            curr_rev_file = next(f for f in rev_files if f.name == sel_rev)
            st.text_area("Revised Source Text", extract_text(curr_rev_file), height=200)

st.divider()

# --- 6. EXECUTION & PROGRESS DASHBOARD ---
if st.button("🚀 Run Full Batch Audit"):
    if not api_key:
        st.error("API Key missing in Secrets.")
    elif master_file and rev_files:
        text_master = extract_text(master_file)[:35000]
        
        # Progress Tracking UI
        total_files = len(rev_files)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, rev in enumerate(rev_files):
            # Update Progress Bar
            percent_complete = int(((index + 1) / total_files) * 100)
            progress_bar.progress(percent_complete)
            status_text.info(f"Auditing File {index + 1} of {total_files}: **{rev.name}**")
            
            with st.status(f"Processing {rev.name}...", expanded=False) as status:
                text_rev = extract_text(rev)[:35000]
                
                # Similarity Calculation (Free)
                score = fuzz.token_set_ratio(text_master, text_rev)
                risk_color = "🟢 Low" if score > 90 else "🟡 Medium" if score > 75 else "🔴 High"
                
                try:
                    report = run_audit(text_master, text_rev, api_key, focus_mode)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    # Store Results
                    st.session_state.history.append({"time": timestamp, "files": rev.name, "result": report})
                    st.session_state.batch_log.append({
                        "Timestamp": timestamp,
                        "File Name": rev.name,
                        "Match Score": f"{score}%",
                        "Risk Level": risk_color,
                        "AI Summary": report[:250].replace("\n", " ") + "..."
                    })
                    
                    st.subheader(f"📋 Report: {rev.name} ({score}% Match)")
                    st.markdown(report)
                    st.download_button(f"📥 Download Markdown: {rev.name}", report, file_name=f"audit_{rev.name}.md", key=f"dl_{rev.name}")
                    status.update(label=f"Completed: {rev.name}", state="complete")
                except Exception as e:
                    st.error(f"Error processing {rev.name}: {e}")
        
        status_text.success(f"✅ Batch Audit Complete! {total_files} files processed.")
    else:
        st.warning("Please upload both a Master file and at least one Revised file.")

# --- 7. RISK DASHBOARD & EXCEL LOG ---
if st.session_state.batch_log:
    st.divider()
    st.subheader("📊 Master Audit Trail & Risk Dashboard")
    
    df = pd.DataFrame(st.session_state.batch_log)
    
    # Quick Stats
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    stat_col1.metric("Total Audited", len(df))
    stat_col2.metric("High Risk Files", len(df[df['Risk Level'].str.contains("High")]))
    stat_col3.metric("Avg Match %", f"{int(df['Match Score'].str.replace('%','').astype(int).mean())}%")
    
    st.dataframe(df, use_container_width=True)
    
    # Excel Export Logic
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Audit_Summary')
    
    st.download_button(
        "📥 Download Master Audit Log (Excel)",
        data=output.getvalue(),
        file_name=f"Audit_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )