from pydantic import BaseModel, Field
from typing import List, Optional

class NoteCreate(BaseModel):
    title : str = Field(...,min_length=1,max_length=100)
    content : str = Field(...)
    tags : List[str] = Field(default=[])

class NoteResponse(BaseModel):
    id : str = Field(...,alias="_id") #mongodb return _id and in python we cant use _something as ignored by compiler
    title : str
    content : str
    tags : List[str]

    class Config:
        populate_by_name = True  # Allows using either "id" or "_id" interchangeably

class NoteUpdate(BaseModel):
    title : Optional[str] = Field(None,min_length=1,max_length=100)
    content : Optional[str] = Field(None)
    tags : Optional[List[str]] = Field(None)