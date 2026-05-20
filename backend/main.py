from fastapi import FastAPI,HTTPException
from models import NoteCreate,NoteResponse
from typing import List
app = FastAPI(title="Smart Notes App")

NOTE_DB = [
        {"id": 1, "title": "my_note1", "content": "This is my note","tags" : ['adventure']},
        {"id": 2, "title": "my_note2", "content": "This is my note2", "tags" : ['romance']}
    ]

id_counter = 3

@app.get("/")
def greet():
    return "Welcome to Smart Notes App"

@app.get("/notes",response_model = List[NoteResponse])
def get_all_notes():
    return NOTE_DB

@app.post("/notes",response_model = NoteResponse, status_code=201)
def create_note(node_data : NoteCreate):
    global id_counter

    new_note = node_data.model_dump()
    new_note["id"] = id_counter
    NOTE_DB.append(new_note)

    id_counter += 1

    return new_note

@app.get("/notes/{note_id}",response_model=NoteResponse)
def get_note(note_id : int):
    for note in NOTE_DB:
        if note["id"] == note_id:
            return note

    raise HTTPException(status_code=404,detail=f"Note with ID : {note_id} doesn't exist")