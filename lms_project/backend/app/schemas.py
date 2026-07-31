from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["student", "instructor", "admin"]


# ---------------------------------------------------------------------------
# Auth / students
# ---------------------------------------------------------------------------


class StudentRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class StudentResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


# ---------------------------------------------------------------------------
# Courses / lessons
# ---------------------------------------------------------------------------


class CourseCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10, max_length=2000)
    max_seats: int = Field(gt=0, le=10000)
    instructor_id: str | None = None
    # Only used/required when an admin creates the course; an instructor is
    # always the owner of a course they create, regardless of this field.


class CourseSummary(BaseModel):
    id: str
    title: str
    description: str
    instructor_id: str
    instructor_name: str
    max_seats: int
    seats_available: int


class LessonCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    content: str = Field(min_length=1, max_length=5000)


class LessonResponse(BaseModel):
    id: str
    title: str
    content: str


class CourseDetailResponse(CourseSummary):
    lessons: list[LessonResponse]


class EnrollResponse(BaseModel):
    message: str
    course_id: str
    student_id: str


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    id: str
    action: str
    actor_email: EmailStr
    target: str
    timestamp: datetime
