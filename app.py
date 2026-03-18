import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from docx import Document
import io
import re
from datetime import datetime

# --- 1. Page & Security Configuration ---
st.set_page_config(page_title="Smart-Diff Pro", layout="wide", page_icon="🔍")

# Password Protection
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123") 

# --- 2. Initialize Session History ---
if "history" not in st.session_state:
    st.session_state.history = []

# --- 3. API & Model Setup ---
api_key = st.secrets.get("GEMINI_API_KEY")

def get_ai_response(text_a, text_b, key):
    genai.configure(api_key=key)
    system_instr = """
    ROLE: Professional Document Auditor.
    OBJECTIVE: Conduct a high-precision semantic comparison.
    FORMAT: Use 🟢[ADD], 🔴[DEL], 🟠[MOD], 🔵[MOVE]. 
    Be concise. Ignore formatting.
    """
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        system_instruction=system_instr,
        generation_config={"temperature": 0, "max_output_tokens": 4096}
    )
    user_prompt = f"Original (A):\n{text_a}\n\nRevised (B):\n{text_b}"
    response = model.generate_content(user_prompt)
    return response.text

# --- 4. Helper Functions ---
def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_text(uploaded_file):
    try:
        if uploaded_file.name.endswith('.pdf'):
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            return clean_text("\n".join([page.get_text() for page in doc]))
        elif uploaded_file.name.endswith('.docx'):
            doc = Document(io.BytesIO(uploaded_file.read()))
            return clean_text("\n".join([para.text for para in doc]))
    except Exception as e:
        st.error(f"Error: {e}")
    return ""

# --- 5. User Interface ---
with st.sidebar:
    st.header("🔐 Access")
    pwd_input = st.text_input("App Password", type="password")
    
    st.divider()
    st.header("📜 Session History")
    if st.session_state.history:
        for idx, item in enumerate(reversed(st.session_state.history)):
            with st.expander(f"{item['time']} - {item['files']}"):
                st.markdown(item['result'])
    else:
        st.write("No comparisons yet.")

st.title("🔍 Smart-Diff Pro")

if pwd_input != APP_PASSWORD:
    st.warning("Please enter the correct App Password.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Upload Original", type=['pdf', 'docx'])
with col2:
    file_b = st.file_uploader("Upload Revised", type=['pdf', 'docx'])

if st.button("🚀 Execute Semantic Audit"):
    if not api_key:
        st.error("API Key missing in Secrets.")
    elif file_a and file_b:
        with st.spinner("Analyzing..."):
            raw_a = extract_text(file_a)[:35000]
            raw_b = extract_text(file_b)[:35000]
            
            try:
                report = get_ai_response(raw_a, raw_b, api_key)
                
                # Save to History
                timestamp = datetime.now().strftime("%H:%M:%S")
                st.session_state.history.append({
                    "time": timestamp,
                    "files": f"{file_a.name} vs {file_b.name}",
                    "result": report
                })
                
                st.divider()
                st.subheader("📋 Current Audit Findings")
                st.markdown(report)
                st.download_button("📥 Download This Report", report, file_name=f"audit_{timestamp}.md")
            except Exception as e:
                st.error(f"Audit failed: {e}")
    else:
        st.warning("Both files are required.")