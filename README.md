# 📝 NoteBook AI

A full-stack intelligent note-taking application with AI-powered question-answering using Retrieval-Augmented Generation (RAG). Save your notes and ask questions — the AI searches your personal knowledge base and answers using your own content.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-1.46+-red?logo=streamlit)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0+-darkgreen?logo=mongodb)
![Ollama](https://img.shields.io/badge/Ollama-Local_AI-purple)

---

## Features

- **Note Management** — Create, read, update, and delete notes with tags
- **AI-Powered Search** — Semantic search across notes using vector embeddings
- **RAG Chat** — Ask questions and get answers sourced from your notes
- **Smart Source Attribution** — Shows whether answers come from your notes or general knowledge
- **Chat Sessions** — Multi-session chat history with create/delete functionality
- **User Authentication** — JWT-based secure login and registration
- **Multi-Tenant** — Each user's notes and chats are fully isolated
- **100% Local AI** — All AI processing runs on your machine via Ollama (no API keys, no cloud)
- **Token Bucket Rate Limiting** — Custom, self-contained API rate limiter to protect local hardware compute channels against resource exhaustion attacks 🌟

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| Backend API | FastAPI + Uvicorn |
| Database | MongoDB (via Motor async driver) |
| AI/LLM | Ollama (qwen2.5:0.5b) |
| Embeddings | nomic-embed-text (768-dim vectors) |
| Auth | JWT + Bcrypt (passlib) |

---

## Architecture

```
┌─────────────────┐        ┌──────────────────┐        ┌─────────────────┐
│   Streamlit     │  HTTP  │    FastAPI        │  Async │    MongoDB      │
│   Frontend      │◄──────►│    Backend        │◄──────►│    Database     │
│   (Port 8501)   │        │    (Port 8000)    │        │    (Port 27017) │
└─────────────────┘        └────────┬─────────┘        └─────────────────┘
                                    │
                                    │ OpenAI-compatible API
                                    ▼
                           ┌──────────────────┐
                           │     Ollama       │
                           │  (Port 11434)    │
                           │  - qwen2.5:0.5b  │
                           │  - nomic-embed   │
                           └──────────────────┘
```

### System Design: Rate Limiting
To prevent heavy LLM generation requests from overwhelming the local host CPU, the system implements an in-memory **Token Bucket Algorithm**. 

- **Mechanism:** Tracks API request frequencies uniquely mapped against the user's authenticated session identifiers.
- **Capacity Rules:** Configured with a burst capacity of 3 requests and a strict token regeneration interval ($capacity=3, refill\_rate=0.066$).
- **Handling:** Excess request bursts exceeding the computational boundary are short-circuited instantly at the API gateway layer, returning a standard `HTTP 429 Too Many Requests` status code to protect application thread stability.

---

## Prerequisites

- **Python 3.10+**
- **MongoDB** — Running locally on port 27017
- **Ollama** — Installed and running locally

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/amanrai-warangal/NoteBook-AI.git
cd smart-notes-app
```

### 2. Install Python Dependencies

```bash
pip install fastapi uvicorn motor pydantic python-jose passlib[bcrypt] openai numpy streamlit requests
```

Or if you want the full environment:

```bash
pip install -r requirements.txt
```

### 3. Install & Start MongoDB

**Windows (using MongoDB Community):**
```bash
# Download from https://www.mongodb.com/try/download/community
# Start the service:
net start MongoDB
```

**macOS (Homebrew):**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

**Linux:**
```bash
sudo systemctl start mongod
```

Verify it's running:
```bash
mongosh --eval "db.runCommand({ping: 1})"
```

### 4. Install & Setup Ollama

**Download Ollama:** https://ollama.com/download

Pull the required models:
```bash
ollama pull qwen2.5:0.5b
ollama pull nomic-embed-text
```

Verify Ollama is running:
```bash
curl http://localhost:11434/api/tags
```

### 5. Run the Application

**Terminal 1 — Start the Backend:**
```bash
cd backend
uvicorn main:app --reload
```
Backend will be available at `http://127.0.0.1:8000`

**Terminal 2 — Start the Frontend:**
```bash
cd frontend
streamlit run app.py
```
Frontend will open at `http://localhost:8501`

---

## Project Structure

```
smart-notes-app/
├── backend/
│   ├── main.py          # FastAPI app, all API endpoints
│   ├── models.py        # Pydantic schemas (request/response validation)
│   ├── auth.py          # JWT token + Bcrypt password utilities
│   ├── limiter.py       # Custom in-memory Token Bucket rate limiter utility 🌟
│   └── ai.py            # Ollama client (embeddings + LLM generation)
├── frontend/
│   └── app.py           # Streamlit UI (notes, chat, auth)
├── requirements.txt     # Python dependencies
└── README.md
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create a new user account |
| POST | `/auth/login` | Login and receive JWT token |

### Notes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notes` | List all user notes (with optional keyword search) |
| POST | `/notes` | Create a new note |
| GET | `/notes/{id}` | Get a single note |
| PUT | `/notes/{id}` | Update a note |
| DELETE | `/notes/{id}` | Delete a note |
| GET | `/notes/semantic-search` | AI-powered semantic search |

### AI Chat
| Method | Endpoint | Description | Status Codes |
|--------|----------|-------------|--------------|
| POST | `/ai/chat` | Ask a question (RAG pipeline) | `200 OK`, `429 Too Many Requests` 🛑 |
| GET | `/ai/history` | List all chat sessions | `200 OK` |
| GET | `/ai/history/{session_id}` | Get full chat thread | `200 OK`, `404 Not Found` |
| DELETE | `/ai/history/{session_id}` | Delete a chat session | `200 OK` |

---

## Environment Variables (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `LLM_ENDPOINT` | `http://localhost:11434/v1` | Ollama API endpoint |
| `SECRET_KEY` | `DEVELOPMENT_SECRET_KEY_...` | JWT signing secret |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token expiry time |

---

## Usage

1. **Register** an account on the login page
2. **Create notes** — Add your study material, meeting notes, research, etc.
3. **Search** — Use keyword search or toggle AI semantic search for meaning-based results
4. **Ask questions** — Switch to AI Chat and ask questions about your notes
5. **Chat history** — Previous conversations are saved in the sidebar; click to resume, or delete them

---

## License

MIT
