"""Profile pictures for patients and doctors (R02).

Storage decision
----------------
Avatars reuse the existing local encrypted-file architecture (``backend/uploads/<store>/``, git-ignored) and the
Phase 05 AES-256-GCM helper (``document_crypto``) with store name ``profile_images``. No external or paid service is
used. The MongoDB ``users`` document only holds a small reference:

* ``profileImage``      - the API path clients display, ``/api/profile/pictures/<userId>?v=<version>``;
* ``profileImageMeta``  - ``{storageKey, version, contentType, width, height, bytes, updatedAt}``.

No Base64 image is stored in MongoDB. Production limitation: local disk is per server; a multi-instance deployment
needs shared or object storage behind the same interface (documented in the R02 storage report).

Processing
----------
1. The upload is read with a hard byte cap (default 5 MB); larger bodies are refused without reading the rest.
2. Pillow identifies the real format from the content (the file name and the client's content type are ignored);
   only JPEG, PNG and WebP are accepted.
3. Header dimensions are checked before decoding (default max 8000 px per side, 40 megapixels), and Pillow's
   decompression-bomb error is turned into a 400, so a small file that expands to a huge bitmap is refused.
4. The image is fully decoded (malformed or truncated data fails here), EXIF orientation is applied, the optional
   square crop is applied, and the result is resized to 512 x 512 and re-encoded as a new JPEG. Re-encoding drops
   every metadata block (EXIF including GPS, XMP, ICC, comments), so nothing from the original file is stored.
5. The file name is a server-generated UUID under a directory named after the authenticated user id; no client
   input reaches the filesystem path.

Replacement is safe under concurrency: the new file is written first, then the user document is switched with one
atomic ``find_one_and_update`` that returns the previous reference, and only that previous file is deleted. If the
database update fails the new file is removed and the old picture stays. Two racing uploads both succeed in order,
the later one wins, and each removes exactly the file it replaced, so no orphan is left and the current file is never
deleted.

Visibility
----------
* Own picture: always.
* Doctor picture: any authenticated user when the doctor is APPROVED and ACTIVE (the same rule as doctor
  discovery); otherwise only the doctor and administrators. Uploading never changes a doctor's discoverability.
* Patient picture: the patient, and a doctor with an existing care relationship (the clinical access rule used for
  records). Not administrators, not other patients, not unrelated doctors.
Refusals return 404 so an outsider cannot tell whether a picture exists.

Pictures are display-only: they are never sent to an AI provider and never used for identification, inference or
ranking.
"""

from __future__ import annotations

import io
import logging
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from pymongo import ReturnDocument
from pymongo.database import Database

from app.config.settings import settings
from app.services.document_crypto import open_from_storage, seal_for_storage
from app.utils.rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)

STORE = "profile_images"
ALLOWED_FORMATS = {"JPEG": "JPEG", "PNG": "PNG", "WEBP": "WebP"}
OUTPUT_CONTENT_TYPE = "image/jpeg"
PICTURE_ROLES = {"PATIENT", "DOCTOR"}

upload_limiter = SlidingWindowRateLimiter(
    max_requests=settings.PROFILE_IMAGE_UPLOADS_PER_HOUR, window_seconds=3600, name="profile picture change",
    detail="Too many profile picture changes. Please try again later.")


def _base_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "uploads" / STORE


def picture_url(user_id: str, version: str) -> str:
    return f"/api/profile/pictures/{user_id}?v={version}"


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile picture not found.")


def _user_query(user_id: str) -> Dict[str, Any]:
    if ObjectId.is_valid(user_id):
        return {"$or": [{"_id": ObjectId(user_id)}, {"_id": user_id}]}
    return {"_id": user_id}


async def read_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read at most max_bytes + 1 bytes so an oversized body is refused without buffering all of it."""
    data = await file.read(max_bytes + 1)
    if not data:
        raise _bad("The selected file is empty.")
    if len(data) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"The image is larger than {max_bytes // (1024 * 1024)} MB.")
    return data


def _parse_crop(crop_x: Optional[float], crop_y: Optional[float], crop_size: Optional[float]):
    values = (crop_x, crop_y, crop_size)
    if all(v is None for v in values):
        return None
    if any(v is None for v in values):
        raise _bad("cropX, cropY and cropSize must be sent together.")
    if not (0 <= crop_x <= 1 and 0 <= crop_y <= 1 and 0 < crop_size <= 1):
        raise _bad("Crop values must be fractions between 0 and 1.")
    return crop_x, crop_y, crop_size


def process_image(data: bytes, crop: Optional[Tuple[float, float, float]] = None) -> Tuple[bytes, int, int]:
    """Validate untrusted image bytes and return (clean JPEG bytes, width, height)."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    max_pixels = settings.PROFILE_IMAGE_MAX_PIXELS
    max_dim = settings.PROFILE_IMAGE_MAX_DIMENSION
    out_size = settings.PROFILE_IMAGE_OUTPUT_SIZE
    previous_limit = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = max_pixels
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                probe = Image.open(io.BytesIO(data))
            except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
                raise _bad("The file is not a supported image. Use a JPEG, PNG or WebP photo.")
            except (Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise _bad("The image dimensions are too large.")
            fmt = (probe.format or "").upper()
            if fmt not in ALLOWED_FORMATS:
                raise _bad("Only JPEG, PNG or WebP images are accepted.")
            width, height = probe.size
            if width < 1 or height < 1 or width > max_dim or height > max_dim or width * height > max_pixels:
                raise _bad("The image dimensions are too large.")
            if getattr(probe, "n_frames", 1) > 1:
                raise _bad("Animated images are not accepted.")
            try:
                probe.verify()  # structural check (truncated or corrupt chunks)
                image = Image.open(io.BytesIO(data))
                image.load()  # full decode
            except (Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise _bad("The image dimensions are too large.")
            except Exception:  # noqa: BLE001 - any decoder failure means a malformed image
                raise _bad("The image file is damaged or incomplete.")
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit

    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        flat = Image.new("RGB", image.size, (255, 255, 255))
        flat.paste(image, mask=image.split()[-1])
        image = flat
    else:
        image = image.convert("RGB")

    w, h = image.size
    if crop is not None:
        cx, cy, cs = crop
        side = max(1, round(cs * min(w, h)))
        left = min(max(0, round(cx * w)), w - side)
        top = min(max(0, round(cy * h)), h - side)
    else:
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
    image = image.crop((left, top, left + side, top + side)).resize((out_size, out_size), Image.LANCZOS)

    clean = Image.new("RGB", image.size)  # fresh image: no info/exif/icc carried over
    clean.paste(image)
    out = io.BytesIO()
    clean.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue(), out_size, out_size


def _write(user_id: str, payload: bytes) -> str:
    key = f"{user_id}/{uuid.uuid4().hex}.jpg"
    path = (_base_dir() / key).resolve()
    if not str(path).startswith(str(_base_dir().resolve())):
        raise _bad("Invalid storage destination.")
    path.parent.mkdir(parents=True, exist_ok=True)
    sealed, _meta = seal_for_storage(payload, f"{STORE}/{key}")
    path.write_bytes(sealed)
    return key


def _remove(storage_key: Optional[str]) -> None:
    if not storage_key:
        return
    try:
        path = (_base_dir() / storage_key).resolve()
        if str(path).startswith(str(_base_dir().resolve())):
            path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove a replaced profile picture file.")


def _owner_id(user) -> str:
    return str(user.id)


def _role(user) -> str:
    role = getattr(user, "role", None)
    return str(getattr(role, "value", role) or "").upper()


async def upload(db: Database, user, file: UploadFile, crop_x=None, crop_y=None, crop_size=None) -> Dict[str, Any]:
    if _role(user) not in PICTURE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Profile pictures are available for patient and doctor accounts.")
    owner = _owner_id(user)
    upload_limiter.check(owner)
    crop = _parse_crop(crop_x, crop_y, crop_size)
    raw = await read_capped(file, settings.PROFILE_IMAGE_MAX_BYTES)
    clean, width, height = process_image(raw, crop)

    key = _write(owner, clean)
    version = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc)
    meta = {"storageKey": key, "version": version, "contentType": OUTPUT_CONTENT_TYPE, "width": width,
            "height": height, "bytes": len(clean), "updatedAt": now}
    try:
        before = db["users"].find_one_and_update(
            _user_query(owner),
            {"$set": {"profileImage": picture_url(owner, version), "profileImageMeta": meta, "updatedAt": now}},
            projection={"profileImageMeta": 1}, return_document=ReturnDocument.BEFORE)
    except Exception:
        _remove(key)  # keep the previous picture if the reference could not be switched
        raise
    if before is None:
        _remove(key)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    _remove((before.get("profileImageMeta") or {}).get("storageKey"))
    return {"profileImage": picture_url(owner, version), "version": version, "width": width, "height": height,
            "contentType": OUTPUT_CONTENT_TYPE}


def remove(db: Database, user) -> Dict[str, Any]:
    owner = _owner_id(user)
    upload_limiter.check(owner)
    now = datetime.now(timezone.utc)
    before = db["users"].find_one_and_update(
        _user_query(owner), {"$set": {"profileImage": None, "updatedAt": now}, "$unset": {"profileImageMeta": ""}},
        projection={"profileImageMeta": 1}, return_document=ReturnDocument.BEFORE)
    if before is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    _remove((before.get("profileImageMeta") or {}).get("storageKey"))
    return {"profileImage": None}


def _doctor_publicly_visible(db: Database, doctor_id: str, account: Dict[str, Any]) -> bool:
    if account.get("accountStatus") != "ACTIVE":
        return False
    profile = db["doctor_profiles"].find_one({"userId": doctor_id}, {"verificationStatus": 1})
    return bool(profile and profile.get("verificationStatus") == "APPROVED")


def can_view(db: Database, viewer, target_id: str, target: Dict[str, Any]) -> bool:
    viewer_id, viewer_role = _owner_id(viewer), _role(viewer)
    if viewer_id == target_id:
        return True
    target_role = str(target.get("role") or "").upper()
    if target_role == "DOCTOR":
        if viewer_role == "ADMIN":
            return True
        return _doctor_publicly_visible(db, target_id, target)
    if target_role == "PATIENT" and viewer_role == "DOCTOR":
        from app.services.clinical_safety_service import ClinicalSafetyService
        try:
            return bool(ClinicalSafetyService.verify_doctor_patient_care_relationship(db, viewer_id, target_id))
        except HTTPException:
            return False
    return False


def read_for(db: Database, viewer, target_id: str) -> Tuple[bytes, str, str]:
    """Return (jpeg bytes, version, content type) if the viewer may see target_id's picture, else 404."""
    if not target_id or len(target_id) > 64 or not all(c.isalnum() or c in "-_" for c in target_id):
        raise _not_found()  # path traversal and junk identifiers never reach storage
    target = db["users"].find_one(_user_query(target_id), {"role": 1, "accountStatus": 1, "profileImageMeta": 1})
    if not target or not can_view(db, viewer, target_id, target):
        raise _not_found()
    meta = target.get("profileImageMeta") or {}
    key = meta.get("storageKey")
    if not key:
        raise _not_found()
    path = (_base_dir() / key).resolve()
    if not str(path).startswith(str(_base_dir().resolve())) or not path.is_file():
        raise _not_found()
    try:
        data = open_from_storage(path.read_bytes(), f"{STORE}/{key}")
    except Exception:
        logger.warning("A stored profile picture could not be opened.")
        raise _not_found()
    return data, str(meta.get("version") or ""), str(meta.get("contentType") or OUTPUT_CONTENT_TYPE)
