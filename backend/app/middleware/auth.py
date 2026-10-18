from typing import Callable, List, Optional
from bson import ObjectId
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.database import Database

from app.config.database import get_database
from app.models.user import AccountStatus, UserRole
from app.schemas.user import UserResponseSchema
from app.utils.security import decode_access_token

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Database = Depends(get_database),
) -> UserResponseSchema:
    """Validate JWT access token from Authorization header and return active or verified pending doctor user profile."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = {}
    if ObjectId.is_valid(user_id):
        query = {"$or": [{"_id": ObjectId(user_id)}, {"_id": user_id}]}
    else:
        query = {"_id": user_id}

    user = db["users"].find_one(query)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("emailVerified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email verification required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.get("accountStatus") == AccountStatus.SUSPENDED.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is suspended.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Support restricted pending-doctor sessions (email verified, awaiting admin approval)
    is_pending_verified_doctor = (
        user.get("role") == UserRole.DOCTOR.value
        and user.get("emailVerified") is True
        and user.get("accountStatus") == AccountStatus.PENDING.value
    )

    if not is_pending_verified_doctor and user.get("accountStatus") != AccountStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive or suspended.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_profile = {
        "id": str(user["_id"]),
        "fullName": user["fullName"],
        "email": user["email"],
        "phone": user.get("phone"),
        "role": user["role"],
        "emailVerified": user["emailVerified"],
        "accountStatus": user["accountStatus"],
        "createdAt": user["createdAt"],
        "updatedAt": user.get("updatedAt"),
        "profileImage": user.get("profileImage"),
        "authProviders": user.get("authProviders"),
    }
    return UserResponseSchema(**user_profile)


def require_roles(allowed_roles: List[str]) -> Callable:
    """Dependency factory restricting access to specified roles."""
    def role_dependency(
        current_user: UserResponseSchema = Depends(get_current_user),
    ) -> UserResponseSchema:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return role_dependency


def require_role(role: str) -> Callable:
    """Dependency helper restricting access to a single role."""
    return require_roles([role])


require_patient = require_role("PATIENT")
require_doctor = require_role("DOCTOR")
require_admin = require_role("ADMIN")


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Database = Depends(get_database),
) -> Optional[UserResponseSchema]:
    """Extract authenticated user if JWT token is provided and valid, otherwise return None."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None

        query = {}
        if ObjectId.is_valid(user_id):
            query = {"$or": [{"_id": ObjectId(user_id)}, {"_id": user_id}]}
        else:
            query = {"_id": user_id}

        user = db["users"].find_one(query)
        if not user or not user.get("emailVerified"):
            return None
        if user.get("accountStatus") == AccountStatus.SUSPENDED.value:
            return None

        user_profile = {
            "id": str(user["_id"]),
            "fullName": user["fullName"],
            "email": user["email"],
            "phone": user.get("phone"),
            "role": user["role"],
            "emailVerified": user["emailVerified"],
            "accountStatus": user["accountStatus"],
            "createdAt": user["createdAt"],
            "updatedAt": user.get("updatedAt"),
            "profileImage": user.get("profileImage"),
            "authProviders": user.get("authProviders"),
        }
        return UserResponseSchema(**user_profile)
    except Exception:
        return None
