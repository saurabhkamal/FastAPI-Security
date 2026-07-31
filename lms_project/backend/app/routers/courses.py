import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.audit import log_audit_event
from app.idempotency import get_cached_response, store_response
from app.schemas import (
    CourseCreateRequest,
    CourseDetailResponse,
    CourseSummary,
    EnrollResponse,
    LessonCreateRequest,
    LessonResponse,
)
from app.security import CurrentUser, get_current_user, require_api_key, require_role
from app.store import COURSE_TITLES, COURSES, LESSONS, USERS

router = APIRouter(prefix="/courses", tags=["courses"])


def _course_summary(course: dict) -> CourseSummary:
    instructor = USERS.get(course["instructor_id"])
    return CourseSummary(
        id=course["id"],
        title=course["title"],
        description=course["description"],
        instructor_id=course["instructor_id"],
        instructor_name=instructor["name"] if instructor else "Unknown",
        max_seats=course["max_seats"],
        seats_available=course["max_seats"] - len(course["enrolled_student_ids"]),
    )


def _get_course_or_404(course_id: str) -> dict:
    course = COURSES.get(course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.post(
    "",
    response_model=CourseSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_course(
    payload: CourseCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_role("instructor", "admin"))],
):
    if payload.title.strip().lower() in COURSE_TITLES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Course title already exists")

    if current_user.role == "instructor":
        instructor_id = current_user.user_id
    else:
        # admin must specify an existing instructor to own the course
        if not payload.instructor_id or USERS.get(payload.instructor_id, {}).get("role") != "instructor":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid instructor_id is required")
        instructor_id = payload.instructor_id

    course_id = str(uuid.uuid4())
    course = {
        "id": course_id,
        "title": payload.title,
        "description": payload.description,
        "instructor_id": instructor_id,
        "max_seats": payload.max_seats,
        "enrolled_student_ids": set(),
    }
    COURSES[course_id] = course
    COURSE_TITLES.add(payload.title.strip().lower())
    LESSONS[course_id] = []

    log_audit_event("course_created", current_user.email, target=course_id)

    return _course_summary(course)


@router.get("", response_model=list[CourseSummary])
def list_courses():
    return [_course_summary(course) for course in COURSES.values()]


@router.get("/{course_id}", response_model=CourseDetailResponse)
def get_course(course_id: str):
    course = _get_course_or_404(course_id)
    summary = _course_summary(course)
    lessons = [LessonResponse(**lesson) for lesson in LESSONS.get(course_id, [])]
    return CourseDetailResponse(**summary.model_dump(), lessons=lessons)


@router.post(
    "/{course_id}/enroll",
    response_model=EnrollResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def enroll_in_course(
    course_id: str,
    current_user: Annotated[CurrentUser, Depends(require_role("student"))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    scope = f"enroll:{course_id}"
    cached = get_cached_response(scope, idempotency_key, current_user.user_id)
    if cached is not None:
        return cached

    course = _get_course_or_404(course_id)

    if current_user.user_id in course["enrolled_student_ids"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already enrolled in this course")

    if len(course["enrolled_student_ids"]) >= course["max_seats"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Course is full")

    course["enrolled_student_ids"].add(current_user.user_id)

    result = EnrollResponse(message="Enrolled successfully", course_id=course_id, student_id=current_user.user_id)
    store_response(scope, idempotency_key, current_user.user_id, result)
    return result


@router.post(
    "/{course_id}/lessons",
    response_model=LessonResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_lesson(
    course_id: str,
    payload: LessonCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_role("instructor"))],
):
    course = _get_course_or_404(course_id)

    if course["instructor_id"] != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    lesson = {"id": str(uuid.uuid4()), "title": payload.title, "content": payload.content}
    LESSONS[course_id].append(lesson)

    return LessonResponse(**lesson)


@router.delete("/{course_id}", dependencies=[Depends(require_api_key)])
def delete_course(
    course_id: str,
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
):
    course = _get_course_or_404(course_id)

    del COURSES[course_id]
    COURSE_TITLES.discard(course["title"].strip().lower())
    LESSONS.pop(course_id, None)

    log_audit_event("course_deleted", current_user.email, target=course_id)

    return {"message": "Course deleted", "course_id": course_id}
