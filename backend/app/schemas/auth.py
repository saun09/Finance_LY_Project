from pydantic import BaseModel


class SignupIn(BaseModel):
    username: str
    password: str


class LoginIn(BaseModel):
    username: str
    password: str


class AuthUserOut(BaseModel):
    user_id: str
    username: str
