"""
File operations endpoints.
"""

import os
import mimetypes
import shutil
from typing import Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from models.schemas import FileItem, DirectoryListing
from core.config import settings

router = APIRouter(prefix="/api/files", tags=["Files"])


@router.get("/list")
async def list_directory(path: str = ""):
    """List files and directories in the specified path."""
    try:
        # Expand user path and resolve
        if path.startswith("~"):
            path = os.path.expanduser(path)

        if not path:
            path = os.path.expanduser(settings.default_work_dir)

        path = os.path.abspath(path)

        # Security check - ensure path exists
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Directory not found")

        if not os.path.isdir(path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        items = []
        try:
            for item_name in sorted(os.listdir(path)):
                item_path = os.path.join(path, item_name)

                # Skip hidden files
                if item_name.startswith('.'):
                    continue

                stat_info = os.stat(item_path)
                is_dir = os.path.isdir(item_path)

                file_item = FileItem(
                    name=item_name,
                    path=item_path,
                    type="directory" if is_dir else "file",
                    size=None if is_dir else stat_info.st_size,
                    modified=stat_info.st_mtime,
                    mime_type=None if is_dir else mimetypes.guess_type(item_path)[0]
                )
                items.append(file_item)
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")

        # Get parent directory
        parent = os.path.dirname(path) if path != "/" else None

        return DirectoryListing(
            path=path,
            items=items,
            parent=parent
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/content")
async def get_file_content(path: str):
    """Get the content of a file."""
    try:
        # Expand user path and resolve
        if path.startswith("~"):
            path = os.path.expanduser(path)

        path = os.path.abspath(path)

        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="File not found")

        if not os.path.isfile(path):
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Check file size
        file_size = os.path.getsize(path)
        max_size = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(status_code=413, detail="File too large")

        # Try to read as text first
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                "path": path,
                "content": content,
                "type": "text",
                "size": file_size,
                "mime_type": mimetypes.guess_type(path)[0]
            }
        except UnicodeDecodeError:
            # If it's not text, return file info only
            return {
                "path": path,
                "content": None,
                "type": "binary",
                "size": file_size,
                "mime_type": mimetypes.guess_type(path)[0],
                "message": "Binary file - content not displayed"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear-directory")
async def clear_directory(path: str):
    """Clear all contents of a directory."""
    try:
        # Expand user path
        if path.startswith("~"):
            path = os.path.expanduser(path)

        abs_path = os.path.abspath(path)

        # Security check - ensure path exists and is a directory
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Directory not found")

        if not os.path.isdir(abs_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        # Count items before deletion
        items_deleted = 0

        # Remove all contents
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
            items_deleted += 1

        return {
            "message": f"Successfully cleared directory: {path}",
            "items_deleted": items_deleted,
            "path": abs_path
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing directory: {str(e)}")


@router.get("/images")
async def get_images(work_dir: str):
    """Get all image files from the working directory."""
    try:
        # Expand user path
        if work_dir.startswith("~"):
            work_dir = os.path.expanduser(work_dir)

        abs_path = os.path.abspath(work_dir)

        # Check if directory exists
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            return {"images": [], "message": "Working directory not found"}

        # Common image extensions
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.tiff', '.tif'}

        images = []

        # Recursively search for image files
        for root, dirs, files in os.walk(abs_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()

                if file_ext in image_extensions:
                    # Get relative path from work_dir
                    rel_path = os.path.relpath(file_path, abs_path)

                    # Get file stats
                    stat = os.stat(file_path)

                    images.append({
                        "name": file,
                        "path": file_path,
                        "relative_path": rel_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "extension": file_ext,
                        "directory": os.path.dirname(rel_path) if os.path.dirname(rel_path) else "root"
                    })

        # Sort by modification time (newest first)
        images.sort(key=lambda x: x['modified'], reverse=True)

        return {
            "work_dir": work_dir,
            "images": images,
            "count": len(images)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scanning for images: {str(e)}")


@router.get("/serve-image")
async def serve_image(path: str):
    """Serve an image file."""
    try:
        # Security check - ensure path exists and is a file
        abs_path = os.path.abspath(path)

        if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="Image file not found")

        # Check if it's an image file
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.tiff', '.tif'}
        file_ext = os.path.splitext(abs_path)[1].lower()

        if file_ext not in image_extensions:
            raise HTTPException(status_code=400, detail="File is not an image")

        # Determine MIME type
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff'
        }

        mime_type = mime_types.get(file_ext, 'application/octet-stream')

        # Return the file
        return FileResponse(abs_path, media_type=mime_type)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")


@router.get("/find")
async def find_file(directory: str, filename: str):
    """Recursively search for a file by name within a directory."""
    try:
        if directory.startswith("~"):
            directory = os.path.expanduser(directory)

        abs_dir = os.path.abspath(directory)

        if not os.path.exists(abs_dir) or not os.path.isdir(abs_dir):
            raise HTTPException(status_code=404, detail="Directory not found")

        # Sanitize filename to prevent path traversal
        safe_filename = os.path.basename(filename)
        if not safe_filename or safe_filename.startswith('.'):
            raise HTTPException(status_code=400, detail="Invalid filename")

        matches = []
        for root, dirs, files in os.walk(abs_dir):
            for f in files:
                if f == safe_filename:
                    full_path = os.path.join(root, f)
                    stat = os.stat(full_path)
                    matches.append({
                        "name": f,
                        "path": full_path,
                        "relative_path": os.path.relpath(full_path, abs_dir),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })

        # Sort by modification time (newest first)
        matches.sort(key=lambda x: x['modified'], reverse=True)

        return {
            "directory": abs_dir,
            "filename": safe_filename,
            "matches": matches,
            "count": len(matches),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding file: {str(e)}")


# Allowed extensions for file upload
_UPLOAD_ALLOWED_EXTENSIONS = {
    '.csv', '.txt', '.md', '.json', '.fits', '.npy',
    '.h5', '.hdf5', '.dat', '.tsv', '.xlsx', '.xls',
    '.png', '.jpg', '.jpeg', '.pdf',
}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    task_id: str = Form(...),
    subfolder: str = Form("input_files"),
):
    """Upload a file for a Denario research task.

    Files are stored in {work_dir}/denario_tasks/{task_id}/{subfolder}/.
    """
    # Validate extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _UPLOAD_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' not allowed. Allowed: {sorted(_UPLOAD_ALLOWED_EXTENSIONS)}"
        )

    # Prevent path traversal in filename
    safe_name = os.path.basename(file.filename or "upload")
    if not safe_name or safe_name.startswith('.'):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Prevent path traversal in subfolder
    safe_subfolder = os.path.normpath(subfolder).lstrip(os.sep)
    if ".." in safe_subfolder:
        raise HTTPException(status_code=400, detail="Invalid subfolder path")

    # Build target directory
    base_work_dir = os.path.expanduser(settings.default_work_dir)
    target_dir = os.path.join(base_work_dir, "denario_tasks", task_id, safe_subfolder)
    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, safe_name)

    # Read and validate size
    contents = await file.read()
    max_size = settings.max_file_size_mb * 1024 * 1024
    if len(contents) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_file_size_mb}MB"
        )

    # Write file
    with open(target_path, "wb") as f:
        f.write(contents)

    return {
        "filename": safe_name,
        "path": target_path,
        "size": len(contents),
        "task_id": task_id,
        "subfolder": safe_subfolder,
    }
