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

# Expected columns - CSV only stores metadata + audio filename reference
EXPECTED_COLS = ["id", "timestamp", "user-name", "Farmer Name", "Woreda Zone", "Kebele Locality", "Phone Link Contact", "Audio File"]

# ============================================================================
# CLOUD DATABASE STORAGE CORE LOGIC (GITHUB API)
# ============================================================================

def get_github_headers():
    token = st.secrets.get("github", {}).get("token")
    if not token:
        st.error("❌ GitHub token missing in .streamlit/secrets.toml!")
        return None
    
    # Universal support for fine-grained or classic tokens
    auth_prefix = "Bearer" if str(token).startswith("github_pat_") else "token"
    return {
        "Authorization": f"{auth_prefix} {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def fetch_data_from_github() -> pd.DataFrame:
    """Downloads CSV from GitHub cleanly without crashing or corrupting data."""
    headers = get_github_headers()
    if not headers:
        return pd.DataFrame(columns=EXPECTED_COLS)

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            return pd.DataFrame(columns=EXPECTED_COLS)

        if response.status_code == 200:
            raw_content = response.json().get('content', '')
            if not raw_content:
                return pd.DataFrame(columns=EXPECTED_COLS)
                
            content = base64.b64decode(raw_content).decode('utf-8')

            if not content or not content.strip():
                return pd.DataFrame(columns=EXPECTED_COLS)

            try:
                df = pd.read_csv(io.StringIO(content))
                
                # Check if DataFrame is valid and has expected columns
                if df.empty:
                    return pd.DataFrame(columns=EXPECTED_COLS)
                    
                # Standardize column headers
                df.columns = [str(c).strip() for c in df.columns]
                
                # Align or enforce expected columns
                for col in EXPECTED_COLS:
                    if col not in df.columns:
                        df[col] = ""
                
                df = df[EXPECTED_COLS]
                df = df.dropna(subset=['id'])
                df = df[df['id'].astype(str).str.strip() != '']
                
                return df
                
            except Exception:
                return pd.DataFrame(columns=EXPECTED_COLS)

    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        
    return pd.DataFrame(columns=EXPECTED_COLS)

def save_data_to_github(updated_df: pd.DataFrame) -> bool:
    """Saves CSV to GitHub safely."""
    headers = get_github_headers()
    if not headers:
        return False

    # Safety Guard: Never write a completely malformed/empty dataset unless intentional
    if updated_df is None or not isinstance(updated_df, pd.DataFrame):
        st.error("❌ Refused to save corrupted DataFrame object.")
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"

    sha = None
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            sha = response.json().get('sha')
    except Exception:
        pass

    # Clean missing values before CSV string export
    export_df = updated_df[EXPECTED_COLS].fillna("")
    csv_data = export_df.to_csv(index=False)
    encoded_data = base64.b64encode(csv_data.encode('utf-8')).decode('utf-8')

    payload = {
        "message": f"Survey Sync - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": encoded_data,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
        
    try:
        res = requests.put(url, headers=headers, json=payload, timeout=15)
        if res.status_code in [200, 201]:
            return True
        else:
            st.error(f"GitHub API error: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        st.error(f"Network error during upload: {str(e)}")
        return False

def upload_file_to_github(filename: str, file_bytes: bytes) -> bool:
    """Uploads binary audio file to GitHub repo root."""
    headers = get_github_headers()
    if not headers:
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{filename}"

    # Get SHA if file already exists to avoid 409 Conflict
    sha = None
    try:
        check_res = requests.get(url, headers=headers, timeout=10)
        if check_res.status_code == 200:
            sha = check_res.json().get('sha')
    except Exception:
        pass

    encoded_data = base64.b64encode(file_bytes).decode('utf-8')

    payload = {
        "message": f"Upload Audio Memo: {filename}",
        "content": encoded_data,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
    
    try:
        res = requests.put(url, headers=headers, json=payload, timeout=60)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"Upload error for {filename}: {str(e)}")
        return False

def fetch_file_from_github(filename: str) -> bytes:
    """Downloads binary file from repo root."""
    headers = get_github_headers()
    if not headers:
        return b""

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{filename}"

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return base64.b64decode(response.json()['content'])
    except Exception:
        pass
    return b""

def delete_file_from_github(filename: str) -> bool:
    """Deletes file from repo root."""
    headers = get_github_headers()
    if not headers:
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{filename}"

    sha = None
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            sha = response.json().get('sha')
    except Exception:
        pass

    if not sha:
        return True

    payload = {
        "message": f"Delete {filename}",
        "sha": sha,
        "branch": "main"
    }

    try:
        res = requests.delete(url, headers=headers, json=payload, timeout=10)
        return res.status_code in [200, 204]
    except Exception:
        return False

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
    
    if st.session_state['editor']:
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
    
    if not st.session_state['editor']:
        with st.container(border=True):
            st.subheader("Field Agent Authentication")
            name_in = st.text_input("Registered By (Your Full Name):")
            if st.button("Initialize Terminal Session"):
                if name_in.strip():
                    st.session_state['editor'] = name_in.strip()
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
                        # 1. Pull latest current DataFrame state safely
                        df = fetch_data_from_github()
                        
                        # Calculate robust Next ID
                        if not df.empty and "id" in df.columns:
                            valid_ids = pd.to_numeric(df["id"], errors='coerce').dropna()
                            next_id = int(valid_ids.max() + 1) if not valid_ids.empty else 1
                        else:
                            next_id = 1
                        
                        # 2. Process audio upload separately
                        audio_filename = ""
                        if audio is not None:
                            safe_name = "".join([c for c in f_name if c.isalnum() or c in ('_', '-')])[:20]
                            ext = audio.name.split(".")[-1] if "." in audio.name else "mp3"
                            audio_filename = f"audio_ID{next_id}_{safe_name}.{ext}"
                            audio_bytes = audio.getvalue()
                            
                            st.info(f"📤 Uploading {len(audio_bytes):,} bytes audio...")
                            upload_success = upload_file_to_github(audio_filename, audio_bytes)
                            
                            if upload_success:
                                st.success(f"✅ Audio file committed: {audio_filename}")
                            else:
                                st.warning("⚠️ Audio file upload failed, but logging text record...")
                                audio_filename = ""

                        # 3. Formulate new record entry
                        new_row = {
                            "id": next_id,
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "user-name": str(st.session_state["editor"]),
                            "Farmer Name": str(f_name),
                            "Woreda Zone": str(woreda),
                            "Kebele Locality": str(kebele),
                            "Phone Link Contact": str(phone),
                            "Audio File": str(audio_filename)
                        }
                        
                        new_entry_df = pd.DataFrame([new_row])
                        
                        # 4. Safe concat with column enforcing
                        if df.empty:
                            updated_df = new_entry_df
                        else:
                            updated_df = pd.concat([df, new_entry_df], ignore_index=True)
                        
                        # 5. Push non-corrupted CSV to GitHub
                        if save_data_to_github(updated_df):
                            st.success(f"✅ Sync Successful! Record #{next_id} logged for {f_name}.")
                        else:
                            st.error("❌ CSV update rejected by GitHub API.")
                else:
                    st.error("Name, Woreda, and Kebele are mandatory.")

# ============================================================================
# INTERFACE: ADMINISTRATIVE COMPLIANCE PANELS
# ============================================================================
elif st.session_state["page"] == "Data":
    st.button("⬅️ Back to Home Layout", on_click=lambda: nav("Home"))
    
    if not st.session_state['auth']:
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
        if not df.empty and len(df) > 0:
            has_records = True

        if has_records:
            st.subheader("📈 Survey Analytics Overview")
            
            total_records = len(df)
            audio_count = 0
            if "Audio File" in df.columns:
                audio_count = df["Audio File"].apply(lambda x: pd.notna(x) and str(x).strip() != "").sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("📋 Total Records", total_records)
            m2.metric("🎤 Audio Files", audio_count)
            m3.metric("👥 Active Agents", df["user-name"].nunique() if "user-name" in df.columns else 0)
            
            st.divider()
            
            st.subheader("👤 Agent Performance Breakdown")
            if "user-name" in df.columns:
                user_stats = df.groupby("user-name").agg(
                    Records=("id", "count"),
                    Audio_Files=("Audio File", lambda x: x.apply(lambda v: pd.notna(v) and str(v).strip() != "").sum())
                ).reset_index()
                user_stats.columns = ["Agent Name", "Records Entered", "Audio Files"]
                user_stats = user_stats.sort_values("Records Entered", ascending=False)
                st.dataframe(user_stats, use_container_width=True, hide_index=True)
                st.bar_chart(user_stats.set_index("Agent Name")["Records Entered"])
            
            st.divider()
            
            st.subheader("📥 Cloud Data Packages Extraction Modules")
            c1, c2 = st.columns(2)
            
            display_df = df.drop(columns=["Audio File"], errors="ignore")
            c1.download_button("📥 Extract Metrics Sheet (CSV)", display_df.to_csv(index=False).encode('utf-8-sig'), "Amhara_ME_Data_2026.csv", use_container_width=True)
            
            with st.spinner("Packing audio files..."):
                z_buf = BytesIO()
                with zipfile.ZipFile(z_buf, "w") as zf:
                    audio_found = 0
                    for idx, row in df.iterrows():
                        audio_fn = str(row.get('Audio File', '')).strip()
                        if audio_fn and audio_fn != "nan":
                            audio_bytes = fetch_file_from_github(audio_fn)
                            if audio_bytes and len(audio_bytes) > 0:
                                zf.writestr(audio_fn, audio_bytes)
                                audio_found += 1
                                
            c2.download_button("🎤 Extract Audio Recordings (ZIP)", z_buf.getvalue(), "Amhara_ME_Audios.zip", use_container_width=True)

            st.divider()

            st.subheader("🗑️ Cleanse Datasets Control System")
            st.warning("Critical Warning: This clears ALL data from GitHub.")
            if st.button("PERMANENTLY FLUSH ALL RECORDS", type="primary", use_container_width=True):
                for idx, row in df.iterrows():
                    audio_fn = str(row.get('Audio File', '')).strip()
                    if audio_fn and audio_fn != "nan":
                        delete_file_from_github(audio_fn)
                empty_df = pd.DataFrame(columns=EXPECTED_COLS)
                if save_data_to_github(empty_df):
                    st.success("All records wiped.")
                    st.rerun()
        else:
            st.info("No surveyor records are currently stored inside your remote GitHub cloud database file.")
