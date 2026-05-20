from fastapi import FastAPI, HTTPException, status
from models import NoteCreate, NoteResponse
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
async def get_all_notes():
    notes = []
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