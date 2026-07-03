import streamlit as st
import pandas as pd
import base64
import zipfile
import datetime
import io
import requests
from io import BytesIO

# --- GITHUB CONFIGURATION ---
GITHUB_OWNER = "your-github-username"       # 👈 Update this
GITHUB_REPO = "your-repo-name"             # 👈 Update this
CSV_FILENAME = "amhara_me_2026.csv"          # 👈 Your flat-file database

# --- HELPERS FOR GITHUB API ---
def get_github_headers():
    """Retrieves token from .streamlit/secrets.toml securely"""
    token = st.secrets.get("github", {}).get("token")
    if not token:
        st.error("❌ GitHub token missing in Secrets configuration!")
        return None
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def fetch_data_from_github() -> pd.DataFrame:
    """Downloads the current CSV database file from your repository"""
    headers = get_github_headers()
    if not headers: return pd.DataFrame()
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        content = base64.b64decode(response.json()['content']).decode('utf-8')
        return pd.read_csv(io.StringIO(content))
    else:
        # If file doesn't exist yet, return an empty tracking DataFrame with your schema
        return pd.DataFrame(columns=["id", "timestamp", "name", "woreda", "kebele", "phone", "audio_data", "registered_by"])

def save_data_to_github(updated_df: pd.DataFrame) -> bool:
    """Overwrites or creates the CSV tracking file in your repository"""
    headers = get_github_headers()
    if not headers: return False
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{CSV_FILENAME}"
    
    # Check if file exists to fetch its tracking SHA hash (required by GitHub to modify files)
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
        
    res = requests.put(url, headers=headers, json=payload)
    return res.status_code in [200, 201]

def to_b64(file):
    if file: return base64.b64encode(file.getvalue()).decode()
    return ""

# --- SESSION STATE & NAVIGATION ---
if "page" not in st.session_state: st.session_state["page"] = "Home"
if "auth" not in st.session_state: st.session_state["auth"] = False
if "editor" not in st.session_state: st.session_state["editor"] = None

def nav(p):
    st.session_state["page"] = p
    st.rerun()

# --- PAGE: HOME ---
if st.session_state["page"] == "Home":
    st.title("🌾 Amhara M&E Survey 2026 (GitHub Cloud DB)")
    if st.session_state["editor"]:
        st.success(f"👤 Active Editor: **{st.session_state['editor']}**")
    
    st.divider()
    col1, col2 = st.columns(2)
    if col1.button("📝 NEW REGISTRATION", use_container_width=True, type="primary"): nav("Reg")
    if col2.button("📊 ADMIN DASHBOARD", use_container_width=True): nav("Data")

# --- PAGE: REGISTRATION ---
elif st.session_state["page"] == "Reg":
    st.button("⬅️ Home", on_click=lambda: nav("Home"))
    
    if not st.session_state["editor"]:
        with st.container(border=True):
            st.subheader("Login Once")
            name_in = st.text_input("Registered By (Your Name):")
            if st.button("Start"):
                if name_in.strip():
                    st.session_state["editor"] = name_in.strip()
                    st.rerun()
    else:
        with st.form("reg_form", clear_on_submit=True):
            st.info(f"M&E Logging as: {st.session_state['editor']}")
            f_name = st.text_input("Farmer Name")
            woreda = st.text_input("Woreda")
            kebele = st.text_input("Kebele")
            phone = st.text_input("Phone Number")
            audio = st.file_uploader("🎤 Audio Recording", type=['mp3','wav','m4a'])
            
            if st.form_submit_button("Save Registration"):
                if f_name and woreda and kebele:
                    # 1. Pull existing database sheet down from GitHub
                    df = fetch_data_from_github()
                    
                    # 2. Calculate dynamic structural ID row sequence
                    next_id = int(df["id"].max() + 1) if not df.empty else 1
                    
                    # 3. Build new entry record row
                    new_entry = pd.DataFrame([{
                        "id": next_id,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "name": f_name,
                        "woreda": woreda,
                        "kebele": kebele,
                        "phone": phone,
                        "audio_data": to_b64(audio),
                        "registered_by": st.session_state["editor"]
                    }])
                    
                    # 4. Concatenate and sync back to GitHub repo cloud database
                    updated_df = pd.concat([df, new_entry], ignore_index=True)
                    if save_data_to_github(updated_df):
                        st.success(f"✅ Saved safely to GitHub Cloud for {f_name}!")
                    else:
                        st.error("❌ Cloud transaction failed. Verify repository access permissions.")
                else:
                    st.error("Name, Woreda, and Kebele are required.")

# --- PAGE: ADMIN (Passcode: oaf2026) ---
elif st.session_state["page"] == "Data":
    st.button("⬅️ Home", on_click=lambda: nav("Home"))
    
    if not st.session_state["auth"]:
        st.header("🔒 Admin Access")
        pass_input = st.text_input("Enter Passcode", type="password")
        if st.button("Unlock Dashboard"):
            if pass_input == "oaf2026": 
                st.session_state["auth"] = True
                st.rerun()
            else:
                st.error("Incorrect Passcode")
    else:
        df = fetch_data_from_github()
        
        col_t, col_l = st.columns([8, 2])
        col_t.header("📊 Admin Management")
        if col_l.button("🔒 Lock Dashboard"):
            st.session_state["auth"] = False
            st.rerun()

        if not df.empty:
            st.subheader("📥 Data Export")
            c1, c2 = st.columns(2)
            
            # Export basic rows table (excluding memory-heavy base64 audio columns)
            display_df = df.drop(columns=["audio_data"]) if "audio_data" in df.columns else df
            c1.download_button("📥 Excel Download", display_df.to_csv(index=False).encode('utf-8-sig'), "Amhara_ME_Data_2026.csv", use_container_width=True)
            
            # Reconstruct Audio ZIP archive binaries straight out of text vectors
            z_buf = BytesIO()
            with zipfile.ZipFile(z_buf, "w") as zf:
                for _, row in df.iterrows():
                    if pd.notna(row['audio_data']) and row['audio_data'] != "": 
                        zf.writestr(f"ID_{row['id']}_{row['name']}.mp3", base64.b64decode(row['audio_data']))
            c2.download_button("🎤 Audio ZIP", z_buf.getvalue(), "Amhara_ME_Audios.zip", use_container_width=True)

            st.divider()

            st.subheader("🗑️ Database Control")
            st.error("Warning: This action will permanently wipe your GitHub database sheet clean.")
            if st.button("DELETE ALL RECORDS FROM DATABASE", type="primary", use_container_width=True):
                empty_df = pd.DataFrame(columns=df.columns)
                if save_data_to_github(empty_df):
                    st.success("All remote database records cleared successfully.")
                    st.rerun()
        else:
            st.info("No records located inside your GitHub database repository file.")
