import os
from werkzeug.utils import secure_filename
from flask import current_app

# Allowed extensions
ALLOWED_IMAGE_EXT = ["jpg", "jpeg", "png"]
ALLOWED_DOC_EXT = ["pdf"]

def allowed_file(filename, allowed_ext):
    """Check if the uploaded file has a valid extension."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_ext

def save_user_file(file, user, prefix, allowed_ext):
    """
    Save uploaded file to user's folder.
    - file: FileStorage object from request.files
    - user: SQLAlchemy User object
    - prefix: prefix for file name (profile_pic, cnic_front, resume, etc.)
    - allowed_ext: list of allowed extensions
    Returns relative path to file.
    """
    if not file or file.filename == "":
        raise ValueError("No file selected for upload.")

    if not allowed_file(file.filename, allowed_ext):
        raise ValueError(f"Invalid file type. Allowed types: {', '.join(allowed_ext)}")

    # Ensure user folder exists
    user_folder = os.path.join(current_app.root_path, "static", "uploads", f"user_{user.id}")
    os.makedirs(user_folder, exist_ok=True)

    # Secure filename
    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    filename = f"{prefix}{ext.lower()}"
    file_path = os.path.join(user_folder, filename)

    # Save file
    file.save(file_path)

    # Return relative path for database
    rel_path = os.path.relpath(file_path, current_app.root_path)
    return rel_path.replace("\\", "/")  # handle Windows paths

def remove_user_file(file_path):
    """
    Remove a file from the filesystem.
    file_path: relative path stored in DB (e.g., 'static/uploads/user_1/profile_pic.jpg')
    """
    if not file_path:
        return
    abs_path = os.path.join(current_app.root_path, file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
