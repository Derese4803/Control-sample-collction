import streamlit as st
import pandas as pd
import base64
import zipfile
import datetime
import io
import requests
from io import BytesIO

# ============================================================================
# GITHUB ENVIRONMENT CONFIGURATION
# ============================================================================
GITHUB_OWNER = "Derese4803"                 
GITHUB_REPO = "control-sample-collction"
CSV_FILENAME = "amhara_me_2026.csv"         

# ============================================================================
# CLOUD DATABASE STORAGE CORE LOGIC (GITHUB API)
# ============================================================================

def get_github_headers():
    token = st.secrets.get("github", {}).get("token")
    if not token:
        st.error("❌ GitHub token missing in .streamlit/secrets.toml!")
        return None
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def fetch_data_from_github() -> pd.DataFrame:
    headers = get_github_headers()
    if not headers: 
        return pd.DataFrame()
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            content = base64.b64decode(response.json()['content']).decode('utf-8')
            return pd.read_csv(io.StringIO(content))
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        
    return pd.DataFrame(columns=["id", "timestamp", "user-name", "Farmer Name", "Woreda Zone", "Kebele Locality", "Phone Link Contact", "Audio Recording Memo"])

def save_data_to_github(updated_df: pd.DataFrame) -> bool:
    headers = get_github_headers()
    if not headers: 
        return False
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"
    
    response = requests.get(url, headers=headers)
    sha = response.json()['sha'] if response.status_code == 200 else None
    
    csv_data = updated_df.to_csv(index=False)
    encoded_data = base64.b64encode(csv_data.encode()).decode()
    
    payload = {
        "message": f"Survey Sync - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": encoded_data,
        "branch": "main"  
    }
    if sha: 
        payload["sha"] = sha
        
    try:
        res = requests.put(url, headers=headers, json=payload, timeout=10)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"Network error during upload: {str(e)}")
        return False

def to_b64(file):
    \"\"\"Encodes standard uploaded media binaries safely into flat strings\"\"\"
    if file: 
        return base64.b64encode(file.getvalue()).decode()
    return ""

# ============================================================================
# STATE ROUTING MANAGEMENT
# ============================================================================
if "page" not in st.session_state: st.session_state["page"] = "Home"
if "auth" not in st.session_state: st.session_state["auth"] = False
if "editor" not in st.session_state: st.session_state["editor"] = None

def nav(p):
    st.session_state["page"] = p
    st.rerun()

# ============================================================================
# INTERFACE: HOME SCREEN
# ============================================================================
if st.session_state["page"] == "Home":
    st.title("🌾 Amhara M&E Survey 2026")
    
    if st.session_state["editor"]:
        st.success(f"👤 Active Editor: **{st.session_state['editor']}**")
    
    st.divider()
    col1, col2 = st.columns(2)
    if col1.button("📝 NEW REGISTRATION", use_container_width=True, type="primary"): 
        nav("Reg")
    if col2.button("📊 ADMIN DASHBOARD", use_container_width=True): 
        nav("Data")

# ============================================================================
# INTERFACE: REGISTRATION FORM
# ============================================================================
elif st.session_state["page"] == "Reg":
    st.button("⬅️ Back to Home Layout", on_click=lambda: nav("Home"))
    
    if not st.session_state["editor"]:
        with st.container(border=True):
            st.subheader("Field Agent Authentication")
            name_in = st.text_input("Registered By (Your Full Name):")
            if st.button("Initialize Terminal Session"):
                if name_in.strip():
                    st.session_state["editor"] = name_in.strip()
                    st.rerun()
    else:
        with st.form("reg_form", clear_on_submit=True):
            st.info(f"Logging Metrics Data As: {st.session_state['editor']}")
            f_name = st.text_input("Farmer Name")
            woreda = st.text_input("Woreda Zone")
            kebele = st.text_input("Kebele Locality")
            phone = st.text_input("Phone Link Contact")
            audio = st.file_uploader("🎤 Audio Recording Memo", type=['mp3','wav','m4a'])
            
            if st.form_submit_button("Save Registration Metadata"):
                if f_name and woreda and kebele:
                    with st.spinner("Processing transaction package to cloud..."):
                        df = fetch_data_from_github()
                        
                        try:
                            next_id = int(pd.to_numeric(df["id"]).max() + 1) if not df.empty and "id" in df.columns else 1
                        except:
                            next_id = len(df) + 1
                        
                        new_entry = pd.DataFrame([{
                            "id": next_id,
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "user-name": st.session_state["editor"],
                            "Farmer Name": f_name,
                            "Woreda Zone": woreda,
                            "Kebele Locality": kebele,
                            "Phone Link Contact": phone,
                            "Audio Recording Memo": to_b64(audio)
                        }])
                        
                        updated_df = pd.concat([df, new_entry], ignore_index=True)
                        if save_data_to_github(updated_df):
                            st.success(f"✅ Sync Successful! Record securely logged to GitHub Cloud for {f_name}.")
                        else:
                            st.error("❌ Cloud transaction rejected. Verify access permissions or repository configurations.")
                else:
                    st.error("Name, Woreda, and Kebele data fields are strictly mandatory.")

# ============================================================================
# INTERFACE: ADMINISTRATIVE COMPLIANCE PANELS
# ============================================================================
elif st.session_state["page"] == "Data":
    st.button("⬅️ Back to Home Layout", on_click=lambda: nav("Home"))
    
    if not st.session_state["auth"]:
        st.header("🔒 Executive Access Verification")
        pass_input = st.text_input("Enter Root Passcode Token", type="password")
        if st.button("Validate Security Token"):
            if pass_input == "oaf2026": 
                st.session_state["auth"] = True
                st.rerun()
            else:
                st.error("Invalid passcode token entered.")
    else:
        df = fetch_data_from_github()
        
        col_t, col_l = st.columns([8, 2])
        col_t.header("📊 Admin Management Station")
        if col_l.button("🔒 Lock Portal"):
            st.session_state["auth"] = False
            st.rerun()

        has_records = False
        if not df.empty:
            if len(df) > 0 and not (len(df) == 1 and df.iloc[0].isna().all()):
                has_records = True

        if has_records:
            # ================================================================
            # ANALYTICS DASHBOARD
            # ================================================================
            st.subheader("📈 Survey Analytics Overview")
            
            total_records = len(df)
            audio_count = 0
            if "Audio Recording Memo" in df.columns:
                audio_count = df["Audio Recording Memo"].apply(lambda x: pd.notna(x) and str(x).strip() != "").sum()
            
            # Metrics cards
            m1, m2, m3 = st.columns(3)
            m1.metric("📋 Total Records", total_records)
            m2.metric("🎤 Audio Attachments", audio_count)
            m3.metric("👥 Active Agents", df["user-name"].nunique() if "user-name" in df.columns else 0)
            
            st.divider()
            
            # Per-user breakdown
            st.subheader("👤 Agent Performance Breakdown")
            if "user-name" in df.columns:
                user_stats = df.groupby("user-name").agg(
                    Records=("id", "count"),
                    Audio_Submissions=("Audio Recording Memo", lambda x: x.apply(lambda v: pd.notna(v) and str(v).strip() != "").sum())
                ).reset_index()
                user_stats.columns = ["Agent Name", "Records Entered", "Audio Uploaded"]
                user_stats = user_stats.sort_values("Records Entered", ascending=False)
                st.dataframe(user_stats, use_container_width=True, hide_index=True)
                
                # Simple bar chart
                st.bar_chart(user_stats.set_index("Agent Name")["Records Entered"])
            
            st.divider()
            
            st.subheader("📥 Cloud Data Packages Extraction Modules")
            c1, c2 = st.columns(2)
            
            display_df = df.drop(columns=["Audio Recording Memo"]) if "Audio Recording Memo" in df.columns else df
            c1.download_button("📥 Extract Metrics Sheet (CSV)", display_df.to_csv(index=False).encode('utf-8-sig'), "Amhara_ME_Data_2026.csv", use_container_width=True)
            
            with st.spinner("Decoding audio binary streams from database..."):
                z_buf = BytesIO()
                with zipfile.ZipFile(z_buf, "w") as zf:
                    for idx, row in df.iterrows():
                        audio_str = row.get('Audio Recording Memo', '')
                        if pd.notna(audio_str) and str(audio_str).strip() != "":
                            try:
                                binary_audio = base64.b64decode(audio_str)
                                farmer_name = str(row.get('Farmer Name', f'Unknown_{idx}')).replace(" ", "_")
                                zf.writestr(f"ID_{row.get('id', idx)}_{farmer_name}.mp3", binary_audio)
                            except:
                                pass
            c2.download_button("🎤 Extract Voice Recordings Archive (ZIP)", z_buf.getvalue(), "Amhara_ME_Audios.zip", use_container_width=True)

            st.divider()

            st.subheader("🗑️ Cleanse Datasets Control System")
            st.warning("Critical Warning: Confirming this option completely clears your CSV text database file from GitHub.")
            if st.button("PERMANENTLY FLUSH CLOUD REPOSITORY RECORDS", type="primary", use_container_width=True):
                empty_df = pd.DataFrame(columns=["id", "timestamp", "user-name", "Farmer Name", "Woreda Zone", "Kebele Locality", "Phone Link Contact", "Audio Recording Memo"])
                if save_data_to_github(empty_df):
                    st.success("Cloud spreadsheets successfully wiped from repository layout.")
                    st.rerun()
        else:
            st.info("No surveyor records are currently stored inside your remote GitHub cloud database file.")
"""

# Write with raw string to avoid escaping issues
with open('/mnt/agents/output/app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

# Verify it's valid Python
import ast
try:
    with open('/mnt/agents/output/app.py', 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print("✅ Syntax valid! File saved.")
    print(f"Total lines: {len(code.splitlines())}")
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
