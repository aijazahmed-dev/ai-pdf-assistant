from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from passlib.hash import bcrypt
import uuid as uuid_pkg
from pydantic import BaseModel, EmailStr, StringConstraints
from typing import Annotated
import os
import logging
from auth import require_login, sign_jwt
from database import get_connection
from pdf_processor import extract_text_from_pdf
from llm_client import get_llm_response


# Import FastAPI router for creating grouped endpoints
router = APIRouter()

# Pydantic model for user registration input validation
class UserRegistration(BaseModel):
    user_name: str
    email: EmailStr
    password: str

# Identifier type: a string with automatic whitespace stripping,
# and length constraints (minimum 3, maximum 50 characters).
# This will be used for fields like username or email in login.
Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=50)
]

# Pydantic model for login input validation
class LoginInput(BaseModel):
    identifier: Identifier # username or email
    password: str

class DeleteAccountInput(BaseModel):
    password: str

# Define temporary directory for uploads
UPLOAD_DIR = "/temp/cag_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Endpoint to register a new user with a UUID
@router.post("/register_user/{uuid}")
def register_user(uuid: uuid_pkg.UUID, user: UserRegistration):
    """
    Register a new user with a UUID.

    Validates the username, checks for duplicate UUIDs or emails, 
    hashes the password, and stores the user in the database.

    Args:
        uuid (UUID): Unique user identifier.
        user (UserRegistration): Username, email, and password.

    Returns:
        dict: Success message with user details and registration date.

    Raises:
        HTTPException: If validation fails or the UUID/email already exists.
    """

    from datetime import datetime
    registration_date = datetime.utcnow().strftime("%d-%m-%y")

    uuid_str = str(uuid)

    # Validate username
    if not user.user_name:
        logging.warning("Registration failed: Username is empty")
        raise HTTPException(
            status_code=400, detail="User name cannot be empty!"
        )

    max_user_length = 15
    if len(user.user_name) > max_user_length:
        logging.warning(f"Registration failed: Username '{user.user_name}' is too long.")
        raise HTTPException(
            status_code=400, detail="User name is too long!"
        )
    
    # Log start of registration attempt
    logging.info(f"Registration attempt for UUID: {uuid_str}, username: {user.user_name}")
    

    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, email FROM users WHERE user_id = %s OR email = %s", (uuid_str, user.email))
        row = cursor.fetchone()
        if row:
            db_user_id, db_email = row["user_id"], row["email"]
            if db_user_id == uuid_str: 
                logging.warning(f"Registration failed: UUID '{uuid_str}' is already registered.")
                raise HTTPException(
                    status_code=400, detail=f"UUID '{uuid_str}' is already registered!"
                )
            elif db_email == user.email:
                logging.warning(f"Registration failed: Email '{user.email}' already exists.")
                raise HTTPException(
                    status_code=400, detail=f"Email '{user.email}' is already exist!"
                )

        # Hash the password
        password_bytes = user.password.encode("utf-8")[:72]
        hashed_password = bcrypt.hash(password_bytes.decode("utf-8"))
    
        # Save user data in the database
        cursor.execute("INSERT INTO users (user_id, user_name, email, password, registration_date) VALUES (%s, %s, %s, %s, %s)",
                    (uuid_str, user.user_name, user.email, hashed_password, registration_date)   
            )
        conn.commit()

        # Log success
        logging.info(f"User registered successfully: UUID={uuid_str}, username={user.user_name}")
        
        return {
            "message": "User registered successfully!",
            "uuid": uuid_str,
            "user_name": user.user_name,
            "email": user.email,
            "Registration_date": registration_date
        }

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Endpoint to authenticate a user for login and start a session
@router.post("/login")
def user_login(login_data: LoginInput):
    """
    Authenticate a user and return an access token.

    Verifies the username/email and password against the database. 
    On success, returns a JWT for session management.

    Args:
        login_data (LoginInput): Username/email and password.

    Returns:
        dict: Success message with JWT access token.

    Raises:
        HTTPException: If credentials are invalid.
    """

    logging.info(f"Login attempt for user: {login_data.identifier}")  # Log attempt

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, user_name, email, password FROM users WHERE user_name = %s OR email = %s",
            (login_data.identifier, login_data.identifier))

        row = cursor.fetchone()
        if not row:
            logging.warning(f"Login failed: User not found ({login_data.identifier})")
            raise HTTPException(status_code=401, detail="Invalid credentials.")
        
        db_user_id = row["user_id"]
        db_password = row["password"]


        if not bcrypt.verify(login_data.password, db_password):
            logging.warning(f"Login failed: Wrong password for {login_data.identifier}")
            raise HTTPException(status_code=401, detail="Invalid credentials.")
        
        token = sign_jwt(db_user_id)
        return {
            "message": "Login successful",
            "access_token": token,
            "token_type": "bearer"
        }

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Endpoint to upload a PDF file for a specific user identified by UUID
@router.post("/upload", status_code=201)
def upload_pdf(
    file: UploadFile = File(...),
    current_user: str = Depends(require_login)
):
    """
    Upload a PDF file for the logged-in user.

    Validates the file type and size, extracts text from the PDF, 
    saves the data in the database, and deletes the temporary file.

    Args:
        file (UploadFile): PDF file to upload.
        current_user (str): Authenticated user ID.

    Returns:
        dict: Success message with user ID, file name, and upload date.

    Raises:
        HTTPException:
            - 400: If file type or size is invalid.
            - 404: If the user ID does not exist.
            - 500: If PDF processing fails.
    """
    from datetime import datetime
    upload_date = datetime.utcnow().strftime("%d-%m-%y")
    
    file_name = file.filename
    user_id = current_user

    logging.info(f"Upload attempt: user={user_id}, file={file_name}")
    
    # Validate file type is PDF
    if file.content_type != "application/pdf":
        logging.warning(f"Upload failed: Not a PDF (user={user_id}, file={file_name})")
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are accepted")

    # Validate file size (limit: 5 MB)
    max_size = 20 * 1024 * 1024
    contents = file.file.read()
    file_size = len(contents)

    if file_size > max_size:
        logging.warning(f"Upload failed: File too large ({file_size} bytes) UUID: {user_id}")
        raise HTTPException(
            status_code=400, detail="The file is too large. Max size allowed is 20 MB"
        )
    file.file.seek(0) # Reset pointer after reading

    # Create the full file path by combining the upload folder, user's UUID, and the original file name
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")

    conn = None
    cursor = None
    try:
        # Save uploaded file to disk temporarily
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())
        
        # Extract text using the utility function
        extracted_text = extract_text_from_pdf(file_path)

        if extracted_text is None:
            logging.error(f"Text extraction failed (user={user_id}, file={file_name})")
            raise HTTPException(
                status_code=500, detail="Failed to extract text from PDF"
            )
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            logging.warning(f"Upload failed: User not found (user={user_id})")
            raise HTTPException(status_code=404, detail="User ID not found")
        
        cursor.execute(
            "INSERT INTO pdfs (user_id, file_name, upload_date, pdf_text, last_updated) VALUES (%s, %s, %s, %s, %s)",
            (user_id, file_name, upload_date, extracted_text, upload_date))

        conn.commit()

        logging.info(f"Upload successful: user={user_id}, file={file_name}")

        return {
            "message": f"File uploaded and text extracted successfully",
            "uuid": user_id,
            "file_name": file_name,
            "upload_date": upload_date,
            "last_updated": upload_date
            
        }
    
    except Exception as e:
        logging.error(f"Upload error (user={user_id}, file={file_name}): {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error accurred during file processing: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        # Clean up: delete temporary file after processing
        if os.path.exists(file_path):
            os.remove(file_path)
    
# Endpoint to update existing PDF data for a specific UUID by appending text from a new PDF file
@router.put("/update")
def update_pdf_data(file: UploadFile = File(...), 
                    current_user: str = Depends(require_login)):
    """
    Update stored PDF data for the logged-in user.

    Extracts text from a newly uploaded PDF and appends it to the 
    existing stored text. Also updates the last modified date.

    Args:
        file (UploadFile): PDF file to append.
        current_user (str): Authenticated user ID.

    Returns:
        dict: Success message with user ID and update date.

    Raises:
        HTTPException:
            - 400: If file type or size is invalid.
            - 404: If the user is not found.
            - 500: If text extraction fails or another error occurs.
    """


    user_id = current_user
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, user_name FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            logging.warning(f"Update failed: User not found. UUID: {user_id}")
            raise HTTPException(status_code=404, detail="User not found.")
    
        db_user_name = row["user_name"]

    
        logging.info(f"User {db_user_name} is attempting to update data for UUID {user_id} with file '{file.filename}'")

        # Validate that the uploaded file is a PDF
        if file.content_type != "application/pdf":
            logging.warning(f"Update failed: Invalid file type '{file.content_type}' for file '{file.filename}' by user: {current_user}")
            raise HTTPException(
                status_code=400, detail="Invalid file type. Only PDF files are accepted!")
    
        # Validate file size
        max_size = 20 * 1024 * 1024
        contents = file.file.read()
        file_size = len(contents)
    
        if file_size > max_size:
            logging.warning(f"Update failed: File '{file.filename}' too large ({file_size} bytes). User: {current_user}")
            raise HTTPException(
            status_code=400, detail="The file is too large. Max size allowed is 20 MB")
        file.file.seek(0)
    
        # Define temporary path to save the uploaded file
        file_path = os.path.join(UPLOAD_DIR, f"{user_id}_update_{file.filename}")
    
        # Save the uploaded file temporarily
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())

        # Extract text from the new PDF file
        new_text = extract_text_from_pdf(file_path)

        # If no text was extracted from the uploaded PDF, log an error and raise an exception
        if new_text is None:
            logging.error(f"Text extraction failed for file '{file.filename}' by user: {db_user_name}")
            raise HTTPException(
                status_code=500, detail="Failed to extract text from PDF!")
        
        # Record current date as last updated date
        from datetime import datetime
        last_updated = datetime.utcnow().date()
        
        # Append new text to existing data
        cursor.execute(
            "UPDATE pdfs SET pdf_text = COALESCE(pdf_text, '') || %s, last_updated = %s WHERE user_id = %s AND file_name = %s",
            ("\n\n" + new_text, last_updated, user_id, file.filename))
        conn.commit()

        logging.info(f"PDF data updated successfully by {db_user_name} for UUID {user_id} on {last_updated}")

        return {
            "message": f"Data appended successfully by {db_user_name}",
            "uuid": str(user_id),
            "last_updated": str(last_updated)
            }

    except Exception as e:
        # Log the exception e
        logging.error(f"Error during file upload. UUID: {user_id} - {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"An error accurred during file processing: {str(e)}")
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        # Cleanup the temporarily file
        if os.path.exists(file_path):
            os.remove(file_path)

# Endpoint to query stored data for a specific UUID using a user-provided question.
@router.get("/query")
def query_data(query: str = Query(..., min_length=1), 
               current_user: str = Depends(require_login)
               ):
    """
    Query stored PDF data for the logged-in user.

    Retrieves the user's stored text, sends it along with the query 
    to the LLM service, and returns the model's response.

    Args:
        query (str): The user's question.
        current_user (str): Authenticated user ID.

    Returns:
        dict: User ID, username, query, and LLM response.

    Raises:
        HTTPException:
            - 404: If the user or PDF data is not found.
    """
    user_id = current_user
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, user_name FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            logging.warning(f"Query failed: UUID '{user_id}' not found.")
            raise HTTPException(
                status_code=404, detail=f"User not found!")
    
        db_user_name = row["user_name"]
        logging.info(f"User '{db_user_name}' is querying UUID '{user_id}' with question: '{query}'")
        
    
        # Get stored data for the UUID
        cursor.execute("SELECT pdf_text FROM pdfs WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row or not row["pdf_text"]:
            raise HTTPException(status_code=404, detail="No PDF data found for this user")
        
        stored_text = row["pdf_text"]

        # Send stored text and query to the LLM and get response
        llm_response = get_llm_response(context=stored_text, query=query)

        # Log successful query
        logging.info(
            f"Query success: User '{db_user_name}' got response for UUID '{user_id}'. "
            f"Query: '{query}' | Response length: {len(llm_response) if llm_response else 0} characters")

        return {"uuid": user_id, 
                "user": db_user_name, 
                "query": query, 
                "LLM_response": llm_response
            }
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Endpoint to delete stored PDF data 
@router.delete("/delete_data", status_code=201)
def delete_pdf_data(current_user: str = Depends(require_login)):
    """
    Delete all stored PDF data for the logged-in user.

    Removes all extracted PDF text entries linked to the user's UUID.

    Args:
        current_user (str): Authenticated user ID.

    Returns:
        dict: Success message confirming deletion.

    Raises:
        HTTPException:
            - 404: If the user is not found.
    """
    user_id = current_user
    conn = None
    cursor = None

    logging.info(f"UUID '{user_id}' is attempting to delete data.")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            logging.warning(f"Deletion failed: UUID '{user_id}' not found.")
            raise HTTPException(
                status_code=404, detail=f"User not found")

        cursor.execute("DELETE FROM pdfs WHERE user_id = %s", (user_id,))
        deleted_rows = cursor.rowcount

        if deleted_rows == 0:
            logging.info(f"No PDF data found for UUID '{user_id}'.")
            return {"message": f"No PDF data found for UUID '{user_id}'"}
        
        conn.commit()

        logging.info(f"Data for UUID '{user_id}' deleted successfully.")
        return {"message": f"Data for UUID '{user_id}' has been deleted!"}
        
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.delete("/delete_account", status_code=201)
def delete_account(password: DeleteAccountInput, current_user: str = Depends(require_login)):
    """
    Delete the account of the logged-in user after verifying the password.

    Args:
        body (DeleteAccountInput): User's current password for confirmation.
        current_user (str): Authenticated user ID.

    Returns:
        dict: Success message with the deleted user's UUID.

    Raises:
        HTTPException:
            - 401: If the password is incorrect.
            - 404: If the user is not found.
    """
    user_id = current_user
    conn = None
    cursor = None

    logging.info(f"UUID '{user_id}' is attempting to delete account.")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, password FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            logging.warning(f"Deletion failed: UUID '{user_id}' not found.")
            raise HTTPException(
                status_code=404, detail=f"User not found")
        
        db_password = row["password"]
        if not bcrypt.verify(password.password, db_password):
            logging.warning(f"Account deletion failed: Wrong password. UUID: '{user_id}'")
            raise HTTPException(status_code=401, detail="Wrong password.")
        
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()

        logging.info(f"User account for UUID '{user_id}' has been deleted successfully.")
        return {"message": f"Your account has been deleted!",
                "uuid": user_id
                }
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Endpoint to list all registered user UUIDs along with total user count.
@router.get("/get_users")
def get_all_users(current_user: str = Depends(require_login)):
    """
    List all registered user UUIDs (admin only).

    Verifies the requesting user is an admin and returns all UUIDs 
    along with the total number of registered users.

    Args:
        current_user (str): Authenticated user ID.

    Returns:
        dict: UUID list and total user count.

    Raises:
        HTTPException:
            - 403: If the user is not an admin.
            - 404: If the user is not found.
    """

    user_id = current_user
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            logging.warning(f"Deletion failed: UUID '{user_id}' not found.")
            raise HTTPException(
                status_code=404, detail=f"User not found")
        
        if user_id != "92994189-e6ae-43f8-8df9-00247522e3c6":
            raise HTTPException(status_code=403, detail="Admins only")
        
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        if not rows:
            logging.warning("UUIDs not found")
            return {"uuids": [], "total_users": 0}

        uuids = [row["user_id"] for row in rows]

        total_users = len(uuids)
        logging.info(f"Listing all UUIDs. Total users: {total_users}")

        # Return list of UUIDs and total count
        return {"uuids": uuids, "total_users": total_users}
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Endpoint to fetch the upload history (excluding text content) for a specific user UUID.
@router.get("/uploads_history")
def get_uploads_history(current_user: str = Depends(require_login)):
    """
    Fetch upload history for the logged-in user.

    Returns metadata for uploaded files (name and timestamps), 
    excluding extracted PDF text content.

    Args:
        current_user (str): Authenticated user ID.

    Returns:
        dict: File name, upload date, and last updated timestamp.

    Raises:
        HTTPException:
            - 404: If the user is not found.
            - 500: If data retrieval fails.
    """
    user_id = current_user
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            logging.warning(f"Upload history fetch failed: UUID {user_id} not found")
            raise HTTPException(
                status_code=404, detail=f"UUID not found")
        
        cursor.execute("SELECT user_id, file_name, upload_date, last_updated FROM pdfs")
        row = cursor.fetchone()
        if not row:
            logging.warning(f"Upload history not found: UUID {user_id}")
            raise HTTPException(
                status_code=404, detail="History not found"
            )

        db_file_name, upload_date, last_updated = row["file_name"], row["upload_date"], row["last_updated"]
    
        logging.info(f"Upload history for UUID '{user_id}' fetched successfully.")
        return {
            "file_name": db_file_name,
            "upload_date": upload_date,
            "last_updated": last_updated
        }
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    








