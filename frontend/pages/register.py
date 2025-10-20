import streamlit as st
from dotenv import load_dotenv
import requests
import os

load_dotenv()
API_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.title("Register")
uuid = st.text_input("Enter UUID")
user_name = st.text_input("Enter Username")
email = st.text_input("Enter Email")
password = st.text_input("Enter Password", type="password")

if st.button("Register"):
    if not uuid or not user_name or not email or not password:
        st.warning("All fields are required!")
    else: 
        response = requests.post(f"{API_URL}/api/v1/register_user/{uuid}", json={"user_name": user_name, "email": email, "password": password})
        if response.status_code in (200, 201):
            st.success("User registered successfully. Go to login page")
        else:
            st.error("Registration failed")


    
