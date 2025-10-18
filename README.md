# AI PDF Assistant - Chat with Your PDF

## Overview

The AI PDF Assistant Project is a FastAPI-powered backend application that enables users to register, log in, and upload PDF documents. Once uploaded, the text content of PDF is extracted and stored. Users can then interact with this content by asking natural language questions, which are answered by a Language Model (LLM) such as Google Gemini. The system maintains persistent data using a PostgreSQL database, and includes JWT-based session management, secure authentication, PDF file validation, and detailed logging. This makes it ideal for searching, querying, and analyzing document content in a conversational way.

---

## Features

1. **User Management**

   - Register with UUID, username, email, and password.
   - UUID-based identification.
   - JWT authentication login.

2. **Persistent User Storage**

   - User data is stored in the users table within a PostgreSQL database for long-term persistence.
   - PDF upload metadata and extracted content are stored in the pdfs table, ensuring reliable data management.

3. **Secure Login System**

   - Passwords hashed with `passlib`'s bcrypt.
   - Only authenticated users can access core functionalities.

4. **File Upload & Processing**

   - Upload PDF files.
   - Extracts and stores content using `pypdf`.
   - Validates file type and size.

5. **Querying with LLM (Google Gemini)**

   - Ask questions based on your uploaded PDF content.
   - Get contextual responses via the Gemini LLM.

6. **Upload History & Management**

   - View upload metadata history (excluding text).
   - Update/append new content to PDF files.
   - Allows a logged-in user to delete all PDF data linked to their account (UUID).

7. **Logging**

   - Logs user actions like login, logout, uploads, and errors to `app.log`.

---

## Project Structure

```
project folder/                  # Root project folder
├── backend/                     # FastAPI backend application
│   ├── main.py                  # FastAPI app entry point
│   ├── auth.py                  # JWT authentication and dependencies
│   ├── data_handler.py          # Core API endpoints for user and PDF operations
│   ├── database.py              # PostgreSQL database connection and models
│   ├── llm_client.py            # Google Gemini LLM integration
│   ├── pdf_processor.py         # Extracts and processes PDF text
│   ├── requirements.txt         # Backend dependencies
│
├── frontend/                    # Streamlit frontend application
│   ├── app.py                   # Main Streamlit entry point
│   ├── pages/                   # Multi-page Streamlit UI
│   │   ├── dashboard.py         # User dashboard to manage and query PDFs
│   │   ├── login.py             # User login page
│   │   ├── logout.py            # User logout page
│   │   └── register.py          # User registration page
│   ├── requirements.txt         # Frontend dependencies
│
├── db/                          # Database initialization folder
│   └── init.sql                 # Initializes database schema on first run
│
├── logs/                        # Logs folder
│   └── app.log                  # Log file for user actions and errors
│
├── .gitignore                   # Ignore unecessary files 
├── docker-compose.dev.yml       # Docker Compose file for local development
├── docker-compose.prod.yml      # Docker Compose file for production (uses prebuilt images)
├── Dockerfile.backend           # Dockerfile for FastAPI backend
├── Dockerfile.frontend          # Dockerfile for Streamlit frontend
├── .dockerignore                # Ignore unnecessary files for Docker builds
├── .env                         # Environment variables (secret keys, DB configs, API keys)
├── README.md                    # Project documentation

```
*Note:*
The backend is powered by FastAPI with PostgreSQL for reliable data storage, while the frontend uses Streamlit with multi-page support for an interactive and user-friendly interface.

---

## How to Run

*This project includes Docker support for easy setup and deployment.*

1. **Clone the repository**
   ```
   git clone https://github.com/aijazahmed-dev/ai-pdf-assistant.git
   cd project-folder
   ```
2. **Set up environment variables**
   *Create a .env file in the root folder with the following variables (adjust values as needed):*

   *Application Secrets And Database Configuration*
   ```env
   SECRET_KEY=your_secret_key
   GEMINI_API_KEY=your_google_gemini_api_key
   ALGORITHM=HS256

   POSTGRES_USER=your_db_user
   POSTGRES_PASSWORD=your_db_password
   POSTGRES_DB=your_db_name
   POSTGRES_HOST=db
   POSTGRES_PORT=5432
   DATABASE_URL=postgresql://your_db_user:your_db_password@db:5432/your_db_name
   ```

   ⚠️*Note:* The .env file is not included in GitHub for security reasons. Each developer must create their own. And give variable names exactly as I have mentioned above


3. **Run with Docker Compose**
   *Development (local, with code changes visible inside containers)*
   - docker compose -f docker-compose.dev.yml up -d --build

   *Production (using prebuilt images from Docker Hub)*
   - docker compose -f docker-compose.prod.yml up -d

   This will start three services:
      - FastAPI backend → http://localhost:8000
      - Streamlit frontend → http://localhost:8501
      - PostgreSQL database (with initial schema from db/init.sql)


4. **Access the application**\
   - Swagger API Docs → http://localhost:8000/docs
   - Streamlit Frontend → http://localhost:8501


5. **Stopping the application**

   To stop all services:
   - docker compose -f docker-compose.dev.yml down
   - docker compose -f docker-compose.prod.yml down

   ```

---

## API Endpoints Summary

| Method | Endpoint                         | Description                       |
| ------ | -------------------------------- | --------------------------------- |
| POST   | `/api/v1/register_user/{uuid}`   | Register a new user               |
| POST   | `/api/v1/login`                  | Log in a registered user          |
| POST   | `/api/v1/upload`                 | Upload a single PDF               |
| PUT    | `/api/v1/update`                 | Append text from another PDF      |
| GET    | `/api/v1/query`                  | Query extracted content using LLM |
| DELETE | `/api/v1/delete_data`            | Delete user and file data         |
| DELETE | `/api/v1/delete_account`         | Delete user account               |
| GET    | `/api/v1/get_users`              | List all registered UUIDs         |
| GET    | `/api/v1/uploads_history`        | Get upload metadata history       |

---

## Dependencies

**Backend**

- fastapi
- python-multipart
- uvicorn
- pydantic
- python-dotenv
- passlib[bcrypt]
- pypdf
- google-genai
- itsdangerous
- email-validator
- psycopg2
- python-jose[cryptography]

**Frontend**
- streamlit
- requests

---

## Notes

- PDF files must be under **20MB**.
- Only `.pdf` files are accepted.
- File and username validations are enforced.
- Data is stored in a PostgreSQL database for reliability and scalability

---

## License

This project is for educational purposes.

---

## Author

**Aijaz Ahmed**\
Python Developer | AI Enthusiast 
