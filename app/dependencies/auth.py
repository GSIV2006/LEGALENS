"""
Authentication Dependencies

JWT authentication and role-based access control dependencies.
"""
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import TokenData


# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    auto_error=True,
)


def _decode_token(token: str) -> TokenData:
    """
    Decode JWT token and return token data.

    Args:
        token: JWT token string

    Returns:
        TokenData with user information

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: Optional[int] = payload.get("sub")
        email: Optional[str] = payload.get("email")
        role: Optional[str] = payload.get("role")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenData(
            user_id=user_id,
            email=email,
            role=role,
        )

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to get the current authenticated user.

    Returns:
        User object if authenticated

    Raises:
        HTTPException: If not authenticated
    """
    token_data = _decode_token(token)

    user = db.query(User).filter(User.id == token_data.user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get the current active user.

    Returns:
        User object if authenticated and active

    Raises:
        HTTPException: If not authenticated or inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


def require_role(
    required_roles: List[str],
):
    """
    Factory function to create role-based dependency.

    Args:
        required_roles: List of allowed roles

    Returns:
        Dependency function that checks user role

    Example:
        @router.post("/rules")
        def create_rule(
            rules: RuleCreate,
            current_user: User = Depends(require_role(["ADMIN"])),
            db: Session = Depends(get_db),
        ):
            ...
    """
    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required roles: {required_roles}",
            )
        return current_user
    return role_checker


class RoleChecker:
    """
    Class-based dependency for role checking.

    Can be used as:
        RoleChecker(["ADMIN", "INSPECTOR"])
    """

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required roles: {self.allowed_roles}",
            )
        return current_user


# Convenience instances
admin_only = RoleChecker(["ADMIN"])
admin_or_inspector = RoleChecker(["ADMIN", "INSPECTOR"])
inspector_or_viewer = RoleChecker(["INSPECTOR", "VIEWER"])
all_roles = RoleChecker(["ADMIN", "INSPECTOR", "VIEWER"])
