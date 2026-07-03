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
# ⚠️ MAKE SURE THESE STRINGS EXACTLY MATCH YOUR GITHUB URL (CASE-SENSITIVE)
GITHUB_OWNER = "Derese4803"                 # Your exact GitHub username
GITHUB_REPO = "control-sample-collection"   # Your updated repository name
CSV_FILENAME = "amhara_me_2026.csv"         # The name of your spreadsheet database

# ============================================================================
# CLOUD DATABASE STORAGE CORE LOGIC (GITHUB API)
# ============================================================================

def get_github_headers():
    """Retrieves authentication token securely from Streamlit Secret Manager"""
    token = st.secrets.get("github", {}).get("token")
    if not token:
        st.error("❌ GitHub token missing in .streamlit/secrets.toml!")
        return None
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def fetch_data_from_github() -> pd.DataFrame:
    """Downloads the current CSV database file straight from your repository"""
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
        
    # Standard schema structure falling back to your exact custom format layout
    return pd.DataFrame(columns=["id", "timestamp", "user-name", "Farmer Name", "Woreda Zone", "Kebele Locality", "Phone Link Contact", "Audio Recording Memo"])

def save_data_to_github(updated_df: pd.DataFrame) -> bool:
    """Overwrites or appends data rows to your repository spreadsheet"""
    headers = get_github_headers()
    if not headers: 
        return False
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"
    
    # Check if file exists to pull down its version SHA hash tracking identifier
    response = requests.get(url, headers=headers)
    sha = response.json()['sha'] if response.status_code == 200 else None
    
    csv_data = updated_df.to_csv(index=False)
    encoded_data = base64.b64encode(csv_data.encode()).decode()
    
    payload = {
        "message": f"Survey Sync - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": encoded_data,
        "branch": "main"  # 👈 Change to 'master' if your repo baseline uses it
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
    """Encodes standard uploaded media binaries safely into flat strings"""
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
    st.caption("Cloud Storage Subsystem Engine: Connected via GitHub Repository Tables")
    
    if st.session_state["editor"]:
        st.success(f"👤 Active Editor Profiling Mode: **{st.session_state['editor']}**")
    
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
                        # 1. Access current data spreadsheet from repo
                        df = fetch_data_from_github()
                        
                        # 2. Extract linear index sequence identifiers
                        try:
                            next_id = int(pd.to_numeric(df["id"]).max() + 1) if not df.empty and "id" in df.columns else 1
                        except:
                            next_id = len(df) + 1
                        
                        # 3. Compile new entry vector matching your exact CSV file structure
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
                        
                        # 4. Concatenate records matrices and save remote cloud file
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
        # --- AUTOMATED PERMISSIONS TESTING INSTRUMENT ---
        with st.expander("🔍 Cloud Database Connection Diagnostic Tester"):
            if st.button("Execute Verification Framework"):
                headers = get_github_headers()
                url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"
                
                res = requests.get(url, headers=headers)
                if res.status_code == 200:
                    st.success("✅ Connectivity & Read Access: SUCCESS (System can read your cloud database)")
                    scopes = res.headers.get("X-OAuth-Scopes", "")
                    if "repo" in scopes or "public_repo" in scopes:
                        st.success(f"✅ Secure Write Access: SUCCESS (Token holds 'repo' permissions. Scope map: {scopes})")
                    else:
                        st.error(f"❌ Secure Write Access: FAILED (Token missing repository scopes. Found: {scopes})")
                else:
                    st.error(f"❌ Sync Failure: Target not found (Status Code: {res.status_code}). Confirm Owner & Repository name spellings.")

        # Download database representation from repository
        df = fetch_data_from_github()
        
        col_t, col_l = st.columns([8, 2])
        col_t.header("📊 Admin Management Station")
        if col_l.button("🔒 Lock Portal"):
            st.session_state["auth"] = False
            st.rerun()

        # Check if database file has logs populated inside it
        has_records = False
        if not df.empty:
            if len(df) > 0 and not (len(df) == 1 and df.iloc[0].isna().all()):
                has_records = True

        if has_records:
            st.subheader("📥 Cloud Data Packages Extraction Modules")
            c1, c2 = st.columns(2)
            
            # Form clean text-based table spreadsheet for analytics (omits audio blobs)
            display_df = df.drop(columns=["Audio Recording Memo"]) if "Audio Recording Memo" in df.columns else df
            c1.download_button("📥 Extract Metrics Sheet (CSV)", display_df.to_csv(index=False).encode('utf-8-sig'), "Amhara_ME_Data_2026.csv", use_container_width=True)
            
            # Assemble audio recording blobs back into a direct download ZIP archive
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

            # Data clearance controller engine
            st.subheader("🗑️ Cleanse Datasets Control System")
            st.warning("Critical Warning: Confirming this option completely clears your CSV text database file from GitHub.")
            if st.button("PERMANENTLY FLUSH CLOUD REPOSITORY RECORDS", type="primary", use_container_width=True):
                empty_df = pd.DataFrame(columns=["id", "timestamp", "user-name", "Farmer Name", "Woreda Zone", "Kebele Locality", "Phone Link Contact", "Audio Recording Memo"])
                if save_data_to_github(empty_df):
                    st.success("Cloud spreadsheets successfully wiped from repository layout.")
                    st.rerun()
        else:
            st.info("No surveyor records are currently stored inside your remote GitHub cloud database file.")
