import streamlit as st
from dotenv import load_dotenv
import requests
import os

st.title("Login")

load_dotenv()

API_URL = os.getenv("BACKEND_URL", "http://backend:8000")

user = st.text_input("Enter Username/Password")
password = st.text_input("Enter Password", type="password")

if st.button("Login"):
    if not user or not password:
        st.warning("All fields are required!")
    else:
        response = requests.post(f"{API_URL}/api/v1/login", json={"identifier": user, "password": password})
        if response.status_code in (200, 201):
            data = response.json()
            st.session_state["authenticated"] = True
            st.session_state["token"] = data["access_token"]
            st.success("Login successfull. Go to dashboard")
        else:
            st.error("Login failed. Invalid Email or Password")
    
        
