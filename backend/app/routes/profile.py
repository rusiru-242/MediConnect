"""R02: profile pictures (patients and doctors) and patient profile data."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Path, Response, UploadFile
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user
from app.schemas.user import UserResponseSchema
from app.services import patient_profile_service, profile_image_service

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me")
def get_my_profile(user: UserResponseSchema = Depends(get_current_user), db: Database = Depends(get_database)):
    """The patient's own profile: identity, patient-reported health profile and recorded allergies."""
    return patient_profile_service.get_profile(db, user)


@router.patch("/me")
def update_my_profile(body: patient_profile_service.ProfileUpdate,
                      user: UserResponseSchema = Depends(get_current_user), db: Database = Depends(get_database)):
    return patient_profile_service.update_profile(db, user, body)


@router.post("/me/picture")
async def upload_my_picture(
    file: UploadFile = File(...),
    cropX: Optional[float] = Form(default=None),
    cropY: Optional[float] = Form(default=None),
    cropSize: Optional[float] = Form(default=None),
    user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
):
    """Upload or replace the caller's own picture. The owner is always the authenticated user."""
    return await profile_image_service.upload(db, user, file, cropX, cropY, cropSize)


@router.delete("/me/picture")
def remove_my_picture(user: UserResponseSchema = Depends(get_current_user), db: Database = Depends(get_database)):
    return profile_image_service.remove(db, user)


@router.get("/pictures/{user_id}")
def get_picture(user_id: str = Path(..., max_length=64), user: UserResponseSchema = Depends(get_current_user),
                db: Database = Depends(get_database)):
    data, version, content_type = profile_image_service.read_for(db, user, user_id)
    # Private: only the authenticated client may cache it; the version in the URL changes on every replacement.
    return Response(content=data, media_type=content_type, headers={
        "Cache-Control": "private, max-age=86400", "ETag": f'"{version}"', "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline"})
