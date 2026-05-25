from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from models import NoteCreate, NoteResponse, NoteUpdate, UserLogin, UserRegister, UserResponse, TokenResponse
from typing import List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId  # BSON is the binary JSON format MongoDB uses internally
from auth import get_password_hash, verify_password, create_access_token, get_current_user
import os

from ai import generate_text_embedding

app = FastAPI(title="Smart Notes App")

# ==========================================
# 🌐 CORS MIDDLEWARE SECURITY CONFIGURATION
# ==========================================
# Allows your independent Streamlit frontend (port 8501) to communicate with your FastAPI backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development; narrow this down in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],  # Allows the Authorization header to pass through cleanly
)


# Database Initialization
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)

# MongoDB handles lazy creation; these are built automatically on the first write
db = client.notes_db
notes_collection = db.notes
users_collection = db.users 


# ==========================================
# 🛠️ DATA CONFIGURATION HELPERS
# ==========================================

def format_note(note) -> dict:
    """
    Converts MongoDB's internal BSON ObjectId fields into standard 
    strings to ensure smooth serialization into Pydantic models.
    """
    note["_id"] = str(note["_id"])
    return note


def format_user(user) -> dict:
    """
    Maps MongoDB's binary unique document keys into standard string
    identifiers while keeping credentials secure.
    """
    user["_id"] = str(user["_id"])
    return user


# ==========================================
# 🔐 USER AUTHENTICATION ENDPOINTS
# ==========================================

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister):
    """
    Registers a new unique user profile. Evaluates uniqueness of the 
    requested username, hashes the raw password string via Bcrypt, and 
    creates a document inside the users collection.
    """
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
    """
    Authenticates user credentials. Validates username existence and 
    compares hashed credentials. Generates and returns a stateless, 
    cryptographically signed JWT access token on success.
    """
    user = await users_collection.find_one({"username": login_data.username})

    # Fixed: Returns identical errors for both user and password failure
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid username or password"
        )
    
    if not verify_password(login_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid username or password"
        )
    
    #Generate our stateless JWT passport packing the user's ID inside
    token_payload = {"user_id": str(user["_id"]), "username": user["username"]}
    access_token = create_access_token(data=token_payload)

    return {"access_token": access_token, "token_type": "bearer"}


# ==========================================
# 📋 CORE NOTES MANAGEMENT ENDPOINTS
# ==========================================

@app.get("/notes", response_model=List[NoteResponse], response_model_by_alias=False)
async def get_notes(q: str = None, current_user : dict = Depends(get_current_user)):
    """
    Fetches collections of notes. If query string 'q' is active, performs 
    an asynchronous, case-insensitive keyword regex search over note 
    titles and contents. Returns all documents if no query is supplied.
    """
    notes = []

    query_filter = {"user_id" : current_user["user_id"]}
    if q:
        query_filter = {
            "$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"content": {"$regex": q, "$options": "i"}}
            ]
        }
        cursor = notes_collection.find(query_filter)
    else:
        cursor = notes_collection.find(query_filter)
        
    async for document in cursor:
        notes.append(format_note(document))
    return notes


@app.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED, response_model_by_alias=False)
async def create_note(note_data: NoteCreate, current_user : dict = Depends(get_current_user)):
    """
    Persists a fresh note instance into MongoDB, automatically calling 
    the local Ollama AI container via OpenAI-style routing to inject math embeddings.
    """
    new_note_dict = note_data.model_dump()
    new_note_dict["user_id"] = current_user["user_id"]

    # 🌟 OPTIMAL CONTEXT PACKING: Combine title and body so concepts tie together perfectly
    combined_text_context = f"Title: {note_data.title}\nContent: {note_data.content}"
    note_vector = await generate_text_embedding(combined_text_context)
    new_note_dict["embedding"] = note_vector

    result = await notes_collection.insert_one(new_note_dict)
    
    inserted_note = await notes_collection.find_one({"_id": result.inserted_id})
    return format_note(inserted_note)


@app.get("/notes/{note_id}", response_model=NoteResponse, response_model_by_alias=False)
async def get_note_by_id(note_id: str, current_user : dict = Depends(get_current_user)):
    """
    Retrieves details of a specific note file by its unique identifier. 
    Includes a BSON format guard check to prevent underlying connection 
    exceptions if faulty formats are supplied by clients.
    """
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")
        
    note = await notes_collection.find_one({"_id": ObjectId(note_id), "user_id" : current_user["user_id"]})
    if note:
        return format_note(note)

    raise HTTPException(status_code=404, detail=f"Note with ID: {note_id} doesn't exist or unauthorized access")


@app.put("/notes/{note_id}", response_model=NoteResponse, response_model_by_alias=False)
async def update_note(note_id: str, update_data: NoteUpdate, current_user : dict = Depends(get_current_user)):
    """
    Modifies existing records by executing a targeted partial update. 
    Strips omitted/null fields from the payload payload, applying updates 
    strictly to the populated fields via MongoDB's native $set operator.
    """
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")

    clean_update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

    if not clean_update_dict:
        raise HTTPException(status_code=400, detail="No Valid Update Fields Provided")
    
    result = await notes_collection.update_one(
        {"_id": ObjectId(note_id), "user_id" : current_user["user_id"]},
        {"$set": clean_update_dict}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")

    updated_note = await notes_collection.find_one({"_id": ObjectId(note_id)})
    return format_note(updated_note)   
    

@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: str, current_user : dict = Depends(get_current_user)):
    """
    Permanently drops a selected note document from the collection 
    matching the validated target identifier. Returns an explicit 
    204 No Content success flag upon execution.
    """
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")
        
    result = await notes_collection.delete_one({"_id": ObjectId(note_id),"user_id" : current_user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
        
    return None