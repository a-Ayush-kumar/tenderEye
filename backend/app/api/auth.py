"""
OfficerGuard Auth API - Registration, login, token refresh, profile
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models import User
from app.core.security import (
    get_password_hash, verify_password, create_access_token,
    get_current_user
)
from app.services.audit_chain import log_audit_event

router = APIRouter()


# ========== Pydantic Models ==========

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    department: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = "OFFICER"  # ADMIN, OFFICER, AUDITOR
    allowed_ips: Optional[list] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    department: Optional[str]
    designation: Optional[str]
    role: str
    last_login: Optional[datetime]
    dsc_serial: Optional[str]
    dsc_valid_until: Optional[datetime]
    is_active: str


class DSCBindRequest(BaseModel):
    dsc_serial: str
    dsc_issuer: str
    dsc_valid_until: datetime


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


# ========== API Routes ==========

@router.post("/register", response_model=UserResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new officer/admin user."""
    # Check if email exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Only allow ADMIN creation if no users exist (first admin), else require admin auth
    admin_count = db.query(User).filter(User.role == "ADMIN").count()
    if admin_count > 0 and request.role == "ADMIN":
        raise HTTPException(status_code=403, detail="Contact existing admin to create admin accounts")

    user = User(
        email=request.email,
        name=request.name,
        hashed_password=get_password_hash(request.password),
        department=request.department,
        designation=request.designation,
        role=request.role if admin_count > 0 else "ADMIN",  # First user = admin
        allowed_ips=request.allowed_ips or [],
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_audit_event("USER_REGISTERED", {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "department": user.department
    }, db)

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        department=user.department,
        designation=user.designation,
        role=user.role,
        last_login=user.last_login,
        dsc_serial=user.dsc_serial,
        dsc_valid_until=user.dsc_valid_until,
        is_active=user.is_active
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, req: Request, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.hashed_password):
        # Log failed attempt
        log_audit_event("LOGIN_FAILED", {
            "email": request.email,
            "ip": req.client.host if req.client else "unknown"
        }, db)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.is_active != "Y":
        raise HTTPException(status_code=403, detail="Account deactivated")

    # Update last login
    user.last_login = datetime.utcnow()
    user.last_login_ip = req.client.host if req.client else "unknown"
    user.failed_logins = 0
    db.commit()

    access_token = create_access_token(data={"sub": user.id, "role": user.role})

    log_audit_event("LOGIN_SUCCESS", {
        "user_id": user.id,
        "email": user.email,
        "ip": user.last_login_ip
    }, db)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=3600,  # 1 hour
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "department": user.department
        }
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        department=user.department,
        designation=user.designation,
        role=user.role,
        last_login=user.last_login,
        dsc_serial=user.dsc_serial,
        dsc_valid_until=user.dsc_valid_until,
        is_active=user.is_active
    )


@router.post("/bind-dsc")
def bind_dsc(request: DSCBindRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Bind Class 3 Digital Signature Certificate to user account."""
    user.dsc_serial = request.dsc_serial
    user.dsc_issuer = request.dsc_issuer
    user.dsc_valid_until = request.dsc_valid_until
    db.commit()

    log_audit_event("DSC_BOUND", {
        "user_id": user.id,
        "dsc_serial": request.dsc_serial,
        "issuer": request.dsc_issuer
    }, db)

    return {"status": "DSC bound successfully", "dsc_serial": request.dsc_serial}


@router.post("/change-password")
def change_password(request: PasswordChangeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change user password."""
    if not verify_password(request.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = get_password_hash(request.new_password)
    db.commit()

    log_audit_event("PASSWORD_CHANGED", {"user_id": user.id}, db)
    return {"status": "Password updated successfully"}


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    """Logout (client should discard token). Server-side: log event."""
    log_audit_event("LOGOUT", {"user_id": user.id}, None)
    return {"status": "Logged out successfully"}
