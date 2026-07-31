# LMS — Learning Management System

A small multi-role Learning Management System: **FastAPI** backend (in-memory
storage, JWT + API-key auth, RBAC, rate limiting, exact CORS) and a **Next.js**
frontend (App Router, TypeScript, Tailwind).

This lives inside `fastapi_security/lms_project/` but is a separate,
standalone app from `fastapi_security/realworld_security.py` — it reuses that
file's conventions (in-memory "DB", `.env`-based secrets, `slowapi` rate
limiting, generic error messages) but has its own venv, dependencies, and
frontend.

## Structure

```
lms_project/
  backend/     FastAPI app (Python)
  frontend/    Next.js app (TypeScript)
```

## Roles

- **student** — registers via the UI/API, browses courses, enrolls, views own enrollments
- **instructor** — seeded account, creates courses, adds lessons to owned courses
- **admin** — seeded account, deletes any course, views the audit log

Seed accounts (set in `backend/.env`, change before any real deployment):

| Role       | Email                | Password             |
|------------|-----------------------|-----------------------|
| admin      | admin@lms.com         | AdminPass123!         |
| instructor | instructor@lms.com    | InstructorPass123!    |

Students self-register — there is no seed student account.

## Running the backend

```bash
cd backend
python -m venv venv

# activate the venv - the command depends on your shell:
source venv/Scripts/activate    # Git Bash / MINGW64 on Windows (must use "source", not ./)
venv\Scripts\activate.bat       # Windows cmd.exe
venv\Scripts\Activate.ps1       # Windows PowerShell
source venv/bin/activate        # macOS / Linux

pip install -r requirements.txt

cp .env.example .env           # then edit .env with your own secrets
uvicorn app.main:app --reload --port 8000
```

> Editing `.env` after the server has started requires a manual restart
> (Ctrl+C, then re-run `uvicorn ...`) — `--reload` watches Python source
> files, not `.env`, so config changes aren't picked up automatically.
>
> If you ever move this folder to a different path, delete and recreate
> `venv/` (`rm -rf venv && python -m venv venv && pip install -r
> requirements.txt`) — the `activate` script and the `.exe` launchers under
> `venv/Scripts/` have the old absolute path baked in and silently break
> ("command not found") after a move.

Run the test suite (covers all 15 scenarios below):

```bash
pytest -v
```

## Running the frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_KEY must match backend's API_KEY
npm run dev
```

By default this tries `http://localhost:3000`. If that port is busy (e.g.
Docker Desktop on Windows often squats on it), Next.js **silently picks the
next free port** (3001, 3002, ...) and prints the actual URL in the terminal
- check that output rather than assuming 3000. Whatever port it lands on,
that exact origin must be added to `CORS_ORIGINS` in `backend/.env`
(comma-separated) or every API call from the browser will fail with a CORS
error (which the frontend reports as "Could not reach the API server"):

```bash
# terminal says "- Local: http://localhost:3002" -> add that to backend/.env:
CORS_ORIGINS=http://localhost:3000,http://localhost:3002

# then restart the backend (Ctrl+C, re-run uvicorn) so it picks up the change
```

To pin a specific port instead of letting Next.js choose: `npm run dev --
--port 3100`.

> **Note on `NEXT_PUBLIC_API_KEY`**: any `NEXT_PUBLIC_*` variable is bundled
> into client-side JS and visible in the browser. That's an accepted
> simplification for this demo/assignment; a production app would proxy
> API-key-bearing requests through a Next.js server route instead.

## Security requirements → where they live

| Requirement | Implementation |
|---|---|
| API-key auth | `X-API-Key` header, checked in `app/security.py::require_api_key`, on every private endpoint |
| Token-based auth + RBAC | JWT bearer tokens (`app/security.py`), `require_role(*roles)` dependency |
| Rate limiting | `slowapi` in `app/limiter.py`; 5/min on `/auth/login` and `/students/register` |
| Exact CORS origins | `CORS_ORIGINS` env var → `CORSMiddleware(allow_origins=[...])` in `app/main.py` (never `"*"`) |
| Pydantic validation | `app/schemas.py` — `EmailStr`, `Field` length/range constraints, `Literal` roles |
| Environment variables | `app/config.py` reads everything via `os.getenv`; `.env` is gitignored, `.env.example` is committed |
| Safe global exception handling | catch-all `Exception` handler in `app/main.py` returns a generic message, logs server-side only |
| Custom 404/401/403/409/429 | dedicated exception handlers in `app/main.py`, consistent `{"error", "detail"}` body |
| Public vs private endpoints | only `GET /courses` and `GET /courses/{id}` skip auth entirely |
| Duplicate request prevention | optional `Idempotency-Key` header, `app/idempotency.py` |
| No secrets in source | all secrets loaded from `.env`, never hardcoded |
| No stack traces to users | enforced by the global exception handler |

## Manual test walkthrough (curl)

Set once:

```bash
API=http://localhost:8000
KEY=<value of API_KEY in backend/.env>
```

**1. Successful student registration**
```bash
curl -s -X POST $API/students/register -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name":"Alice","email":"alice@example.com","password":"StrongPass123"}'
# -> 201
```

**2. Invalid email rejection**
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST $API/students/register -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name":"Bad","email":"not-an-email","password":"StrongPass123"}'
# -> 422
```

**3. Duplicate email rejection** — run request #1 again -> 409

**4. Successful login**
```bash
curl -s -X POST $API/auth/login -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"StrongPass123"}'
# -> 200, {access_token, token_type, role}
```

**5. Invalid login rejection**
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST $API/auth/login -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"wrong"}'
# -> 401
```

**6. Rate-limit rejection** — fire the login request 6 times in a row; the
6th returns 429 (limit is 5/minute).

**7. Student attempting an admin action**
```bash
STOKEN=<student access_token from #4>
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE $API/courses/some-course-id \
  -H "X-API-Key: $KEY" -H "Authorization: Bearer $STOKEN"
# -> 403
```

**8. Instructor creating a course**
```bash
ITOKEN=$(curl -s -X POST $API/auth/login -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"email":"instructor@lms.com","password":"InstructorPass123!"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -X POST $API/courses -H "X-API-Key: $KEY" -H "Authorization: Bearer $ITOKEN" -H "Content-Type: application/json" \
  -d '{"title":"FastAPI Fundamentals","description":"Build secure APIs.","max_seats":1}'
# -> 201
```

**9. Student enrolling in a course**
```bash
curl -s -X POST $API/courses/<course_id>/enroll -H "X-API-Key: $KEY" -H "Authorization: Bearer $STOKEN"
# -> 201
```

**10. Duplicate enrollment rejection** — repeat #9 -> 409

**11. Course seat limit rejection** — with `max_seats: 1`, enroll a second
student in the same course -> 409 "Course is full"

**12. Safe error handling**
```bash
curl -s -X POST $API/students/register -H "X-API-Key: $KEY" --data-raw 'not-json'
# -> 400/422 with a generic JSON body, no traceback
```

**13. Invalid API-key rejection**
```bash
curl -s -o /dev/null -w "%{http_code}\n" $API/students/x/courses -H "X-API-Key: wrong-key"
# -> 401
```

**14. CORS configuration**
```bash
curl -s -i -X OPTIONS $API/courses -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: GET" \
  | grep -i access-control-allow-origin
# -> only echoes an origin that's in CORS_ORIGINS; unlisted origins get no such header
```

**15. Secret loading from .env** — stop the server, remove `API_KEY` from
`.env`, restart: the app fails fast with `RuntimeError: Missing required
environment variable: API_KEY`, proving nothing is hardcoded.

The same 15 scenarios are encoded as automated tests in
`backend/tests/test_lms.py` — run `pytest -v` for a one-shot pass/fail report.
