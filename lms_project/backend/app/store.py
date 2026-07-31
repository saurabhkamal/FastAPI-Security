import uuid

from app import config
from app.security import hash_password

# ---------------------------------------------------------------------------
# In-memory "database"
# ---------------------------------------------------------------------------

USERS: dict[str, dict] = {}
# user_id -> {id, name, email, password_hash, role}

USERS_BY_EMAIL: dict[str, str] = {}
# email -> user_id, for O(1) uniqueness/login lookups

COURSES: dict[str, dict] = {}
# course_id -> {id, title, description, instructor_id, max_seats, enrolled_student_ids}

COURSE_TITLES: set[str] = set()
# lowercased titles, for uniqueness checks

LESSONS: dict[str, list[dict]] = {}
# course_id -> [{id, title, content}]

AUDIT_LOGS: list[dict] = []
# [{id, action, actor_email, target, timestamp}]


def reset_store() -> None:
    """Clears all in-memory data and re-seeds admin/instructor accounts. Used by tests."""
    USERS.clear()
    USERS_BY_EMAIL.clear()
    COURSES.clear()
    COURSE_TITLES.clear()
    LESSONS.clear()
    AUDIT_LOGS.clear()
    seed_data()


def _create_user(name: str, email: str, password: str, role: str) -> dict:
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "name": name,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
    }
    USERS[user_id] = user
    USERS_BY_EMAIL[email.lower()] = user_id
    return user


def seed_data() -> None:
    _create_user("Admin", config.ADMIN_EMAIL, config.ADMIN_PASSWORD, "admin")
    _create_user("Instructor", config.INSTRUCTOR_EMAIL, config.INSTRUCTOR_PASSWORD, "instructor")
