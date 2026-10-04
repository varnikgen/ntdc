"""Управление пользователями веб-админки (только role=admin)."""

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import AdminUser
from app.security import hash_password, normalize_mac
from app.services.audit import log_action

router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = ("admin", "operator", "viewer")


@router.get("/", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    users = db.query(AdminUser).order_by(AdminUser.username).all()
    return request.app.state.templates.TemplateResponse(
        "users/list.html",
        {"request": request, "users": users},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_user_form(request: Request):
    return request.app.state.templates.TemplateResponse(
        "users/edit.html",
        {"request": request, "user": None, "roles": VALID_ROLES},
    )


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return request.app.state.templates.TemplateResponse(
        "users/edit.html",
        {"request": request, "user": user, "roles": VALID_ROLES},
    )


@router.post("/")
async def create_user(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("operator"),
    is_active: str = Form("1"),
):
    username = (username or "").strip()
    if not username or len(username) < 2:
        raise HTTPException(400, "Username too short")
    if len(password or "") < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if role not in VALID_ROLES:
        raise HTTPException(400, "Invalid role")

    existing = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing:
        raise HTTPException(400, "Username already exists")

    user = AdminUser(
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active in ("1", "true", "on", "yes"),
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(
        db, "CREATE_USER", "AdminUser", user.id,
        getattr(request.state, "admin_user", "admin"),
        f"Created user {username} role={role}",
    )
    return JSONResponse({"status": "success", "id": user.id, "message": "User created"})


@router.post("/{user_id}/update")
async def update_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(""),
    role: str = Form("operator"),
    is_active: str = Form("1"),
):
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    username = (username or "").strip()
    if not username or len(username) < 2:
        raise HTTPException(400, "Username too short")
    if role not in VALID_ROLES:
        raise HTTPException(400, "Invalid role")

    clash = (
        db.query(AdminUser)
        .filter(AdminUser.username == username, AdminUser.id != user_id)
        .first()
    )
    if clash:
        raise HTTPException(400, "Username already exists")

    user.username = username
    user.role = role
    user.is_active = is_active in ("1", "true", "on", "yes")
    if password and password.strip():
        if len(password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        user.password_hash = hash_password(password)

    db.commit()
    log_action(
        db, "UPDATE_USER", "AdminUser", user.id,
        getattr(request.state, "admin_user", "admin"),
        f"Updated user {username} role={role} active={user.is_active}",
    )
    return JSONResponse({"status": "success", "message": "User updated"})


@router.post("/{user_id}/delete")
async def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    # Нельзя удалить самого себя
    current = getattr(request.state, "admin_user", None)
    if current and user.username == current:
        raise HTTPException(400, "Cannot delete yourself")

    uname = user.username
    db.delete(user)
    db.commit()
    log_action(
        db, "DELETE_USER", "AdminUser", user_id,
        current or "admin",
        f"Deleted user {uname}",
    )
    return JSONResponse({"status": "success", "message": "User deleted"})
