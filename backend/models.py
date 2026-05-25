from pydantic import BaseModel, Field
from typing import List, Optional

class NoteCreate(BaseModel):
    title : str = Field(..., min_length=1, max_length=100)
    content : str = Field(...)
    tags : List[str] = Field(default=[])

class NoteResponse(BaseModel):
    id : str = Field(..., alias="_id") 
    title : str
    content : str
    tags : List[str]
    user_id : str  #ADDED: Keeps your private database rows serialized safely!
    embedding: Optional[List[float]] = None # ADDED: Allows storing raw floating-point numbers, holds 768 float array

    class Config:
        populate_by_name = True  

class NoteUpdate(BaseModel):
    title : Optional[str] = Field(None, min_length=1, max_length=100)
    content : Optional[str] = Field(None)
    tags : Optional[List[str]] = Field(None)

# ==========================================
# USER AUTHENTICATION SCHEMAS (UNCHANGED)
# ==========================================

class UserRegister(BaseModel):
    username : str = Field(..., min_length=3, max_length=50)
    password : str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username : str
    password : str

class UserResponse(BaseModel):
    id : str
    username : str

class TokenResponse(BaseModel):
    access_token : str
    token_type : str = "bearer"