from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from models import NoteCreate, NoteResponse, NoteUpdate, UserLogin, UserRegister, UserResponse, TokenResponse
from typing import List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId  # BSON is the binary JSON format MongoDB uses internally
from auth import get_password_hash, verify_password, create_access_token, get_current_user
import os
import numpy as np
from ai import generate_text_embedding

app = FastAPI(title="Smart Notes App")

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

    # 🌟 NEW: Enforce a strict semantic relevance threshold (0.35 is the sweet spot for nomic-embed)
    SIMILARITY_THRESHOLD = 0.35
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