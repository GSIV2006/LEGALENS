"""
Storage Service - File storage abstraction layer.

For LOCAL development:
    Files are saved to uploads/ folder

For Vercel/production:
    Storage is configurable via STORAGE_MODE env variable

Modes:
    - local: Save files to filesystem (uploads/)
    - memory: Store file metadata in database (for serverless/prototypes)
    - s3: External object storage (Supabase, AWS S3, etc.) - future integration

The rest of the backend does NOT depend on filesystem paths directly.
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, BinaryIO
from datetime import datetime

from app.config import settings


class StorageService:
    """
    Storage service abstraction for handling file uploads.

    Supports multiple storage backends and provides a consistent
    interface regardless of where files are actually stored.
    """

    def __init__(self):
        """Initialize storage service based on configuration."""
        self.mode = settings.STORAGE_MODE.lower()
        self.upload_dir = settings.UPLOAD_DIR

        # Ensure upload directory exists for local mode
        if self.mode == "local":
            self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Initialize backend-specific configuration
        self._init_backend()

    def _init_backend(self):
        """Initialize backend-specific configuration."""
        if self.mode == "local":
            # Local filesystem storage
            self.view_dirs = {}
            for view_type in ["front", "back", "left", "right", "top", "bottom", "other"]:
                view_dir = self.upload_dir / view_type
                view_dir.mkdir(parents=True, exist_ok=True)
                self.view_dirs[view_type] = view_dir

        elif self.mode == "memory":
            # In-memory storage would use database fallback
            # For prototype, we'll store file metadata only
            pass

        elif self.mode == "s3":
            # S3/Supabase storage - would need boto3 or similar
            # Configuration from environment
            self.s3_bucket = os.getenv("S3_BUCKET_NAME", "")
            self.s3_endpoint = os.getenv("S3_ENDPOINT_URL", "")
            self.s3_access_key = os.getenv("S3_ACCESS_KEY", "")
            self.s3_secret_key = os.getenv("S3_SECRET_KEY", "")

    async def save_image(
        self,
        file_data: BinaryIO,
        filename: str,
        view_type: str,
        inspection_id: int,
        content_type: str = "image/jpeg",
        file_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Save an uploaded image.

        Args:
            file_data: File-like object with image data
            filename: Original filename
            view_type: Type of view (front, back, left, right, top, bottom, other)
            inspection_id: Associated inspection ID
            content_type: MIME type of the file
            file_size: Size of the file in bytes

        Returns:
            Dictionary with storage information
        """
        # Validate view type
        valid_views = ["front", "back", "left", "right", "top", "bottom", "other"]
        if view_type not in valid_views:
            raise ValueError(f"Invalid view type: {view_type}. Must be one of {valid_views}")

        # Generate unique storage filename
        ext = filename.lower().split(".")[-1] if "." in filename else "jpg"
        storage_filename = f"{inspection_id}_{uuid.uuid4().hex}.{ext}"
        storage_path = None
        storage_url = None

        if self.mode == "local":
            # Save to local filesystem
            view_dir = self.view_dirs.get(view_type, self.upload_dir)
            file_path = view_dir / storage_filename

            with open(file_path, "wb") as f:
                shutil.copyfileobj(file_data, f)

            storage_path = str(file_path)
            storage_url = f"/uploads/{view_type}/{storage_filename}"

        elif self.mode == "memory":
            # For memory mode, we'd store in database
            # For now, create a placeholder
            storage_path = f"memory:{inspection_id}:{storage_filename}"
            storage_url = f"/api/inspections/{inspection_id}/images/{storage_filename}"

        elif self.mode == "s3":
            # S3 storage would use boto3
            # Placeholder for future implementation
            storage_path = f"s3:{self.s3_bucket}:{storage_filename}"
            storage_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{storage_filename}"

        return {
            "filename": filename,
            "storage_filename": storage_filename,
            "storage_path": storage_path,
            "storage_url": storage_url,
            "view_type": view_type,
            "content_type": content_type,
            "file_size": file_size,
            "saved_at": datetime.utcnow().isoformat(),
        }

    async def delete_image(self, storage_path: str) -> bool:
        """
        Delete an image from storage.

        Args:
            storage_path: Path where the image is stored

        Returns:
            True if deleted successfully
        """
        if self.mode == "local" and storage_path and storage_path.startswith("/"):
            try:
                Path(storage_path).unlink(missing_ok=True)
                return True
            except Exception:
                return False
        return True

    async def get_image_url(self, storage_path: str) -> Optional[str]:
        """
        Get a URL for accessing the stored image.

        Args:
            storage_path: Path where the image is stored

        Returns:
            URL for accessing the image, or None
        """
        if self.mode == "local" and storage_path:
            # Return relative URL for local development
            return storage_path.replace(str(self.upload_dir), "/uploads")
        return storage_path

    async def get_image_bytes(self, storage_path: str) -> Optional[bytes]:
        """
        Read image bytes from storage.

        Args:
            storage_path: Path where the image is stored

        Returns:
            Image bytes or None if not found
        """
        if self.mode == "local" and storage_path and os.path.exists(storage_path):
            with open(storage_path, "rb") as f:
                return f.read()
        return None

    def validate_file_size(self, file_size: int, max_size: int = 10 * 1024 * 1024) -> bool:
        """
        Validate file size.

        Args:
            file_size: Size in bytes
            max_size: Maximum allowed size (default 10MB)

        Returns:
            True if file size is acceptable
        """
        return file_size <= max_size

    def validate_file_type(self, content_type: str) -> bool:
        """
        Validate file content type.

        Args:
            content_type: MIME type

        Returns:
            True if file type is acceptable
        """
        allowed_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
        ]
        return content_type.lower() in allowed_types

    def get_storage_mode(self) -> str:
        """Get current storage mode."""
        return self.mode


# Dependency for getting storage service
def get_storage_service() -> StorageService:
    """Dependency for injecting storage service."""
    return StorageService()


# Global instance
storage_service = StorageService()
