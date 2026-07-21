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
AUDIO_FOLDER = "audio"

# Expected columns
EXPECTED_COLS = ["id", "timestamp", "user-name", "Farmer Name", "Woreda Zone", "Kebele Locality", "Phone Link Contact", "Audio Filename", "Audio Base64"]

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
        return pd.DataFrame(columns=EXPECTED_COLS)

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            return pd.DataFrame(columns=EXPECTED_COLS)

        if response.status_code == 200:
            content = base64.b64decode(response.json()['content']).decode('utf-8')

            if not content or not content.strip():
                return pd.DataFrame(columns=EXPECTED_COLS)

            try:
                df = pd.read_csv(io.StringIO(content))
                actual_cols = [str(c).strip().lower() for c in df.columns]
                expected_cols_lower = [c.lower() for c in EXPECTED_COLS]
                
                if set(actual_cols) != set(expected_cols_lower):
                    return pd.DataFrame(columns=EXPECTED_COLS)
                
                df.columns = EXPECTED_COLS
                df = df.dropna(subset=['id'])
                df = df[df['id'].astype(str).str.strip() != '']
                
                return df
                
            except pd.errors.EmptyDataError:
                return pd.DataFrame(columns=EXPECTED_COLS)

    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        
    return pd.DataFrame(columns=EXPECTED_COLS)

def save_data_to_github(updated_df: pd.DataFrame) -> bool:
    headers = get_github_headers()
    if not headers:
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"

    sha = None
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            sha = response.json().get('sha')
    except Exception:
        pass

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
        if res.status_code in [200, 201]:
            return True
        else:
            st.error(f"GitHub API error: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        st.error(f"Network error during upload: {str(e)}")
        return False

def upload_audio_to_github(filename, file_bytes):
    """Uploads audio file to audio/ folder. Returns (success, error_msg)"""
    headers = get_github_headers()
    if not headers:
        return False, "No GitHub headers available"

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{AUDIO_FOLDER}/{filename}"

    if len(file_bytes) > 100 * 1024 * 1024:
        return False, f"File too large: {len(file_bytes)} bytes (max 100MB)"

    encoded_data = base64.b64encode(file_bytes).decode()

    payload = {
        "message": f"Audio upload - {filename}",
        "content": encoded_data,
        "branch": "main"
    }
    
    try:
        res = requests.put(url, headers=headers, json=payload, timeout=60)
        if res.status_code in [200, 201]:
            return True, "OK"
        elif res.status_code == 404:
            return False, "404: audio/ folder not found. On GitHub, create file audio/.gitkeep first."
        elif res.status_code == 401:
            return False, "401: Unauthorized - token missing repo scope"
        else:
            return False, f"HTTP {res.status_code}: {res.text[:200]}"
    except Exception as e:
        return False, f"Exception: {str(e)}"

def fetch_audio_from_github(filename):
    headers = get_github_headers()
    if not headers:
        return b""

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{AUDIO_FOLDER}/{filename}"

    try:
        response = requests.get(url, headers=headers, timeout=60)
        if response.status_code == 200:
            return base64.b64decode(response.json()['content'])
    except Exception:
        pass
    return b""

def delete_audio_from_github(filename):
    headers = get_github_headers()
    if not headers:
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{AUDIO_FOLDER}/{filename}"

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
        "message": f"Delete audio - {filename}",
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
                        df = fetch_data_from_github()
                        
                        try:
                            next_id = int(pd.to_numeric(df["id"]).max() + 1) if not df.empty and "id" in df.columns else 1
                        except:
                            next_id = len(df) + 1
                        
                        # Upload audio separately if provided
                        audio_filename = ""
                        audio_base64 = ""
                        if audio is not None:
                            safe_name = str(f_name).replace(' ', '_').replace('/', '_')[:30]
                            ext = audio.name.split(".")[-1] if "." in audio.name else "mp3"
                            audio_filename = f"ID_{next_id}_{safe_name}.{ext}"
                            audio_bytes = audio.getvalue()
                            
                            st.info(f"📤 Uploading audio: {audio_filename} ({len(audio_bytes):,} bytes)...")
                            success, msg = upload_audio_to_github(audio_filename, audio_bytes)
                            
                            if success:
                                st.success(f"✅ Audio uploaded to cloud: {audio_filename}")
                            else:
                                st.error(f"❌ Audio upload failed: {msg}")
                                st.info("💾 Falling back to storing audio in CSV (file will be large).")
                                audio_base64 = base64.b64encode(audio_bytes).decode()
                                audio_filename = ""
                        
                        new_entry = pd.DataFrame([{
                            "id": next_id,
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "user-name": st.session_state["editor"],
                            "Farmer Name": f_name,
                            "Woreda Zone": woreda,
                            "Kebele Locality": kebele,
                            "Phone Link Contact": phone,
                            "Audio Filename": audio_filename,
                            "Audio Base64": audio_base64
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
        if not df.empty:
            if len(df) > 0 and not (len(df) == 1 and df.iloc[0].isna().all()):
                has_records = True

        if has_records:
            # ================================================================
            # ANALYTICS DASHBOARD
            # ================================================================
            st.subheader("📈 Survey Analytics Overview")
            
            total_records = len(df)
            audio_separate = 0
            audio_fallback = 0
            if "Audio Filename" in df.columns:
                audio_separate = df["Audio Filename"].apply(lambda x: pd.notna(x) and str(x).strip() != "").sum()
            if "Audio Base64" in df.columns:
                audio_fallback = df["Audio Base64"].apply(lambda x: pd.notna(x) and str(x).strip() != "").sum()
            
            # Metrics cards
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📋 Total Records", total_records)
            m2.metric("🎤 Audio in Folder", audio_separate)
            m3.metric("💾 Audio in CSV", audio_fallback)
            m4.metric("👥 Active Agents", df["user-name"].nunique() if "user-name" in df.columns else 0)
            
            st.divider()
            
            # Per-user breakdown
            st.subheader("👤 Agent Performance Breakdown")
            if "user-name" in df.columns:
                user_stats = df.groupby("user-name").agg(
                    Records=("id", "count"),
                    Audio_Folder=("Audio Filename", lambda x: x.apply(lambda v: pd.notna(v) and str(v).strip() != "").sum()),
                    Audio_CSV=("Audio Base64", lambda x: x.apply(lambda v: pd.notna(v) and str(v).strip() != "").sum())
                ).reset_index()
                user_stats.columns = ["Agent Name", "Records Entered", "Audio in Folder", "Audio in CSV"]
                user_stats = user_stats.sort_values("Records Entered", ascending=False)
                st.dataframe(user_stats, use_container_width=True, hide_index=True)
                
                # Simple bar chart
                st.bar_chart(user_stats.set_index("Agent Name")["Records Entered"])
            
            st.divider()
            
            st.subheader("📥 Cloud Data Packages Extraction Modules")
            c1, c2, c3 = st.columns(3)
            
            display_df = df.drop(columns=["Audio Base64"], errors="ignore")
            c1.download_button("📥 Extract Metrics Sheet (CSV)", display_df.to_csv(index=False).encode('utf-8-sig'), "Amhara_ME_Data_2026.csv", use_container_width=True)
            
            with st.spinner("Packing audio files from cloud folder..."):
                z_buf = BytesIO()
                with zipfile.ZipFile(z_buf, "w") as zf:
                    audio_found = 0
                    audio_missing = 0
                    for idx, row in df.iterrows():
                        audio_fn = str(row.get('Audio Filename', '')).strip()
                        if audio_fn and audio_fn != "":
                            audio_bytes = fetch_audio_from_github(audio_fn)
                            if audio_bytes and len(audio_bytes) > 0:
                                zf.writestr(audio_fn, audio_bytes)
                                audio_found += 1
                            else:
                                audio_missing += 1
                    
                    if audio_missing > 0:
                        st.warning(f"⚠️ {audio_missing} audio file(s) missing from folder. Only {audio_found} included.")
                    elif audio_found == 0 and audio_missing == 0:
                        st.info("ℹ️ No audio files in cloud folder.")
                    else:
                        st.success(f"✅ {audio_found} audio file(s) from folder packed in ZIP.")
            c2.download_button("🎤 Extract from Folder (ZIP)", z_buf.getvalue(), "Amhara_ME_Audios_Folder.zip", use_container_width=True)
            
            with st.spinner("Packing audio from CSV fallback..."):
                z_buf2 = BytesIO()
                with zipfile.ZipFile(z_buf2, "w") as zf:
                    csv_audio_found = 0
                    for idx, row in df.iterrows():
                        b64_data = str(row.get('Audio Base64', '')).strip()
                        if b64_data and b64_data != "":
                            try:
                                audio_bytes = base64.b64decode(b64_data)
                                fn = str(row.get('Audio Filename', f'audio_{idx}.mp3')).strip()
                                if not fn or fn == "":
                                    fn = f"audio_{idx}.mp3"
                                zf.writestr(fn, audio_bytes)
                                csv_audio_found += 1
                            except Exception:
                                pass
                    
                    if csv_audio_found > 0:
                        st.success(f"✅ {csv_audio_found} audio file(s) from CSV packed in ZIP.")
                    else:
                        st.info("ℹ️ No audio stored in CSV fallback.")
            c3.download_button("💾 Extract from CSV (ZIP)", z_buf2.getvalue(), "Amhara_ME_Audios_CSV.zip", use_container_width=True)

            st.divider()

            st.subheader("🗑️ Cleanse Datasets Control System")
            st.warning("Critical Warning: Confirming this option completely clears your CSV text database file from GitHub.")
            if st.button("PERMANENTLY FLUSH CLOUD REPOSITORY RECORDS", type="primary", use_container_width=True):
                # Delete all audio files first
                with st.spinner("Deleting audio files..."):
                    for idx, row in df.iterrows():
                        audio_fn = str(row.get('Audio Filename', '')).strip()
                        if audio_fn and audio_fn != "":
                            delete_audio_from_github(audio_fn)
                empty_df = pd.DataFrame(columns=EXPECTED_COLS)
                if save_data_to_github(empty_df):
                    st.success("Cloud spreadsheets successfully wiped from repository layout.")
                    st.rerun()
        else:
            st.info("No surveyor records are currently stored inside your remote GitHub cloud database file.")
