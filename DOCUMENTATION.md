# NoteBook AI — Technical Documentation

A comprehensive deep-dive into the architecture, design decisions, technology choices, tradeoffs, and concepts used in this project.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Technology Choices & Rationale](#technology-choices--rationale)
4. [Core Concepts Explained](#core-concepts-explained)
5. [RAG Pipeline Deep-Dive](#rag-pipeline-deep-dive)
6. [Authentication System](#authentication-system)
7. [Database Design](#database-design)
8. [Frontend Architecture](#frontend-architecture)
9. [Tradeoffs & Limitations](#tradeoffs--limitations)
10. [Real-World Applications](#real-world-applications)
11. [Potential Improvements](#potential-improvements)

---

## Project Overview

NoteBook AI is a personal knowledge management system that combines traditional note-taking with AI-powered retrieval. Users save notes, and the system automatically generates vector embeddings for each note. When users ask questions, the app performs semantic search to find relevant notes, feeds them as context to a local LLM, and returns an answer grounded in the user's own data.

This is a complete implementation of the **RAG (Retrieval-Augmented Generation)** pattern running entirely on local hardware with no external API dependencies.

---

## System Architecture

### High-Level Flow

```
User → Streamlit UI → HTTP → FastAPI Backend → MongoDB (storage)
                                     ↓
                              Ollama (local AI)
                              ├── nomic-embed-text (embeddings)
                              └── qwen2.5:0.5b (chat generation)
```

### Request Lifecycle (RAG Chat)

```
1. User types question
2. Frontend sends POST /ai/chat with { question, session_id }
3. Backend generates query embedding vector (768 dimensions)
4. Backend loads all user's notes from MongoDB
5. Cosine similarity computed between query vector and each note's vector
6. Top-scoring notes above threshold are selected
7. Selected notes injected into system prompt as context
8. LLM generates answer using notes as grounding context
9. Response returned with answer + source attribution
10. Chat interaction saved to MongoDB for history
```

---

## Technology Choices & Rationale

### Backend: FastAPI

**Why FastAPI over alternatives:**

| Framework | Async Support | Auto-Docs | Type Safety | Performance |
|-----------|:---:|:---:|:---:|:---:|
| **FastAPI** | ✅ Native | ✅ Swagger/OpenAPI | ✅ Pydantic | ✅ Uvicorn/ASGI |
| Flask | ❌ Requires extensions | ❌ Manual | ❌ Manual | ⚠️ WSGI |
| Django | ⚠️ Partial (Django 4+) | ❌ DRF required | ⚠️ Serializers | ⚠️ Heavy |
| Express.js | ✅ Native | ❌ Manual | ❌ Without TS | ✅ Fast |

**Why FastAPI won:**
- **Native async/await** — Critical because our app calls Ollama's AI endpoints and MongoDB concurrently. Synchronous frameworks would block the entire server while waiting for LLM responses (which can take 5-30 seconds).
- **Pydantic models** — Request/response validation is automatic. We define `NoteCreate`, `ChatRequest`, etc. once, and FastAPI validates payloads, generates docs, and serializes responses.
- **Auto-generated OpenAPI docs** — Visit `/docs` for instant Swagger UI. No extra setup.
- **Dependency injection** — The `get_current_user` dependency elegantly handles auth on every protected route without boilerplate.

**Tradeoff:** FastAPI is single-process by default. For production, you'd need Gunicorn with multiple Uvicorn workers or container orchestration.

---

### Database: MongoDB

**Why MongoDB over SQL databases:**

| Requirement | MongoDB | PostgreSQL | SQLite |
|-------------|:---:|:---:|:---:|
| Flexible schema (notes with variable tags) | ✅ Native | ⚠️ JSON column | ⚠️ Limited |
| Store 768-float embedding arrays | ✅ Native arrays | ⚠️ Requires pgvector | ❌ No |
| Async Python driver | ✅ Motor | ✅ asyncpg | ❌ No |
| No migrations needed | ✅ Schemaless | ❌ Requires Alembic | ❌ Requires migrations |
| Multi-tenant isolation | ✅ Query filter | ✅ Row-level | ✅ Row-level |

**Why MongoDB won:**
- **Document model fits notes perfectly** — A note has a title, content, tags (array), and an embedding (768-float array). In MongoDB, this is one document. In SQL, you'd need a notes table + a tags junction table + a separate vector storage mechanism.
- **Motor async driver** — Pairs perfectly with FastAPI's async design. Every database call is non-blocking.
- **No schema migrations** — Adding the `embedding` field or `user_id` field later required zero migration files. Just start writing documents with the new fields.
- **Native array storage** — Embedding vectors (768 floats) store directly in the document. No extensions or plugins needed.

**Tradeoff:** MongoDB doesn't have built-in vector search indexes (Atlas has it, but not the free local version). We compute cosine similarity in-memory using NumPy, which works fine for personal use (<10,000 notes) but won't scale to millions.

**Alternative considered:** PostgreSQL + pgvector would give us proper vector indexing (HNSW/IVFFlat) for scalable similarity search. We chose MongoDB for simplicity and schema flexibility in a prototype.

---

### AI/LLM: Ollama (Local)

**Why Ollama over cloud APIs:**

| Factor | Ollama (Local) | OpenAI API | Hugging Face Inference |
|--------|:---:|:---:|:---:|
| Cost | ✅ Free | ❌ Pay per token | ⚠️ Free tier limited |
| Privacy | ✅ Data never leaves machine | ❌ Sent to cloud | ❌ Sent to cloud |
| Latency | ⚠️ Depends on hardware | ✅ Fast (cloud GPUs) | ⚠️ Variable |
| Internet required | ✅ No (after model download) | ❌ Yes | ❌ Yes |
| Model quality | ⚠️ Smaller models | ✅ GPT-4 level | ✅ Large models |

**Why Ollama won:**
- **Privacy** — Notes are personal. Users shouldn't need to send private thoughts to OpenAI's servers.
- **Zero cost** — No API keys, no billing, no rate limits.
- **OpenAI-compatible API** — Ollama exposes `/v1/chat/completions` and `/v1/embeddings` endpoints. We use the official `openai` Python SDK pointed at localhost. If you later want to switch to OpenAI/Azure, change one URL.
- **Offline capability** — Works without internet after initial model download.

**Tradeoff:** Local models (`qwen2.5:0.5b`) are dramatically less capable than GPT-4 or Claude. The 0.5B parameter model sometimes generates awkward responses. For production, you'd upgrade to `llama3:8b` or `mistral:7b` (require ~8GB RAM) or use a cloud API.

---

### Embedding Model: nomic-embed-text

**Why nomic-embed-text:**
- **768-dimensional vectors** — Good balance between quality and storage size
- **Optimized for retrieval** — Trained specifically for search/RAG tasks
- **Runs locally via Ollama** — Same infrastructure as the chat model
- **Strong performance** — Competitive with OpenAI's ada-002 on MTEB benchmarks

**Alternatives considered:**
- `all-MiniLM-L6-v2` (384-dim) — Smaller but lower quality
- OpenAI `text-embedding-3-small` — Better quality but requires API key + cost
- `mxbai-embed-large` — Larger model, better quality, slower inference

---

### Chat Model: qwen2.5:0.5b

**Why this specific model:**
- **Tiny footprint** — Runs on any machine with 1GB+ free RAM
- **Fast inference** — Generates responses in 2-5 seconds on CPU
- **Instruction-following** — Reasonably follows system prompts for its size
- **Good enough for RAG** — When you provide context (notes), even small models can extract and summarize effectively

**Tradeoff:** This is the weakest point of the stack. A 0.5B model frequently:
- Generates awkward phrasing
- Occasionally ignores parts of the system prompt
- Struggles with complex multi-step reasoning

**Upgrade path:** `qwen2.5:3b` → `llama3:8b` → `mistral:7b` → cloud API (as hardware/budget allows).

---

### Frontend: Streamlit

**Why Streamlit over alternatives:**

| Framework | Learning Curve | Prototyping Speed | Customization | Production-Ready |
|-----------|:---:|:---:|:---:|:---:|
| **Streamlit** | ✅ Minimal | ✅ Very fast | ⚠️ Limited | ⚠️ OK |
| React + Next.js | ❌ High | ❌ Slow | ✅ Full control | ✅ Yes |
| Gradio | ✅ Minimal | ✅ Fast | ❌ Very limited | ❌ No |
| Flask + Jinja | ⚠️ Medium | ⚠️ Medium | ✅ Full control | ✅ Yes |

**Why Streamlit won:**
- **Python-only** — No JavaScript, no HTML templates, no CSS frameworks. The entire UI is ~300 lines of Python.
- **Built-in components** — `st.chat_message`, `st.chat_input`, `st.sidebar`, `st.form`, `st.dialog` give us a ChatGPT-like experience out of the box.
- **Session state** — `st.session_state` handles authentication tokens, chat history, and UI state without external state management libraries.
- **Instant iteration** — Hot-reloads on file save. No build step.

**Tradeoff:** Streamlit reruns the entire script on every interaction. This means:
- No fine-grained component updates (the whole page re-renders)
- State management requires explicit `st.session_state` tracking
- Limited layout control (no CSS Grid/Flexbox without hacks)
- Not ideal for apps with >1000 concurrent users

---

### Authentication: JWT + Bcrypt

**Why JWT (stateless tokens) over sessions:**

| Approach | Scalability | Storage | Stateless | Revocation |
|----------|:---:|:---:|:---:|:---:|
| **JWT** | ✅ No server state | Client-side | ✅ Yes | ❌ Hard |
| Server sessions | ⚠️ Requires shared store | Server-side (Redis) | ❌ No | ✅ Easy |
| OAuth2 (3rd party) | ✅ Delegated | Provider | ✅ Yes | ✅ Easy |

**Why JWT won:**
- **Stateless** — Backend doesn't store sessions. The token itself contains user_id and expiry. Any backend instance can verify it.
- **Simple** — No Redis, no session table, no cookies. Just a header: `Authorization: Bearer <token>`.
- **Pairs with FastAPI** — FastAPI's `HTTPBearer` security scheme + dependency injection makes JWT trivial to implement.

**Why Bcrypt for passwords:**
- Industry standard for password hashing
- Built-in salt (prevents rainbow table attacks)
- Configurable work factor (slows brute force)
- Battle-tested for 25+ years

---

## Core Concepts Explained

### Vector Embeddings

An embedding is a mathematical representation of text as a list of floating-point numbers (a vector). The key property: **semantically similar text produces similar vectors.**

```
"machine learning" → [0.12, -0.45, 0.78, ..., 0.33]  (768 numbers)
"deep learning AI" → [0.14, -0.43, 0.76, ..., 0.31]  (very similar vector!)
"chocolate cake"   → [-0.67, 0.22, -0.11, ..., 0.89]  (very different vector)
```

In this app, every note gets embedded when created. When you search or ask a question, your query is also embedded, and we find notes with the most similar vectors.

### Cosine Similarity

The metric used to compare two vectors. It measures the angle between them:
- **1.0** = identical direction (perfect match)
- **0.0** = perpendicular (unrelated)
- **-1.0** = opposite (contradictory)

Formula:
```
similarity = (A · B) / (||A|| × ||B||)
```

In practice, scores above **0.4** indicate strong relevance, **0.25-0.4** indicates partial relevance, and below **0.2** means unrelated.

### Retrieval-Augmented Generation (RAG)

RAG solves the fundamental LLM limitation: models only know what they were trained on. By retrieving relevant documents and injecting them into the prompt, the model can answer questions about private data it was never trained on.

```
Traditional LLM:
  User: "What did I learn in yesterday's meeting?"
  LLM: "I don't have access to your meetings."

RAG-Enhanced LLM:
  1. Search user's notes for "meeting" → finds meeting notes
  2. Inject notes into prompt: "Using these notes: [meeting notes]..."
  3. LLM: "Based on your notes, yesterday you discussed the new API design..."
```

### Multi-Tenant Data Isolation

Every database query includes `user_id` as a filter:
```python
notes_collection.find({"user_id": current_user["user_id"]})
```

This ensures User A can never see User B's notes or chat history, even though all data lives in the same MongoDB collections.

---

## RAG Pipeline Deep-Dive

### Dual-Threshold Source Attribution

The system uses two separate similarity thresholds:

```
CONTEXT_THRESHOLD = 0.25  →  "Include in LLM context" (lenient)
SOURCE_THRESHOLD  = 0.40  →  "Show as cited source" (strict)
```

**Why two thresholds?**
- A note scoring 0.30 might provide useful background context for the LLM but isn't directly "sourced"
- Only notes above 0.40 are confident enough to show the user as "this is where the answer came from"
- If no notes pass the source threshold, the response is labeled "General Knowledge"

### General Knowledge Detection

When the LLM answers from its training data rather than from notes, the system detects this and changes the source label:

```python
if "based on general knowledge" in ai_generation.lower() or not source_metadata_list:
    final_sources = [{"id": "external", "title": "General Knowledge", "tags": ["ai-generated"]}]
```

The system prompt instructs the model to prefix general knowledge answers with "Based on general knowledge:" — this acts as a signal for the backend to swap sources.

---

## Authentication System

### Flow

```
Register:
  1. User submits username + password
  2. Backend hashes password with Bcrypt
  3. Stores {username, hashed_password} in MongoDB

Login:
  1. User submits username + password
  2. Backend fetches user, verifies password against hash
  3. Creates JWT containing {user_id, username, exp}
  4. Returns token to frontend

Protected Routes:
  1. Frontend sends Authorization: Bearer <token>
  2. FastAPI's HTTPBearer extracts token
  3. get_current_user dependency decodes + validates JWT
  4. Extracts user_id from payload
  5. Passes user context to route handler
```

### Security Measures

- Passwords never stored in plaintext (Bcrypt hash)
- Tokens expire after 60 minutes
- Each request validates token signature with SECRET_KEY
- User isolation enforced at query level (not just API level)

---

## Database Design

### Collections

**users**
```json
{
  "_id": ObjectId,
  "username": "john",
  "password": "$2b$12$..."  // Bcrypt hash
}
```

**notes**
```json
{
  "_id": ObjectId,
  "user_id": "string",
  "title": "Meeting Notes",
  "content": "We discussed...",
  "tags": ["work", "api"],
  "embedding": [0.12, -0.45, ..., 0.33]  // 768 floats
}
```

**chats**
```json
{
  "_id": ObjectId,
  "user_id": "string",
  "session_id": "session_a1b2c3d4",
  "title": "What is RAG?...",
  "updated_at": ISODate,
  "interactions": [
    {
      "question": "What is RAG?",
      "answer": "Based on your notes...",
      "sources": [{"id": "...", "title": "...", "tags": [...]}],
      "timestamp": ISODate
    }
  ]
}
```

### Why This Schema?

- **Embedding stored with the note** — Avoids a separate vector store. Simple at small scale.
- **Chat interactions as a nested array** — One document per session with $push for new messages. Atomic updates, no joins needed.
- **session_id as UUID** — Not ObjectId because it's generated application-side before database insertion.

---

## Frontend Architecture

### State Management

Streamlit reruns the entire script on every interaction. To maintain state:

```python
st.session_state.token            # JWT (None if logged out)
st.session_state.username         # Display name
st.session_state.active_tab       # "notes" or "chat"
st.session_state.active_session_id       # Current chat thread
st.session_state.active_session_messages # Chat message history
```

### Navigation Pattern

Instead of Streamlit's native tabs (which cause sidebar CSS conflicts), the app uses a sidebar-driven navigation:

```python
if st.session_state.active_tab == "notes":
    render_notes_page()
else:
    render_chat_page()
```

The sidebar always shows:
- Navigation buttons (Notes / Chat)
- Chat session history with delete buttons
- Logout button

### Chat UX Pattern

```python
# 1. User submits message
# 2. Immediately append to session state + render
# 3. Show spinner while backend processes
# 4. Append AI response to session state
# 5. st.rerun() to re-render full conversation
```

---

## Tradeoffs & Limitations

| Decision | Benefit | Cost |
|----------|---------|------|
| Local LLM (0.5B) | Free, private, fast | Lower quality answers |
| In-memory vector search | Simple, no extra infra | Won't scale past ~10K notes |
| MongoDB (no pgvector) | Flexible schema, easy setup | No proper ANN indexing |
| Streamlit frontend | Fast to build, Python-only | Limited UX control, full reruns |
| JWT (no refresh tokens) | Simple auth flow | User must re-login after 60 min |
| Single-process backend | Simple deployment | Can't handle high concurrency |
| Embedding stored in note doc | Simple queries | Large documents, wasteful reads |

---

## Real-World Applications

### Personal Knowledge Management
- Students saving lecture notes and asking questions before exams
- Researchers organizing papers and querying across their reading

### Team Documentation
- Engineering teams storing runbooks and asking "how do I deploy X?"
- Onboarding new hires who can ask questions about company docs

### Meeting Intelligence
- Save meeting transcripts as notes
- Later ask "What did we decide about the pricing model?"

### Study Assistant
- Dump textbook chapters as notes
- Ask targeted questions: "Explain the difference between TCP and UDP based on my networking notes"

### Journaling + Reflection
- Daily journal entries as notes
- Ask "What were my main concerns this month?" for pattern recognition

---

## Potential Improvements

### Short-term
- Add a dedicated vector database (Qdrant, Weaviate, or pgvector)
- Upgrade to a larger model (llama3:8b or mistral:7b)
- Add refresh tokens for seamless re-authentication
- Implement note categories/folders
- Add file upload support (PDF, DOCX → auto-extract text)

### Medium-term
- Streaming responses (SSE) for real-time token generation
- Multi-user collaboration on shared note spaces
- Export chat conversations as PDFs
- Mobile-responsive frontend (React Native or PWA)

### Long-term
- Fine-tune a model on the user's writing style
- Auto-summarization of new notes
- Cross-reference detection between notes
- Graph-based knowledge visualization
- Voice input for note creation

---

## Running Tests

```bash
# Backend API tests (if you add pytest)
cd backend
pytest tests/ -v

# Manual API testing
# Visit http://127.0.0.1:8000/docs for Swagger UI
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m "Add my feature"`
4. Push to branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Ollama](https://ollama.com/)
- [RAG Paper (Lewis et al., 2020)](https://arxiv.org/abs/2005.11401)
- [nomic-embed-text](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
- [Motor (Async MongoDB)](https://motor.readthedocs.io/)
- [JWT RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519)
