from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate


class AuthService:
    """Service layer for authentication and registration."""

    @staticmethod
    def register_user(db: Session, user_in: UserCreate) -> User:
        """
        Register a new user in the database.
        Raises 409 Conflict if email already exists.
        """
        existing_user = db.query(User).filter(User.email == user_in.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        hashed_password = get_password_hash(user_in.password)
        db_user = User(
            email=user_in.email,
            username=user_in.username,
            hashed_password=hashed_password,
            role=UserRole.USER,
            is_active=True,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        """
        Verify credentials and update last_login.
        Raises 401 Unauthorized or 403 Forbidden for failure.
        """
        db_user = db.query(User).filter(User.email == email).first()
        if not db_user or not verify_password(password, db_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not db_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )

        # Update last login timestamp
        db_user.last_login = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_user)
        return db_user
