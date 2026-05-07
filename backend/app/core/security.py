"""
OfficerGuard Security - JWT auth, password hashing, role checks, geo-fencing
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

# Config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "vigil-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    request: Request = None
) -> User:
    """Dependency to get the authenticated user from JWT bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id, User.is_active == "Y").first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Geo-fencing check
    if user.allowed_ips:
        client_ip = request.client.host if request else "unknown"
        if client_ip not in user.allowed_ips:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied from IP {client_ip}. Allowed: {user.allowed_ips}"
            )

    # Time-locking check (business hours: 10:00 - 17:00 IST)
    now = datetime.utcnow()
    hour = (now.hour + 5) % 24 + (now.minute + 30) // 60  # rough IST conversion
    if not (10 <= hour < 17):
        # Allow ADMIN always, block OFFICER/AUDITOR outside hours
        if user.role != "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="Evaluation actions restricted to business hours (10:00-17:00 IST)"
            )

    return user


# Role-based dependencies
async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_officer_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("OFFICER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Officer access required")
    return user


# Geo-fencing middleware for sensitive actions
async def geo_fence_check(request: Request, user: User = Depends(get_current_user)) -> User:
    """Additional geo-fencing for critical endpoints (evaluation, report generation)."""
    client_ip = request.client.host if request else "unknown"
    if user.allowed_ips and client_ip not in user.allowed_ips:
        # Log security event
        from app.services.audit_chain import log_audit_event
        log_audit_event("GEO_FENCE_VIOLATION", {
            "user_id": user.id,
            "client_ip": client_ip,
            "path": request.url.path
        }, None)
        raise HTTPException(
            status_code=403,
            detail=f"Geo-fence violation: access from unauthorized IP {client_ip}"
        )
    return user
