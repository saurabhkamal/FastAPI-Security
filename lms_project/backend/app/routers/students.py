import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.idempotency import get_cached_response, store_response
from app.limiter import limiter
from app.schemas import CourseSummary, StudentRegisterRequest, StudentResponse
from app.security import CurrentUser, get_current_user, hash_password, require_api_key
from app.store import COURSES, USERS, USERS_BY_EMAIL

router = APIRouter(tags=["students"])


@router.post(
    "/students/register",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
@limiter.limit("5/minute")
def register_student(
    request: Request,
    payload: StudentRegisterRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    email = payload.email.lower()

    cached = get_cached_response("register", idempotency_key, email)
    if cached is not None:
        return cached

    if email in USERS_BY_EMAIL:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "name": payload.name,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "role": "student",
    }
    USERS[user_id] = user
    USERS_BY_EMAIL[email] = user_id

    result = StudentResponse(id=user_id, name=user["name"], email=user["email"], role="student")
    store_response("register", idempotency_key, email, result)
    return result


@router.get(
    "/students/{student_id}/courses",
    response_model=list[CourseSummary],
    dependencies=[Depends(require_api_key)],
)
def get_student_courses(
    student_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current_user.role == "instructor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if current_user.role == "student" and current_user.user_id != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if student_id not in USERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    summaries = []
    for course in COURSES.values():
        if student_id in course["enrolled_student_ids"]:
            instructor = USERS.get(course["instructor_id"])
            summaries.append(
                CourseSummary(
                    id=course["id"],
                    title=course["title"],
                    description=course["description"],
                    instructor_id=course["instructor_id"],
                    instructor_name=instructor["name"] if instructor else "Unknown",
                    max_seats=course["max_seats"],
                    seats_available=course["max_seats"] - len(course["enrolled_student_ids"]),
                )
            )
    return summaries
