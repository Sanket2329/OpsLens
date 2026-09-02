from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenResponse, UserLogin, UserRegister, UserResponse, UserUpdate
from app.security.dependencies import get_current_user
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
):
    try:
        token = AuthService(db).register(payload)
        return TokenResponse(access_token=token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    try:
        token = AuthService(db).login(payload.email, payload.password)
        return TokenResponse(access_token=token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's name."""
    current_user.name = payload.name
    repo = UserRepository(db)
    return repo.save(current_user)
