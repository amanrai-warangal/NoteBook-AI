import os  # Added to read from your environment configuration
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import jwt

security_scheme = HTTPBearer()

# Load environment variables with fallback values for seamless local development
SECRET_KEY = os.getenv("SECRET_KEY", "DEVELOPMENT_SECRET_KEY_REPLACE_IN_PRODUCTION")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# Convert the string environment variable to a clean integer safely
env_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
ACCESS_TOKEN_EXPIRE_MINUTES = int(env_minutes)

# Tell passlib to use the industry-standard bcrypt algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- PASSWORD CRYPTOGRAPHY ---
def get_password_hash(password: str) -> str:
    """Converts a raw string password into a secure cryptographic hash."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compares a typed password against the stored hash to see if they match."""
    return pwd_context.verify(plain_password, hashed_password)


# --- JWT PASSPORT ENGINE ---
def create_access_token(data: dict) -> str:
    """Generates a signed, temporary JSON Web Token containing user claims."""
    to_encode = data.copy()

    # Set the token expiration timestamp using clean, timezone-aware offsets
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    # Sign the token using our secret key
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials : HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    """
    FastAPI Dependency: Inspects the Authorization header, decrypts the JWT token,
    verifies its signature, and extracts the payload claims.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate security credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms = [ALGORITHM])
        user_id : str = payload.get("user_id")
        username : str = payload.get("username")

        if user_id is None or username is None:
            raise credentials_exception
        
        return {"user_id" : user_id, "username" : username}
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Security token has expired")
    except jwt.PyJWTError:
        raise credentials_exception