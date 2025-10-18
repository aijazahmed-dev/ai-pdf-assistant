import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import requests
import os


if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.error("You must log in to access the Dashboard.")
    st.stop()  # Prevents the rest of the page from running

load_dotenv()

API_URL = os.getenv("BACKEND_URL", "http://backend:8000")
headers = {"Authorization": f"Bearer {st.session_state['token']}"}

st.title("Dashboard")

st.subheader("📤 Upload PDF")
upload_file = st.file_uploader("Upload your PDF", type=["pdf"])
if upload_file:
    files = {"file": (upload_file.name, upload_file, "application/pdf")}
    response = requests.post(f"{API_URL}/api/v1/upload", files=files, headers=headers)
    if response.status_code in (200, 201):
        st.success("File uploaded successfully")
    else:
        st.error("Failed to upload file")

st.subheader("🔍 Query Your Documents")
user_query = st.text_area("Enter your question")
if st.button("Ask"):
    response = requests.get(f"{API_URL}/api/v1/query", params={"query": user_query}, headers=headers)
    if response.status_code == 200:
        data = response.json()
        answer = data.get("LLM_response", "No response from model.")
        st.success("✅ Answer:")
        st.write(answer)  # shows the LLM response text
    else:
        st.error(f"❌ Failed: {response.text}")


st.subheader("✏️ Update PDF Data") 
st.write("It will append PDF date to existing PDF's data")
upload_file = st.file_uploader("Upload your PDF.", type=["pdf"])
if upload_file:
    files = {"file": (upload_file.name, upload_file, "application/pdf")}
    response = requests.put(f"{API_URL}/api/v1/update", files=files, headers=headers)
    if response.status_code == 200:
        st.success("Data appended successfully")
    else:
        st.error("Failed to append data")

# Initialize session state flags
if "confirm_delete_pdf" not in st.session_state:
    st.session_state.confirm_delete_pdf = False
if "confirm_delete_account" not in st.session_state:
    st.session_state.confirm_delete_account = False

# ---------------- PDF Deletion ----------------
st.subheader("🗑️ Delete PDF Data")

# Initialize session state variable if not set
if "confirm_delete_pdf" not in st.session_state:
    st.session_state.confirm_delete_pdf = False

# Step 1: Ask for confirmation
if st.button("Delete All PDF Data"):
    st.session_state.confirm_delete_pdf = True

# Step 2: Show warning only if user clicked delete
if st.session_state.confirm_delete_pdf:
    st.warning("Are you sure? This action cannot be undone.")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Yes, Delete Data"):
            response = requests.delete(f"{API_URL}/api/v1/delete_data", headers=headers)
            if response.status_code in (200, 201):
                st.success("Data deleted successfully")
                # st.session_state.confirm_delete_pdf = False  # reset state
            else:
                st.error("Data not found.")
            

    with col2:
        if st.button("❌ Cancel"):
            st.info("Deletion canceled")
            st.session_state.confirm_delete_pdf = False  # reset state

# ---------------- Account Deletion ----------------
st.subheader("🗑️ Delete Account")
password = st.text_input("Enter your password to confirm", type="password")

if st.button("Delete Account"):
    st.session_state.confirm_delete_account = True

if st.session_state.confirm_delete_account:
    st.warning("Are you sure you want to delete your account? This cannot be undone.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, Delete Account"):
            response = requests.delete(
                f"{API_URL}/api/v1/delete_account",
                json={"password": password},
                headers=headers,
            )
            if response.status_code in (200, 201):
                st.success("Account deleted successfully")
            else:
                st.error("Failed to delete account.")
            st.session_state.confirm_delete_account = False
    with col2:
        if st.button("❌ Cancel Deletion"):
            st.info("Deletion canceled")
            st.session_state.confirm_delete_account = False


st.subheader("👥 List All Registered Users")
if st.button("Show users"):
    response = requests.get(f"{API_URL}/api/v1/get_users", headers=headers)
    if response.status_code == 200:
        data = response.json()
        st.dataframe(pd.DataFrame(data["uuids"], columns=["User UUIDs"]))
        st.metric("Total Users", data["total_users"])
        st.success(f"Loaded {data['total_users']} users.")

    elif response.status_code == 403:
        st.warning("You are not authorized. Admin access only")

    else:
        st.error("Failed to load users.")


st.subheader("📜 Upload History")
if st.button("Show History"):
    response = requests.get(f"{API_URL}/api/v1/uploads_history", headers=headers)
    if response.status_code in (200, 201):
        data = response.json()
        df = pd.DataFrame([data])  # wrap in list to make it tabular
        st.table(df)

        st.success("Upload history loaded successfully.")
        
    else: 
        st.warning("No upload history found for this user.")




