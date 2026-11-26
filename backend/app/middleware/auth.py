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


def _aware(value):
    from datetime import timezone
    if value is None or getattr(value, "tzinfo", None) is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def access_token_revoked(payload: dict, user: dict, db: Database) -> bool:
    """True when the access token was revoked at logout (jti deny-list) or issued before the account's
    ``tokensValidAfter`` (set on suspension and password reset), Phase 05."""
    valid_after = _aware(user.get("tokensValidAfter"))
    if valid_after is not None and int(payload.get("iat") or 0) < int(valid_after.timestamp()):
        return True
    jti = payload.get("jti")
    return bool(jti) and db["revoked_access_tokens"].find_one({"_id": jti}, {"_id": 1}) is not None


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
    if access_token_revoked(payload, user, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has ended. Please log in again.",
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
require_doctor_applicant = require_role("DOCTOR")
require_admin = require_role("ADMIN")


def require_approved_doctor(
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> UserResponseSchema:
    """Enforces that the current authenticated user is a verified, active, and approved DOCTOR.

    Prevents pending or rejected doctors from accessing protected clinical/doctor APIs,
    even with old or manually crafted tokens.
    """
    if current_user.role != UserRole.DOCTOR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )

    # Query live doctor profile from database to prevent token bypass
    profile = db["doctor_profiles"].find_one({"userId": str(current_user.id)})
    ver_status = profile.get("verificationStatus") if profile else None

    if ver_status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your doctor registration application was not approved. Please contact MediConnect support for further information.",
        )

    if current_user.accountStatus != AccountStatus.ACTIVE.value or ver_status != "APPROVED":
        if not current_user.emailVerified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before continuing.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your doctor registration is currently under review (pending admin approval / accreditation). Only verified doctors can access clinical records and the doctor dashboard once an administrator approves your application.",
        )

    return current_user


require_doctor = require_approved_doctor


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
        if not user or not user.get("emailVerified") or access_token_revoked(payload, user, db):
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
