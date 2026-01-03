import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import time

load_dotenv() 

DATABASE_URL = os.getenv("URL")

def get_connection():
    retries = 10
    for i in range(retries):
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            print(f"Database not ready (attempt {i+1}/{retries}): {e}")
            time.sleep(2)
    raise RuntimeError("Could not connect to the database after several attempts.")
