import os
from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


API_KEY = _required("API_KEY")

JWT_SECRET = _required("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

CORS_ORIGINS = [origin.strip() for origin in _required("CORS_ORIGINS").split(",") if origin.strip()]

ADMIN_EMAIL = _required("ADMIN_EMAIL")
ADMIN_PASSWORD = _required("ADMIN_PASSWORD")

INSTRUCTOR_EMAIL = _required("INSTRUCTOR_EMAIL")
INSTRUCTOR_PASSWORD = _required("INSTRUCTOR_PASSWORD")
