import streamlit as st
import pandas as pd
import base64
import zipfile
import datetime
import io
import re
import requests
from io import BytesIO

# ============================================================================
# GITHUB ENVIRONMENT CONFIGURATION
# ============================================================================
GITHUB_OWNER = "Derese4803"
GITHUB_REPO = "control-sample-collction"
CSV_FILENAME = "amhara_me_2026.csv"

EXPECTED_COLS = ["id", "timestamp", "user-name", "Farmer Name", "Woreda Zone", "Kebele Locality", "Phone Link Contact", "Audio File"]

# ============================================================================
# CLOUD DATABASE STORAGE CORE LOGIC (GITHUB API)
# ============================================================================

def get_github_headers():
    token = st.secrets.get("github", {}).get("token")
    if not token:
        st.error("❌ GitHub token missing in .streamlit/secrets.toml!")
        return None
    
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

        if response.status_code == 200:
            raw_content = response.json().get('content', '')
            if not raw_content:
                return pd.DataFrame(columns=EXPECTED_COLS)
                
            clean_b64 = raw_content.replace("\n", "").replace("\r", "").strip()
            content = base64.b64decode(clean_b64).decode('utf-8', errors='ignore')

            if not content or not content.strip():
                return pd.DataFrame(columns=EXPECTED_COLS)

            try:
                df = pd.read_csv(io.StringIO(content))
                if df.empty:
                    return pd.DataFrame(columns=EXPECTED_COLS)
                    
                df.columns = [str(c).strip() for c in df.columns]
                
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
    if not headers or updated_df is None:
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"

    sha = None
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            sha = response.json().get('sha')
    except Exception:
        pass

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
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"Network error during CSV upload: {str(e)}")
        return False

def upload_file_to_github(filename: str, file_bytes: bytes) -> bool:
    """Uploads binary audio file to GitHub repo root with proper Base64 formatting."""
    headers = get_github_headers()
    if not headers:
        return False

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{filename}"

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
    """Robust binary download with Base64 cleaning and raw direct URL fallback."""
    headers = get_github_headers()
    if not headers:
        return b""

    filename = str(filename).strip()
    if not filename or filename.lower() in ["nan", "none"]:
        return b""

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{filename}"

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            json_data = response.json()
            if "content" in json_data and json_data.get("encoding") == "base64":
                clean_b64 = json_data["content"].replace("\n", "").replace("\r", "").replace(" ", "").strip()
                return base64.b64decode(clean_b64)
            elif "download_url" in json_data and json_data["download_url"]:
                raw_res = requests.get(json_data["download_url"], headers=headers, timeout=30)
                if raw_res.status_code == 200:
                    return raw_res.content
    except Exception:
        pass

    raw_fallback_url = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/{filename}"
    try:
        raw_res = requests.get(raw_fallback_url, headers=headers, timeout=30)
        if raw_res.status_code == 200:
            return raw_res.content
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
        st.success(f"👤 Active Enumerator: **{st.session_state['editor']}**")
    
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
            st.subheader("Enumerator Authentication")
            name_in = st.text_input("Registered By (Enumerator Full Name):")
            if st.button("Initialize Terminal Session"):
                if name_in.strip():
                    st.session_state['editor'] = name_in.strip()
                    st.rerun()
    else:
        with st.form("reg_form", clear_on_submit=True):
            st.info(f"Logging Metrics Data As Enumerator: {st.session_state['editor']}")
            f_name = st.text_input("Farmer Name")
            woreda = st.text_input("Woreda Zone")
            kebele = st.text_input("Kebele Locality")
            phone = st.text_input("Phone Link Contact")
            audio = st.file_uploader("🎤 Audio Recording Memo", type=['mp3','wav','m4a'])
            
            if st.form_submit_button("Save Registration Metadata"):
                if f_name and woreda and kebele:
                    with st.spinner("Processing transaction package to cloud..."):
                        df = fetch_data_from_github()
                        
                        if not df.empty and "id" in df.columns:
                            valid_ids = pd.to_numeric(df["id"], errors='coerce').dropna()
                            next_id = int(valid_ids.max() + 1) if not valid_ids.empty else 1
                        else:
                            next_id = 1
                        
                        audio_filename = ""
                        if audio is not None:
                            clean_farmer_name = re.sub(r'[^a-zA-Z0-9]', '', str(f_name))[:15]
                            if not clean_farmer_name:
                                clean_farmer_name = "farmer"
                            ext = audio.name.split(".")[-1] if "." in audio.name else "m4a"
                            audio_filename = f"audio_ID{next_id}_{clean_farmer_name}.{ext}"
                            audio_bytes = audio.getvalue()
                            
                            st.info(f"📤 Uploading {len(audio_bytes):,} bytes as `{audio_filename}`...")
                            upload_success = upload_file_to_github(audio_filename, audio_bytes)
                            
                            if upload_success:
                                st.success(f"✅ Audio file saved to GitHub: `{audio_filename}`")
                            else:
                                st.error("❌ Audio upload failed. Saving record without audio link.")
                                audio_filename = ""

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
                        updated_df = new_entry_df if df.empty else pd.concat([df, new_entry_df], ignore_index=True)
                        
                        if save_data_to_github(updated_df):
                            st.success(f"✅ Sync Successful! Record #{next_id} logged for {f_name}.")
                        else:
                            st.error("❌ CSV update rejected by GitHub API.")
                else:
                    st.error("Name, Woreda, and Kebele are mandatory.")

# ============================================================================
# INTERFACE: ADMINISTRATIVE COMPLIANCE & ANALYTICS PANELS
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
        col_t.header("📊 Admin Management & Analytics Panel")
        if col_l.button("🔒 Lock Portal"):
            st.session_state["auth"] = False
            st.rerun()

        if not df.empty and len(df) > 0:
            # ----------------------------------------------------------------
            # 1. TOP OVERVIEW METRICS
            # ----------------------------------------------------------------
            st.subheader("📈 Overall System Metrics")
            
            total_records = len(df)
            
            has_audio_mask = df["Audio File"].apply(
                lambda x: pd.notna(x) and str(x).strip() != "" and str(x).strip().lower() not in ["nan", "none"]
            )
            total_audio = has_audio_mask.sum()
            
            unique_enumerators = df["user-name"].nunique() if "user-name" in df.columns else 0
            audio_ratio = (total_audio / total_records * 100) if total_records > 0 else 0
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📋 Total Records", total_records)
            m2.metric("🎤 Total Audio Files", total_audio)
            m3.metric("👥 Active Enumerators", unique_enumerators)
            m4.metric("📊 Audio Coverage Rate", f"{audio_ratio:.1f}%")
            
            st.divider()

            # ----------------------------------------------------------------
            # 2. ENUMERATOR PERFORMANCE BREAKDOWN
            # ----------------------------------------------------------------
            st.subheader("👥 Enumerator Activity & Audio Breakdown")
            
            if "user-name" in df.columns:
                enum_summary = df.groupby("user-name").agg(
                    Total_Data=("id", "count"),
                    Total_Audio=("Audio File", lambda x: x.apply(
                        lambda v: pd.notna(v) and str(v).strip() != "" and str(v).strip().lower() not in ["nan", "none"]
                    ).sum())
                ).reset_index()
                
                enum_summary["Audio Coverage (%)"] = (enum_summary["Total_Audio"] / enum_summary["Total_Data"] * 100).round(1)
                enum_summary.columns = ["Enumerator Name", "Total Data Logged", "Total Audio Files", "Audio Coverage (%)"]
                enum_summary = enum_summary.sort_values("Total Data Logged", ascending=False)
                
                st.dataframe(enum_summary, use_container_width=True, hide_index=True)
                
                c_chart1, c_chart2 = st.columns(2)
                with c_chart1:
                    st.markdown("**📋 Data Logged Per Enumerator**")
                    st.bar_chart(enum_summary.set_index("Enumerator Name")["Total Data Logged"])
                with c_chart2:
                    st.markdown("**🎤 Audio Uploads Per Enumerator**")
                    st.bar_chart(enum_summary.set_index("Enumerator Name")["Total Audio Files"])

            st.divider()
            
            # ----------------------------------------------------------------
            # 3. RAW DATA GRID VIEW
            # ----------------------------------------------------------------
            st.subheader("📋 Complete Dataset Explorer")
            st.dataframe(df, use_container_width=True)
            
            st.divider()
            
            # ----------------------------------------------------------------
            # 4. EXPORT / DOWNLOAD MODULES
            # ----------------------------------------------------------------
            st.subheader("📥 Data Package Extraction")
            c1, c2 = st.columns(2)
            
            display_df = df.drop(columns=["Audio File"], errors="ignore")
            c1.download_button("📥 Extract CSV Sheet", display_df.to_csv(index=False).encode('utf-8-sig'), "Amhara_ME_Data_2026.csv", use_container_width=True)
            
            z_buf = BytesIO()
            audio_found = 0
            audio_missing = 0
            
            with st.spinner("Preparing Audio ZIP Package..."):
                with zipfile.ZipFile(z_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    if "Audio File" in df.columns:
                        for idx, row in df.iterrows():
                            audio_fn = str(row.get('Audio File', '')).strip()
                            if audio_fn and audio_fn.lower() not in ["nan", "none", ""]:
                                audio_bytes = fetch_file_from_github(audio_fn)
                                if audio_bytes and len(audio_bytes) > 0:
                                    zf.writestr(audio_fn, audio_bytes)
                                    audio_found += 1
                                else:
                                    audio_missing += 1

            if audio_found > 0:
                st.success(f"✅ {audio_found} audio file(s) successfully packed into ZIP!")
            if audio_missing > 0:
                st.warning(f"⚠️ {audio_missing} audio file(s) recorded in CSV were not found on GitHub.")

            c2.download_button(
                label=f"🎤 Extract Audio Recordings ZIP ({audio_found} Ready)", 
                data=z_buf.getvalue(), 
                file_name="Amhara_ME_Audios.zip", 
                mime="application/zip",
                use_container_width=True
            )

            st.divider()

            # ----------------------------------------------------------------
            # 5. DATASET FLUSH CONTROL
            # ----------------------------------------------------------------
            st.subheader("🗑️ Cleanse Datasets Control System")
            st.warning("Critical Warning: This clears ALL data from GitHub.")
            if st.button("PERMANENTLY FLUSH ALL RECORDS", type="primary", use_container_width=True):
                for idx, row in df.iterrows():
                    audio_fn = str(row.get('Audio File', '')).strip()
                    if audio_fn and audio_fn.lower() not in ["nan", "none", ""]:
                        delete_file_from_github(audio_fn)
                empty_df = pd.DataFrame(columns=EXPECTED_COLS)
                if save_data_to_github(empty_df):
                    st.success("All records wiped successfully.")
                    st.rerun()
        else:
            st.info("No enumerator records are currently stored inside your remote GitHub cloud database file.")
