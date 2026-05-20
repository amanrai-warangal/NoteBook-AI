from pydantic import BaseModel, Field
from typing import List

class NoteCreate(BaseModel):
    title : str = Field(...,min_length=1,max_length=100,description="the title of the note")
    content : str = Field(...,description="the main text content of the note")
    tags : List[str] = Field(default=[],description="list of category tags for the note")

class NoteResponse(BaseModel):
    id : int
    title : str
    content : str
    tags : List[str]