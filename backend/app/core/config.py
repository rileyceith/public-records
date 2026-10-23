from pathlib import Path
import os


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = APP_DIR.parent
DATA_DIR = Path(os.environ.get("RECORDS_DATA_DIR", PROJECT_DIR / "data")).resolve()
UPLOAD_DIR = Path(os.environ.get("RECORDS_UPLOAD_DIR", DATA_DIR / "attachments")).resolve()
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{(DATA_DIR / 'records.db').as_posix()}",
)
ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
)
SESSION_TTL_SECONDS = 8 * 60 * 60
ID_HASH_KEY = os.environ.get("ID_HASH_KEY", "development-only-change-me")
PUBLIC_MODE = os.environ.get("PUBLIC_MODE", "").lower() in {"1", "true", "yes"}
STATIC_DIR = os.environ.get("STATIC_DIR", "")
if PUBLIC_MODE and (ID_HASH_KEY == "development-only-change-me" or len(ID_HASH_KEY) < 32):
    raise RuntimeError("PUBLIC_MODE requires ID_HASH_KEY to be set to a random secret of at least 32 characters.")
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_TYPES = {
    ".csv": "text/csv",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".txt": "text/plain",
}
