from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.exceptions import AppError
from app.services.auth import decode_token

DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(401, "UNAUTHORIZED", "Missing bearer token", [])
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    user = db.query(User).filter_by(id=int(payload["sub"])).first()
    if not user:
        raise AppError(401, "UNAUTHORIZED", "User not found", [])
    return user


def require_role(*roles: str):
    def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role.name not in roles:
            raise AppError(403, "FORBIDDEN", "Insufficient permissions", [])
        return user

    return _dep
