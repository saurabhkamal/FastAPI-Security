from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.limiter import limiter
from app.schemas import LoginRequest, TokenResponse
from app.security import create_access_token, require_api_key, verify_password
from app.store import USERS, USERS_BY_EMAIL

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(require_api_key)])
@limiter.limit("5/minute")
def login(request: Request, credentials: LoginRequest):
    user_id = USERS_BY_EMAIL.get(credentials.email.lower())
    user = USERS.get(user_id) if user_id else None

    # SECURITY: identical generic message whether the email is unknown or the
    # password is wrong, so the response never reveals which one it was.
    if user is None or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user_id=user["id"], email=user["email"], role=user["role"])
    return TokenResponse(access_token=token, role=user["role"])
