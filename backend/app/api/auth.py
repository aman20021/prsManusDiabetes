from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import DbDep, get_current_user
from app.db.models import User
from app.exceptions import AppError
from app.services.auth import authenticate_user, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbDep):
    user = authenticate_user(db, body.username, body.password)
    if not user:
        raise AppError(401, "UNAUTHORIZED", "Invalid username or password", [])
    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
        role=user.role.name,
        username=user.username,
    )


@router.get("/me")
def me(user: Annotated[User, Depends(get_current_user)]):
    return {"username": user.username, "role": user.role.name}
