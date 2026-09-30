import os
from pathlib import Path
from typing import Any, Dict, Protocol, Set
import uuid
from fastapi import HTTPException, UploadFile, status

# Allowed file configurations
ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".jpg", ".jpeg", ".png"}

ALLOWED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}

# Maximum file size: 5 MB per document
MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024

# Magic byte signatures
MAGIC_BYTES = {
    "pdf": b"%PDF-",
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
}


def _verify_magic_bytes(content_prefix: bytes, extension: str) -> bool:
    """Verify that file content header matches expected file type."""
    ext = extension.lower()
    if ext == ".pdf":
        return content_prefix.startswith(MAGIC_BYTES["pdf"])
    elif ext == ".png":
        return content_prefix.startswith(MAGIC_BYTES["png"])
    elif ext in {".jpg", ".jpeg"}:
        return content_prefix.startswith(MAGIC_BYTES["jpeg"])
    return False


class DocumentStorageProtocol(Protocol):
    """Abstraction for document storage, allowing easy swap with cloud storage."""

    async def save_document(
        self,
        file: UploadFile,
        document_type: str,
        user_id: str,
    ) -> Dict[str, Any]:
        ...

    def get_document_path(self, relative_path: str) -> Path:
        ...


class LocalDocumentStorageService:
    """Secure local filesystem implementation of document storage."""

    def __init__(self, base_directory: Path | None = None) -> None:
        if base_directory is None:
            # backend/uploads/doctor_verification
            project_root = Path(__file__).resolve().parent.parent.parent
            self.base_dir = project_root / "uploads" / "doctor_verification"
        else:
            self.base_dir = base_directory

        # Ensure directory exists with appropriate permissions
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_document(
        self,
        file: UploadFile,
        document_type: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Validate and securely store a verification document."""
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing file for {document_type}.",
            )

        original_filename = Path(file.filename).name  # Prevent path traversal in raw filename
        extension = Path(original_filename).suffix.lower()

        # 1. Validate file extension
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type for {document_type}. Only PDF, JPG, JPEG, and PNG files are accepted.",
            )

        # 2. Validate MIME content-type header
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type ({content_type}) for {document_type}.",
            )

        # 3. Read content and validate size
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The uploaded file for {document_type} is empty.",
            )

        if file_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {original_filename} exceeds maximum allowed size of {max_mb}MB.",
            )

        # 4. Validate content magic bytes (header inspection)
        if not _verify_magic_bytes(content[:16], extension):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File content does not match the file extension for {document_type}.",
            )

        # 5. Generate secure, unique, non-enumerable filename
        safe_name = f"{document_type}_{uuid.uuid4().hex}{extension}"

        # Organize by user directory to prevent directory saturation
        user_dir = self.base_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        target_path = user_dir / safe_name

        # Ensure canonical path is strictly within base directory (path traversal defense)
        if not str(target_path.resolve()).startswith(str(self.base_dir.resolve())):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security validation failed for file destination.",
            )

        # Write file contents
        with open(target_path, "wb") as f:
            f.write(content)

        # Relative path from base_dir for storage
        relative_storage_path = f"{user_id}/{safe_name}"

        return {
            "documentType": document_type,
            "filename": safe_name,
            "originalFilename": original_filename,
            "contentType": content_type,
            "fileSize": file_size,
            "storagePath": relative_storage_path,
        }

    def get_document_path(self, relative_path: str) -> Path:
        """Resolve a stored relative document path, strictly validating against traversal."""
        cleaned_path = Path(relative_path).as_posix().lstrip("/\\")
        full_path = (self.base_dir / cleaned_path).resolve()
        if not str(full_path).startswith(str(self.base_dir.resolve())):
            raise ValueError("Unauthorized document path access.")
        return full_path


document_storage = LocalDocumentStorageService()
