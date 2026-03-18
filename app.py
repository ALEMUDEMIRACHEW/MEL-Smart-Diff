import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
from docx import Document
import io
import re
import pandas as pd
from datetime import datetime
from thefuzz import fuzz # Free similarity scoring

# --- CONFIG & UI ---
st.set_page_config(page_title="Smart-Diff Pro | Zero-Cost", layout="wide")

# Session State for Batch Reports
if "batch_results" not in st.session_state:
    st.session_state.batch_results = []

with st.sidebar:
    st.header("⚙️ Audit Settings")
    focus_mode = st.radio("Focus Profile:", ["Strict", "Logic Only", "Summary"])
    st.divider()
    if st.button("🗑️ Clear Session"):
        st.session_state.batch_results = []
        st.rerun()

st.title("🔍 Smart-Diff Pro: Batch Auditor")
st.caption("Free Enterprise Edition | Zero API Costs beyond Gemini Free Tier")

# --- UTILITIES ---
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
    except Exception as e:
        return ""

def generate_excel(data_list):
    output = io.BytesIO()
    df = pd.DataFrame(data_list)
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Audit_Trail')
    return output.getvalue()

# --- MAIN INTERFACE ---
col_a, col_b = st.columns(2)
with col_a:
    master_file = st.file_uploader("Upload Master (Source)", type=['pdf', 'docx'])
with col_b:
    revised_files = st.file_uploader("Upload Revised (Batch)", type=['pdf', 'docx'], accept_multiple_files=True)

if st.button("🚀 Start Batch Audit"):
    if master_file and revised_files:
        api_key = st.secrets.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        raw_master = extract_text(master_file)[:30000]
        
        for rev in revised_files:
            with st.spinner(f"Processing {rev.name}..."):
                raw_rev = extract_text(rev)[:30000]
                
                # FEATURE 1: Free Similarity Score
                sim_score = fuzz.token_set_ratio(raw_master, raw_rev)
                
                # FEATURE 3: Prompt with Context Anchors
                prompt = f"""Compare Original vs Revised. 
                For every change, provide:
                1. Type (ADD/DEL/MOD)
                2. The Change
                3. Context Anchor: (5 words before/after the change to find it easily)
                
                ORIGINAL: {raw_master}
                REVISED: {raw_rev}"""
                
                response = client.models.generate_content(
                    model="gemini-1.5-flash", # Free tier model
                    contents=prompt
                )
                
                # Save to session data for Excel
                st.session_state.batch_results.append({
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "File Name": rev.name,
                    "Similarity Score": f"{sim_score}%",
                    "Status": "High Risk" if sim_score < 85 else "Low Risk",
                    "AI Summary": response.text[:500] + "..." # Truncated for Excel
                })
                
                # Display individual report
                with st.expander(f"📄 {rev.name} (Match: {sim_score}%)"):
                    st.markdown(response.text)
        
        st.success("Batch Complete!")
    else:
        st.warning("Please upload files first.")

# FEATURE 2: Excel Export Button
if st.session_state.batch_results:
    st.divider()
    st.subheader("📊 Master Audit Log")
    st.dataframe(st.session_state.batch_results)
    
    excel_data = generate_excel(st.session_state.batch_results)
    st.download_button(
        label="📥 Download Audit Trail (Excel)",
        data=excel_data,
        file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )