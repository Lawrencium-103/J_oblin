from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, email: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": exp, "iat": datetime.now(timezone.utc)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"user_id": int(payload["sub"]), "email": payload["email"]}
    except (JWTError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(credentials.credentials)


async def optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict | None:
    if credentials is None:
        return None
    try:
        return decode_token(credentials.credentials)
    except Exception:
        return None
