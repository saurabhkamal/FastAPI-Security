# FastAPI Security

Two things live in this repo:

## `realworld_security.py`

A single-file collection of 19 small FastAPI security exercises, each modeling
a realistic scenario (student registration, banking transfers, exam
submissions, file uploads, coupon management, webhooks, audit logging, etc.).
Every section is self-contained and demonstrates one or more security
practices in isolation — API-key/role-based auth, Pydantic validation,
rate limiting with `slowapi`, safe error messages, CORS configuration,
duplicate-request prevention, and more — using an in-memory "database" and
secrets loaded from `.env`.

Run it with:
```bash
pip install -r requirements.txt
uvicorn realworld_security:app --reload
```

## `lms_project/`

A complete, standalone Learning Management System that applies those same
security practices together in one coherent multi-role app, instead of 19
unrelated toy endpoints. It has a FastAPI backend (JWT + API-key auth,
role-based access for students/instructors/admins, rate limiting, exact CORS,
audit logging, idempotent requests) and a Next.js frontend.

See [`lms_project/README.md`](lms_project/README.md) for setup instructions,
architecture, and a full test walkthrough.
