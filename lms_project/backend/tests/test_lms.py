from pathlib import Path

from app import config
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    API_KEY,
    INSTRUCTOR_EMAIL,
    INSTRUCTOR_PASSWORD,
    api_headers,
    auth_headers,
    login,
    register_student,
)


# 1. Successful student registration
def test_student_registration_success(client):
    resp = register_student(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "student"
    assert "password" not in body


# 2. Invalid email rejection
def test_invalid_email_rejected(client):
    resp = client.post(
        "/students/register",
        headers=api_headers(),
        json={"name": "Bad Email", "email": "not-an-email", "password": "StrongPass123"},
    )
    assert resp.status_code == 422


# 3. Duplicate email rejection
def test_duplicate_email_rejected(client):
    first = register_student(client)
    assert first.status_code == 201
    second = register_student(client)
    assert second.status_code == 409


# 4. Successful login
def test_login_success(client):
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert token


# 5. Invalid login rejection
def test_login_invalid_credentials(client):
    resp = client.post(
        "/auth/login",
        headers=api_headers(),
        json={"email": ADMIN_EMAIL, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


# 6. Rate-limit rejection
def test_rate_limit_rejection(client):
    last_status = None
    for _ in range(6):
        resp = client.post(
            "/auth/login",
            headers=api_headers(),
            json={"email": ADMIN_EMAIL, "password": "wrong-password"},
        )
        last_status = resp.status_code
    assert last_status == 429


# 7. Student attempting an admin action
def test_student_cannot_do_admin_action(client):
    register_student(client)
    student_token = login(client, "alice@example.com", "StrongPass123")

    instructor_token = login(client, INSTRUCTOR_EMAIL, INSTRUCTOR_PASSWORD)
    course = client.post(
        "/courses",
        headers=auth_headers(instructor_token),
        json={"title": "Intro to Testing", "description": "Learn to write great tests.", "max_seats": 2},
    ).json()

    resp = client.delete(f"/courses/{course['id']}", headers=auth_headers(student_token))
    assert resp.status_code == 403


# 8. Instructor creating a course
def test_instructor_creates_course(client):
    instructor_token = login(client, INSTRUCTOR_EMAIL, INSTRUCTOR_PASSWORD)
    resp = client.post(
        "/courses",
        headers=auth_headers(instructor_token),
        json={"title": "FastAPI Fundamentals", "description": "Build secure APIs with FastAPI.", "max_seats": 1},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "FastAPI Fundamentals"
    assert body["seats_available"] == 1


# 9. Student enrolling in a course
def test_student_enrolls_in_course(client):
    instructor_token = login(client, INSTRUCTOR_EMAIL, INSTRUCTOR_PASSWORD)
    course = client.post(
        "/courses",
        headers=auth_headers(instructor_token),
        json={"title": "Data Structures 101", "description": "Arrays, lists, trees, and graphs.", "max_seats": 2},
    ).json()

    register_student(client)
    student_token = login(client, "alice@example.com", "StrongPass123")

    resp = client.post(f"/courses/{course['id']}/enroll", headers=auth_headers(student_token))
    assert resp.status_code == 201
    assert resp.json()["course_id"] == course["id"]


# 10. Duplicate enrollment rejection
def test_duplicate_enrollment_rejected(client):
    instructor_token = login(client, INSTRUCTOR_EMAIL, INSTRUCTOR_PASSWORD)
    course = client.post(
        "/courses",
        headers=auth_headers(instructor_token),
        json={"title": "Algorithms 101", "description": "Sorting, searching, and complexity.", "max_seats": 2},
    ).json()

    register_student(client)
    student_token = login(client, "alice@example.com", "StrongPass123")

    first = client.post(f"/courses/{course['id']}/enroll", headers=auth_headers(student_token))
    assert first.status_code == 201
    second = client.post(f"/courses/{course['id']}/enroll", headers=auth_headers(student_token))
    assert second.status_code == 409


# 11. Course seat limit rejection
def test_course_seat_limit_rejected(client):
    instructor_token = login(client, INSTRUCTOR_EMAIL, INSTRUCTOR_PASSWORD)
    course = client.post(
        "/courses",
        headers=auth_headers(instructor_token),
        json={"title": "Limited Seats Course", "description": "Only one seat available here.", "max_seats": 1},
    ).json()

    register_student(client, name="Alice", email="alice@example.com")
    register_student(client, name="Bob", email="bob@example.com")

    alice_token = login(client, "alice@example.com", "StrongPass123")
    bob_token = login(client, "bob@example.com", "StrongPass123")

    first = client.post(f"/courses/{course['id']}/enroll", headers=auth_headers(alice_token))
    assert first.status_code == 201

    second = client.post(f"/courses/{course['id']}/enroll", headers=auth_headers(bob_token))
    assert second.status_code == 409
    assert second.json()["detail"] == "Course is full"


# 12. Safe error handling
def test_safe_error_handling(client):
    # A totally malformed body should never surface a stack trace to the caller.
    resp = client.post("/students/register", headers=api_headers(), content=b"not-json-at-all")
    assert resp.status_code in (400, 422)
    assert "Traceback" not in resp.text
    assert "File \"" not in resp.text


# 13. Invalid API-key rejection
def test_invalid_api_key_rejected(client):
    resp = client.get("/students/does-not-matter/courses", headers={"X-API-Key": "totally-wrong-key"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"


# 14. CORS configuration
def test_cors_configuration(client):
    resp = client.options(
        "/courses",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"

    blocked = client.options(
        "/courses",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in blocked.headers.keys()}


# 15. Secret loading from .env
def test_secret_loading_from_env():
    assert config.API_KEY == API_KEY
    assert config.API_KEY != "change-me-api-key"
    assert config.JWT_SECRET
    config_source = (Path(__file__).resolve().parents[1] / "app" / "config.py").read_text()
    assert "change-me" not in config_source
    assert API_KEY not in config_source
