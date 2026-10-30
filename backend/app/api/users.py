from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import DbDep, require_role
from app.db.models import Role, User
from app.exceptions import AppError
from app.services.auth import hash_password

router = APIRouter(prefix="/users", tags=["users"])

_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
_ROLES = ("clinician", "mlops")


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str


class AssignRoleRequest(BaseModel):
    role: str


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role.name,
    }


def _require_role(db, name: str) -> Role:
    if name not in _ROLES:
        raise AppError(422, "INVALID_ROLE", "Role must be clinician or mlops", [])
    role = db.query(Role).filter_by(name=name).first()
    if not role:
        raise AppError(422, "INVALID_ROLE", "Role must be clinician or mlops", [])
    return role


@router.get("")
def list_users(
    db: DbDep,
    actor: Annotated[User, Depends(require_role("mlops"))],
):
    users = db.query(User).order_by(User.username).all()
    return {"users": [_user_dict(u) for u in users]}


@router.post("", status_code=201)
def create_user(
    body: CreateUserRequest,
    db: DbDep,
    actor: Annotated[User, Depends(require_role("mlops"))],
):
    username = body.username.strip()
    if not _USERNAME.match(username):
        raise AppError(
            422,
            "INVALID_USERNAME",
            "Username must be 2–64 characters and use letters, numbers, dots, underscores, or hyphens",
            [],
        )
    if len(body.password) < 8:
        raise AppError(422, "WEAK_PASSWORD", "Password must be at least 8 characters", [])

    if db.query(User).filter_by(username=username).first():
        raise AppError(409, "CONFLICT", f"Username {username} is already taken", [])

    role = _require_role(db, body.role)
    user = User(username=username, password_hash=hash_password(body.password), role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_dict(user)


@router.patch("/{user_id}")
def assign_role(
    user_id: int,
    body: AssignRoleRequest,
    db: DbDep,
    actor: Annotated[User, Depends(require_role("mlops"))],
):
    target = db.query(User).filter_by(id=user_id).first()
    if not target:
        raise AppError(404, "NOT_FOUND", "User not found", [])
    if target.id == actor.id:
        raise AppError(422, "SELF_ROLE", "You cannot change your own role", [])

    role = _require_role(db, body.role)
    if target.role.name == "mlops" and role.name != "mlops":
        other_mlops = (
            db.query(User)
            .filter(User.role_id == target.role_id, User.id != target.id)
            .count()
        )
        if other_mlops == 0:
            raise AppError(422, "LAST_MLOPS", "Keep at least one MLOps user", [])

    target.role_id = role.id
    db.commit()
    db.refresh(target)
    return _user_dict(target)
