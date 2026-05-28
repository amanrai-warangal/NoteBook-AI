from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from models import NoteCreate, NoteResponse, NoteUpdate, UserLogin, UserRegister, UserResponse, TokenResponse, ChatRequest, ChatResponse
from typing import List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId  # BSON is the binary JSON format MongoDB uses internally
from auth import get_password_hash, verify_password, create_access_token, get_current_user
import os
import numpy as np
from ai import generate_text_embedding, generate_llm_response
from datetime import datetime
import uuid #random hash for chat session

app = FastAPI(title="NoteBook AI")

# ==========================================
# 🌐 CORS MIDDLEWARE SECURITY CONFIGURATION
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# Database Initialization
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)

db = client.notes_db
notes_collection = db.notes
users_collection = db.users 
chats_collection = db.chats


# ==========================================
# 🛠️ DATA CONFIGURATION HELPERS
# ==========================================

def format_note(note) -> dict:
    """Converts MongoDB's internal BSON ObjectId fields into standard strings."""
    note["_id"] = str(note["_id"])
    return note


def format_user(user) -> dict:
    """Maps MongoDB's binary unique document keys into standard string identifiers."""
    user["_id"] = str(user["_id"])
    return user


# ==========================================
# 🔐 USER AUTHENTICATION ENDPOINTS
# ==========================================

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister):
    """Registers a new unique user profile securely using Bcrypt hashing."""
    existing_user = await users_collection.find_one({"username": user_data.username})

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Username is already registered"
        )
    
    hashed_password = get_password_hash(user_data.password)

    new_user_dict = {
        "username": user_data.username,
        "password": hashed_password
    }

    result = await users_collection.insert_one(new_user_dict)
    return {"message": "User Created Successfully", "user_id": str(result.inserted_id)}


@app.post("/auth/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin):
    """Authenticates credentials and issues signed JWT access tokens."""
    user = await users_collection.find_one({"username": login_data.username})

    if not user or not verify_password(login_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid username or password"
        )
    
    token_payload = {"user_id": str(user["_id"]), "username": user["username"]}
    access_token = create_access_token(data=token_payload)

    return {"access_token": access_token, "token_type": "bearer"}


# ==========================================
# 📋 CORE NOTES MANAGEMENT ENDPOINTS
# ==========================================

@app.get("/notes/semantic-search", response_model=List[NoteResponse], response_model_by_alias=False)
async def semantic_search_notes(q: str, limit: int = 5, current_user: dict = Depends(get_current_user)):
    """Performs an in-memory mathematical vector search over the user's isolated note pool."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query string cannot be empty")

    query_vector = await generate_text_embedding(q)
    if not query_vector:
        raise HTTPException(status_code=500, detail="Failed to generate embedding vector for query")

    cursor = notes_collection.find({"user_id": current_user["user_id"]})
    user_notes = []
    async for doc in cursor:
        user_notes.append(format_note(doc))
    
    scored_notes = []
    A = np.array(query_vector)
    for note in user_notes:
        if "embedding" not in note or not note["embedding"]:
            continue
        
        B = np.array(note["embedding"])
        dot_product = np.dot(A, B)
        norm_A = np.linalg.norm(A)
        norm_B = np.linalg.norm(B)
        
        if norm_A == 0 or norm_B == 0:
            similarity = 0.0
        else:
            similarity = float(dot_product / (norm_A * norm_B))
        
        note["score"] = similarity
        scored_notes.append(note)

    scored_notes.sort(key=lambda x: x["score"], reverse=True)

    # Use a lower threshold to avoid filtering out partially relevant notes
    SIMILARITY_THRESHOLD = 0.2
    relevant_notes = [note for note in scored_notes if note["score"] >= SIMILARITY_THRESHOLD]

    top_matches = relevant_notes[:limit]
    
    for match in top_matches:
        match.pop("score", None)
    
    return top_matches


@app.get("/notes", response_model=List[NoteResponse], response_model_by_alias=False)
async def get_notes(q: str = None, current_user: dict = Depends(get_current_user)):
    """Fetches user notes natively, fallback to case-insensitive keyword regex matching."""
    query_filter = {"user_id": current_user["user_id"]}
    
    if q:
        query_filter["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"content": {"$regex": q, "$options": "i"}}
        ]
        
    notes = []
    cursor = notes_collection.find(query_filter)
    async for document in cursor:
        notes.append(format_note(document))
    return notes


@app.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED, response_model_by_alias=False)
async def create_note(note_data: NoteCreate, current_user: dict = Depends(get_current_user)):
    """Persists a new note and generates an automated semantic embedding vector."""
    new_note_dict = note_data.model_dump()
    new_note_dict["user_id"] = current_user["user_id"]

    combined_text_context = f"Title: {note_data.title}\nContent: {note_data.content}"
    note_vector = await generate_text_embedding(combined_text_context)
    new_note_dict["embedding"] = note_vector

    result = await notes_collection.insert_one(new_note_dict)
    inserted_note = await notes_collection.find_one({"_id": result.inserted_id})
    return format_note(inserted_note)


@app.get("/notes/{note_id}", response_model=NoteResponse, response_model_by_alias=False)
async def get_note_by_id(note_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieves a single note verifying strict ownership parameters."""
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")
        
    note = await notes_collection.find_one({"_id": ObjectId(note_id), "user_id": current_user["user_id"]})
    if note:
        return format_note(note)

    raise HTTPException(status_code=404, detail="Note doesn't exist or unauthorized access")


@app.put("/notes/{note_id}", response_model=NoteResponse, response_model_by_alias=False)
async def update_note(note_id: str, update_data: NoteUpdate, current_user: dict = Depends(get_current_user)):
    """Modifies an existing record and automatically recalculates sync embeddings on text changes."""
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")

    clean_update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not clean_update_dict:
        raise HTTPException(status_code=400, detail="No Valid Update Fields Provided")

    # 🔒 Fetch the existing note first to verify ownership and check text mutations
    existing_note = await notes_collection.find_one({"_id": ObjectId(note_id), "user_id": current_user["user_id"]})
    if not existing_note:
        raise HTTPException(status_code=404, detail="Note not found")

    # 🧠 AI RE-INDEXING GUARD: If title or content changed, recalculate the vector math
    if "title" in clean_update_dict or "content" in clean_update_dict:
        new_title = clean_update_dict.get("title", existing_note["title"])
        new_content = clean_update_dict.get("content", existing_note["content"])
        
        combined_text_context = f"Title: {new_title}\nContent: {new_content}"
        updated_vector = await generate_text_embedding(combined_text_context)
        clean_update_dict["embedding"] = updated_vector

    # Execute the localized update
    await notes_collection.update_one(
        {"_id": ObjectId(note_id), "user_id": current_user["user_id"]},
        {"$set": clean_update_dict}
    )

    # SECURED: Fetch verification strictly matching user token context
    updated_note = await notes_collection.find_one({"_id": ObjectId(note_id), "user_id": current_user["user_id"]})
    return format_note(updated_note)   
    

@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: str, current_user: dict = Depends(get_current_user)):
    """Permanently drops a selected note document matching multi-tenant ownership keys."""
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")
        
    result = await notes_collection.delete_one({"_id": ObjectId(note_id), "user_id": current_user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
        
    return None

@app.post("/ai/chat", response_model=ChatResponse)
async def rag_chat_agent(payload: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Orchestrates the full Retrieval-Augmented Generation (RAG) loop.
    Performs its own scoring to determine whether notes are truly relevant,
    and only attributes sources when they actually contributed to the answer.
    """
    user_query = payload.question
    if not user_query.strip():
        raise HTTPException(status_code=400, detail="Question cannot be left empty")

    # 1. RETRIEVE: Generate query embedding and score against all user notes
    query_vector = await generate_text_embedding(user_query)
    
    context_accumulator = []
    source_metadata_list = []
    
    if query_vector:
        cursor = notes_collection.find({"user_id": current_user["user_id"]})
        user_notes = []
        async for doc in cursor:
            user_notes.append(format_note(doc))
        
        # Score all notes
        A = np.array(query_vector)
        scored_notes = []
        for note in user_notes:
            if not note.get("embedding"):
                continue
            B = np.array(note["embedding"])
            norm_A = np.linalg.norm(A)
            norm_B = np.linalg.norm(B)
            if norm_A == 0 or norm_B == 0:
                continue
            similarity = float(np.dot(A, B) / (norm_A * norm_B))
            scored_notes.append((similarity, note))
        
        scored_notes.sort(key=lambda x: x[0], reverse=True)
        
        # Only include notes with strong relevance as actual sources
        SOURCE_THRESHOLD = 0.4
        CONTEXT_THRESHOLD = 0.25
        
        for score, note in scored_notes[:5]:
            if score >= CONTEXT_THRESHOLD:
                context_accumulator.append(f"Title: {note['title']}\nContent: {note['content']}")
            if score >= SOURCE_THRESHOLD:
                source_metadata_list.append({
                    "id": note["_id"],
                    "title": note["title"],
                    "tags": note.get("tags", [])
                })

    has_relevant_notes = len(context_accumulator) > 0
    extracted_context = "\n\n".join(context_accumulator) if context_accumulator else ""

    # 2. CONSTRUCT SYSTEM PROMPT based on whether notes are relevant
    if has_relevant_notes:
        SYSTEM_PROMPT = (
            "You are a helpful assistant. Answer the user's question using the personal notes below.\n"
            "Rules:\n"
            "- If the notes are relevant, answer using them.\n"
            "- If the notes are NOT relevant, answer from your general knowledge and begin with: 'Based on general knowledge:'\n"
            "- Never apologize or say you cannot answer. Always provide a direct answer.\n"
            "- Do not mention notes, limitations, or add any disclaimers.\n\n"
            f"NOTES:\n{extracted_context}"
        )
    else:
        SYSTEM_PROMPT = (
            "You are a helpful assistant. Answer the user's question directly from your general knowledge.\n"
            "Begin your response with: 'Based on general knowledge:'\n"
            "Never apologize or say you cannot answer. Just answer directly."
        )

    # 3. GENERATE
    ai_generation = await generate_llm_response(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_query
    )

    # 4. If the AI used general knowledge, don't show notes as sources
    if "based on general knowledge" in ai_generation.lower() or not source_metadata_list:
        final_sources = [{"id": "external", "title": "General Knowledge", "tags": ["ai-generated"]}]
    else:
        final_sources = source_metadata_list

    # 5. SESSION ROUTING
    session_id = payload.session_id or f"session_{uuid.uuid4().hex[:8]}"
    derived_title = user_query[:20] + "..." if len(user_query) > 20 else user_query

    new_interaction = {
        "question": user_query,
        "answer": ai_generation,
        "sources": final_sources,
        "timestamp": datetime.utcnow()
    }

    await chats_collection.update_one(
        {"user_id": current_user["user_id"], "session_id": session_id},
        {
            "$push": {"interactions": new_interaction},
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {"title": derived_title}
        },
        upsert=True
    )

    return {
        "answer": ai_generation,
        "session_id": session_id,
        "sources": final_sources
    }

@app.get("/ai/history")
async def get_all_sessions(current_user : dict = Depends(get_current_user)):
    """
    Returns a light index list of all active session metadata cards 
    for the user's sidebar panel view.
    """
    sessions = []
    # Sort threads so the most recently active conversational thread shows up at the top
    cursor = chats_collection.find(
        {"user_id": current_user["user_id"]}, 
        {"session_id": 1, "title": 1, "updated_at": 1}
    ).sort("updated_at", -1)

    async for doc in cursor:
        sessions.append({
            "session_id": doc["session_id"],
            "title": doc.get("title", "Active Chat Session")
        })
    return sessions

@app.get("/ai/history/{session_id}")
async def get_single_session_thread(session_id: str, current_user: dict = Depends(get_current_user)):
    """
    Hydrates the full historical array of interaction blocks 
    for the specific active thread selected in the sidebar panel.
    """
    session_doc = await chats_collection.find_one({"user_id": current_user["user_id"], "session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Conversation session thread not found")
    
    return session_doc.get("interactions", [])


@app.delete("/ai/history/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Deletes a specific chat session for the current user."""
    result = await chats_collection.delete_one(
        {"user_id": current_user["user_id"], "session_id": session_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return None
