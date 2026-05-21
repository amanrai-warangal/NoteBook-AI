from fastapi import FastAPI, HTTPException, status
from models import NoteCreate, NoteResponse, NoteUpdate
from typing import List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId  # BSON is the binary JSON format MongoDB uses internally

app = FastAPI(title="Smart Notes App")

# Database Initialization
MONGODB_URL = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGODB_URL)

# MongoDB handles lazy creation; these are built automatically on the first write
db = client.notes_db
notes_collection = db.notes

# Helper function to bridge the gap between MongoDB dicts and Pydantic schemas
def format_note(note) -> dict:
    note["_id"] = str(note["_id"])  # Convert native ObjectId to standard string
    return note

@app.get("/")
def greet():
    return "Welcome to Smart Notes App"

# READ ALL NOTES
@app.get("/notes", response_model=List[NoteResponse], response_model_by_alias=False)
async def get_notes(q : str = None):
    notes = []
    if q:
        query_filter = {
            "$or" : [
                {"title" : {"$regex" : q, "$options" : "i"}},
                {"content" : {"$regex" : q, "$options" : "i"}}
            ]
        }

        cursor = notes_collection.find(query_filter)
    else:
        # find() returns an async cursor instead of loading all data into memory at once
        cursor = notes_collection.find()
    async for document in cursor:
        notes.append(format_note(document))
    return notes

# CREATE A NOTE
@app.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED, response_model_by_alias=False)
async def create_note(note_data: NoteCreate):
    # Strip incoming Pydantic schema validation into a raw Python dictionary
    new_note_dict = note_data.model_dump()

    # Await the async network call to persist data into the Docker container
    result = await notes_collection.insert_one(new_note_dict)

    # Use the database confirmation receipt (inserted_id) to fetch the fresh document
    inserted_note = await notes_collection.find_one({"_id": result.inserted_id})
    return format_note(inserted_note)

# READ SINGLE NOTE
@app.get("/notes/{note_id}", response_model=NoteResponse, response_model_by_alias=False)
async def get_note_by_id(note_id: str):
    # Guard clause: Prevents MongoDB driver from crashing if the string format is invalid
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")
        
    # Query database using the parsed BSON ObjectId type
    note = await notes_collection.find_one({"_id": ObjectId(note_id)})
    if note:
        return format_note(note)

    raise HTTPException(status_code=404, detail=f"Note with ID: {note_id} doesn't exist")

# Update note
@app.put("/notes/{note_id}", response_model=NoteResponse,response_model_by_alias=False)
async def update_note(note_id : str,update_data: NoteUpdate):
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")

    clean_update_dict = {k : v for k,v in update_data.model_dump().items() if v is not None}

    if not clean_update_dict:
        raise HTTPException(status_code=400, detail="No Valid Update Fields Provided")
    
    result = await notes_collection.update_one(
        {"_id" : ObjectId(note_id)},
        {"$set" : clean_update_dict}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")

    updated_note = await notes_collection.find_one({"_id" : ObjectId(note_id)})
    return format_note(updated_note)   
    

# Delete NOTE
@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: str):
    # Guard clause: Prevents MongoDB driver from crashing if the string format is invalid
    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")
        
    # Query database using the parsed BSON ObjectId type
    result = await notes_collection.delete_one({"_id": ObjectId(note_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
        
    # 204 No Content endpoints return nothing on success
    return None