from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.auth import AuthUserOut, LoginIn, SignupIn
from app.services.auth_service import (
    InvalidCredentialsError,
    UsernameTakenError,
    WeakPasswordError,
    login,
    signup,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthUserOut, status_code=201)
def post_signup(body: SignupIn, session: Session = Depends(get_session)):
    try:
        user = signup(session, body.username, body.password)
    except UsernameTakenError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WeakPasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AuthUserOut(user_id=user.user_id, username=user.username)


@router.post("/login", response_model=AuthUserOut)
def post_login(body: LoginIn, session: Session = Depends(get_session)):
    try:
        user = login(session, body.username, body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return AuthUserOut(user_id=user.user_id, username=user.username)
