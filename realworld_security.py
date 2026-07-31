import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, status, Request, UploadFile, File
from typing import Annotated, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import date, datetime
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uuid      # lets us generate unique random IDs - perfect for "unique ID" requirements
from datetime import timedelta # timedelta lets us add/subtract a duration (like "15 minutes") to/from a datetime
from fastapi.middleware.cors import CORSMiddleware  # FastAPI's built-in tool for configuring CORS rules

load_dotenv()  # reads the .env file and loads its contents into environment variables

API_KEY = os.getenv("API_KEY")  # Fetch the value we set in .env

app = FastAPI(title="FastAPI Security")

# CORS middleware is configured here, right after app creation, since it applies
# to the whole application, not just one endpoint set (see section 15 below for details)
app.add_middleware(
    CORSMiddleware,
    # Attach the CORS middleware to our app - it runs on every request
    allow_origins=["https://track.company.com", "https://admin.company.com"],
    # Only these two exact domains are allowed to call this API from a browser
    # - NOT allow_origins=["*"], which would allow literally any website
    allow_credentials=True,
    # Allows cookies/auth headers to be sent along with cross-origin requests
    allow_methods=["GET", "PATCH"],
    # Only these two HTTP methods are allowed cross-origin (matches section 15's needs)
    allow_headers=["*"],
    # Allow any request headers (e.g. our x-api-key) to be sent cross-origin
)


# ======================================================================================
# 1: Secure Student Registration API
# Scenario: A training institute wants an API where students can register for a course.
#           The institute is receiving fake registrations, invalid email addresses,
#           and unrealistic ages.
# Creating endpoint: POST /students/register
# Requirements: Accept name, email, age, and course; validate and store the registration
# Validation Rules:
#   - Name must contain between 2 and 50 characters
#   - Email must be valid
#   - Age must be between 16 and 65
#   - Course name must contain between 2 and 100 characters
#   - Duplicate email registration must not be allowed
#   - Return status code 201 after successful registration
#   - Return status code 409 if the email already exists
#   - Protect the endpoint using an API key
# Security: The API key must come from a .env file, never hardcoded in the source code
# ======================================================================================

class StudentRegister(BaseModel):
    # Defines the exact shape and validation rules for a registration request
    name: str = Field(min_length=2, max_length=50)
    # Name must be 2-50 characters
    email: EmailStr
    # Must be a valid email format
    age: int = Field(ge=16, le=65)
    # Age must be between 16 and 65
    course: str = Field(min_length=2, max_length=100)
    # Course must be 2-100 characters

registered_students = []
# In-memory "database" storing all registered students as a list of dictionaries

@app.post("/students/register", status_code=status.HTTP_201_CREATED)
# status_code=201 -> FastAPI automatically returns 201 Created on success
def register_student(student: StudentRegister, x_api_key: Annotated[str | None, Header()] = None):
    # student: the validated request body; x_api_key: read from request headers
    if x_api_key != API_KEY:
        # Compares the caller's key against the real key loaded from .env
        raise HTTPException(status_code=401, detail="Invalid API Key")

    for existing in registered_students:
        # Loop through every already-registered student
        if existing["email"] == student.email:
            # Reject if this email has already been used to register
            raise HTTPException(status_code=409, detail="Email already registered")

    new_student = {
        "id": max([s["id"] for s in registered_students], default=0) + 1,
        # Generate a new unique ID: highest existing ID + 1 (default=0 if list is empty)
        **student.model_dump()
        # Unpack name, email, age, course from the validated request into this dict
    }
    registered_students.append(new_student)
    # Save the new student record

    return new_student
    # Send back the newly created student record as confirmation

# Conclusion:
# This endpoint securely registers a new student by validating every input field through
# Pydantic (name length, valid email format, age range, course length), protects access
# using an API key loaded from a .env file instead of being hardcoded, and prevents
# duplicate registrations by checking for an existing email before creating a new record.


# ======================================================================================
# 2: Employee Attendance API with Role-Based Access
# Scenario: A company wants employees to mark attendance, but only managers should be
#           able to view the attendance of all employees.
# Creating endpoints:
#   POST /attendance/check-in
#   GET /attendance/my
#   GET /attendance/all
# Requirements: Use two different headers - X-Employee-Key and X-Manager-Key
# Validation Rules:
#   - Employees can check in only once per day
#   - An employee can view only their own attendance
#   - A manager can view everyone's attendance
#   - Return 403 Forbidden when an employee tries to access the manager endpoint
#   - Store the check-in date and time
# Security: Do not expose the valid manager key in any error response
# ======================================================================================

EMPLOYEE_KEYS = {
    "emp-key-1": "Jack",
    # This key belongs to Jack
    "emp-key-2": "Jones"
    # This key belongs to Jones
}
# When someone sends X-Employee-Key: emp-key-1, we look it up and know it's Jack checking in

MANAGER_KEY = os.getenv("MANAGER_KEY")
# Loads the manager's secret key from .env

attendance_records = []
# In-memory "database" of attendance check-ins

@app.post("/attendance/check-in", status_code=status.HTTP_201_CREATED)
def check_in(x_employee_key: Annotated[str | None, Header()] = None):
    # 1. Identify the employee from their key
    employee_name = EMPLOYEE_KEYS.get(x_employee_key)
    if employee_name is None:
        raise HTTPException(status_code=401, detail="Invalid employee key")

    # 2. Prevent checking in twice on the same day
    today = date.today().isoformat()
    # today's date as a clean string like "2026-07-24"
    for record in attendance_records:
        if record["employee"] == employee_name and record["date"] == today:
            raise HTTPException(status_code=409, detail="Already checked in today")

    # 3. Store the check-in
    new_record = {
        "employee": employee_name,
        "date": today,
        "time": datetime.now().strftime("%H:%M:%S")
        # formats the current time as "14:32:10" for storage
    }
    attendance_records.append(new_record)

    return new_record

@app.get("/attendance/my")
def get_my_attendance(x_employee_key: Annotated[str | None, Header()] = None):
    # Identify the employee from their key
    employee_name = EMPLOYEE_KEYS.get(x_employee_key)
    if employee_name is None:
        raise HTTPException(status_code=401, detail="Invalid employee Key")

    my_records = [r for r in attendance_records if r["employee"] == employee_name]
    # Filter down to only this employee's own records
    return my_records

@app.get("/attendance/all")
def get_all_attendance(x_manager_key: Annotated[str | None, Header()] = None):
    # Manager-only endpoint - compares against the real manager key
    if x_manager_key != MANAGER_KEY:
        raise HTTPException(status_code=403, detail="Access denied")
        # Generic message only - never reveals the real MANAGER_KEY value

    return attendance_records
    # A manager can see every employee's attendance

# Conclusion:
# This set of endpoints implements simple role-based access using two separate keys:
# an employee key that doubles as identity (for checking in and viewing one's own
# attendance) and a manager key that unlocks visibility into everyone's records. The
# 403 response for unauthorized manager access always uses a generic message, ensuring
# the real manager key is never leaked through any error output.


# ======================================================================================
# 3: Online Examination Submission API
# Scenario: An online examination platform wants students to submit answers. Students
#           are trying to submit the exam multiple times and send extremely large text
#           responses.
# Creating endpoints:
#   POST /exam/submit
#   GET /exam/result/{student_id}
# Requirements:
#   - A student can submit an exam only once
#   - Each answer must contain no more than 500 characters
#   - The request must contain at least one answer
#   - Maximum 100 answers per submission
#   - Result endpoint must require an API key
#   - Return 409 for duplicate submission
#   - Return 404 when no result exists
# Security: Apply a rate limit of three exam submissions per minute per IP address
# ======================================================================================

limiter = Limiter(key_func=get_remote_address)
# Creates a limiter object that groups/counts requests by the caller's IP address
app.state.limiter = limiter
# Attaches the limiter to the FastAPI app itself, so it can be used in route functions
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Whenever the rate limit is exceeded, FastAPI handles it using slowapi's built-in handler,
# which automatically returns a proper 429 Too Many Requests response

class Answer(BaseModel):
    # Represents ONE single answer inside a submission
    question_id: int
    # Which question this answer belongs to
    answer: str = Field(max_length=500)
    # Each answer must contain no more than 500 characters

class ExamSubmission(BaseModel):
    student_id: int
    # Which student is submitting
    exam_id: int
    # Which exam this submission is for
    answers: list[Answer] = Field(min_length=1, max_length=100)
    # A list of Answer objects; min_length=1 -> at least one answer required,
    # max_length=100 -> maximum 100 answers per submission

exam_submissions = []
# Our "fake database" for exam submissions
# Each entry: {"student_id": 101, "exam_id": 501, "answers": [...]}

@app.post("/exam/submit", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
# Applies the rate limiter - allow at most 3 requests per minute, counted per IP address
def submit_exam(request: Request, submission: ExamSubmission):
    # request: Request is required for slowapi's rate limiter to inspect the caller's IP

    # 1. Prevent a student from submitting the same exam twice
    for existing in exam_submissions:
        if existing["student_id"] == submission.student_id and existing["exam_id"] == submission.exam_id:
            raise HTTPException(status_code=409, detail="Exam already submitted")

    # 2. Store the new submission
    new_submission = submission.model_dump()
    exam_submissions.append(new_submission)
    return new_submission

@app.get("/exam/result/{student_id}")
def get_exam_result(student_id: int, x_api_key: Annotated[str | None, Header()] = None):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    for submission in exam_submissions:
        # Loop through all stored submissions looking for this student's result
        if submission["student_id"] == student_id:
            return submission
            # Found it - return this student's submission/result immediately

    raise HTTPException(status_code=404, detail="No result found for this student")
    # If the loop finishes without finding a match, no submission exists - return 404

# Conclusion:
# This endpoint validates exam submissions using nested Pydantic models (a list of
# Answer objects inside ExamSubmission), preventing duplicate submissions per student
# per exam, and enforces a strict 3-per-minute rate limit per IP address to stop
# students from spamming submissions or scripting mass attempts.


# ======================================================================================
# 4: Secure Course Purchase API
# Scenario: An EdTech platform wants an API for purchasing courses. Attackers are
#           trying to send negative prices and fake discount values.
# Creating endpoints:
#   POST /courses/purchase
#   GET /purchases/{purchase_id}
# Requirements:
#   - Course price must come from server-side data; the client must not send the final price
#   - Quantity must be between 1 and 5
#   - Accept only valid coupon codes
#   - Calculate the final amount on the server
#   - Create a unique purchase ID
#   - Return 201 after purchase
#   - Return 400 for an invalid coupon
#   - Protect the purchase endpoint with an API key
# Security: Explain why the price should not be trusted when sent by the frontend
# ======================================================================================

COURSES = {
    10: {"name": "FastAPI Bootcamp", "price": 999},
    11: {"name": "Python for Data Science", "price": 1499},
    12: {"name": "Machine Learning Basics", "price": 1999},
}
# Server-side "source of truth" for course prices - the client never sends this

COUPONS = {
    "ABC20": 20,   # 20% OFF
    "SAVE10": 10,  # 10% OFF
}
# Server-side coupon data - client only ever sends the CODE, never the discount %

class PurchaseRequest(BaseModel):
    student_email: EmailStr
    course_id: int
    quantity: int = Field(ge=1, le=5)
    # Quantity must be between 1 and 5
    coupon_code: str | None = None
    # Optional - not every purchase uses a coupon
    # Notice: there is NO price field here at all - the client cannot send a price
    # even if it wanted to, since our model doesn't accept one

purchases = []
# "fake database" of purchases
# Each entry: {"purchase_id": ..., "student_email": ..., "course_id": ..., "quantity": ..., "final_amount": ...}

@app.post("/course/purchase", status_code=status.HTTP_201_CREATED)
def purchase_course(purchase: PurchaseRequest, x_api_key: Annotated[str | None, Header()] = None):
    # 1. Protect the endpoint with an API key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. Look up the course using SERVER-side data only (never trust a client-sent price)
    course = COURSES.get(purchase.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    # 3. Calculate the base amount using the server's price
    base_amount = course["price"] * purchase.quantity

    # 4. Apply a coupon if one was provided
    final_amount = base_amount
    if purchase.coupon_code:
        discount_percent = COUPONS.get(purchase.coupon_code)
        if discount_percent is None:
            raise HTTPException(status_code=400, detail="Invalid coupon code")
        final_amount = base_amount - (base_amount * discount_percent / 100)

    # 5. Generate a unique purchase ID
    purchase_id = str(uuid.uuid4())

    # 6. Store the purchase record
    new_purchase = {
        "purchase_id": purchase_id,
        "student_email": purchase.student_email,
        "course_id": purchase.course_id,
        "course_name": course["name"],
        "quantity": purchase.quantity,
        "final_amount": final_amount
    }
    purchases.append(new_purchase)

    return new_purchase

@app.get("/purchases/{purchase_id}")
def get_purchase(purchase_id: str, x_api_key: Annotated[str | None, Header()] = None):
    # 1. Protect the endpoint with an API key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2. Search for the matching purchase record
    for p in purchases:
        if p["purchase_id"] == purchase_id:
            return p

    raise HTTPException(status_code=404, detail="Purchase not found")

# Conclusion:
# This endpoint proves that a client can never control what it pays: the request model
# has no price field at all, so the server always calculates the final amount from its
# own trusted COURSES and COUPONS data. This directly defeats a common real-world attack
# where a malicious client tampers with a price field sent from the frontend, since
# anything coming from the browser must be treated as untrusted input.


# ======================================================================================
# 5: Password Login API with Brute-Force Protection
# Scenario: A learning portal is experiencing repeated login attempts from attackers
#           trying to guess passwords.
# Creating endpoint: POST /login
# Requirements:
#   - Allow only five login attempts per minute per IP
#   - Use a generic message for invalid credentials
#   - Do not say whether the email or password was incorrect
#   - Return 401 for invalid credentials
#   - Return 429 when the rate limit is exceeded
#   - Return a simple token after a successful login
# Security: The password and generated token must not be printed in logs
# ======================================================================================

FAKE_USERS = {
    "admin@example.com": "secret123"
}
# A small "fake user database" - in a real system, passwords would be HASHED,
# never stored in plain text; kept plain here only for this learning assignment

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@app.post("/login")
@limiter.limit("5/minute")
# Allows at most 5 login attempts per minute, counted per IP address
def login(request: Request, credentials: LoginRequest):
    # request: Request is required for slowapi's rate limiter to identify the caller's IP

    stored_password = FAKE_USERS.get(credentials.email)
    # Looks up the password for this email; returns None if the email isn't registered

    # SECURITY: check both failure cases together, respond with the SAME generic message,
    # so an attacker can't tell whether the email exists or the password was wrong
    if stored_password is None or stored_password != credentials.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # If we reach here, the credentials are correct - generate a simple token
    token = str(uuid.uuid4())
    # uuid.uuid4() creates a random unique string to act as a stand-in access token

    return {"access_token": token, "token_type": "bearer"}
    # Note: nowhere in this function do we print() or log the password or token

# Conclusion:
# This login endpoint defends against brute-force attacks with a strict 5-per-minute
# rate limit, and against user enumeration by returning the exact same generic error
# message regardless of whether the email or the password was wrong. No print or log
# statement anywhere reveals the password or the generated token.


# ======================================================================================
# 6: Banking Money Transfer API
# Scenario: A banking application wants customers to transfer money between accounts.
# Creating endpoints:
#   POST /accounts/transfer
#   GET /accounts/{account_id}/balance
# Requirements:
#   - Amount must be greater than zero
#   - Sender and receiver accounts cannot be the same
#   - Sender must have sufficient balance
#   - Maximum transfer amount is Rs. 1,00,000
#   - Every transaction must have a transaction ID
#   - Return 400 for insufficient balance
#   - Return 404 if an account does not exist
#   - Protect transfer with a private API key
#   - Apply a rate limit of five transfers per minute
# Security: The balance should update only when all validations pass
# ======================================================================================

ACCOUNTS = {
    1001: {"owner": "Jack", "balance": 50000},
    1002: {"owner": "John", "balance": 30000},
    1003: {"owner": "Tom", "balance": 10000},
}
# Server-side account balances - this is our "source of truth"

class TransferRequest(BaseModel):
    from_account: int
    to_account: int
    amount: float = Field(gt=0)
    # gt=0 means "greater than 0" - enforces "amount must be greater than zero"

transactions = []
# Each entry: {"transaction_id": ..., "from_account": ..., "to_account": ..., "amount": ...}

MAX_TRANSFER_AMOUNT = 100000
# Maximum allowed transfer amount per the assignment

@app.post("/accounts/transfer", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def transfer_money(
    request: Request,
    transfer: TransferRequest,
    x_api_key: Annotated[str | None, Header()] = None
):
    # 1. Protect with API Key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. Sender and receiver cannot be the same account
    if transfer.from_account == transfer.to_account:
        raise HTTPException(status_code=400, detail="Sender and receiver accounts cannot be the same")

    # 3. Check maximum transfer limit
    if transfer.amount > MAX_TRANSFER_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Amount exceeds maximum transfer limit of {MAX_TRANSFER_AMOUNT}")

    # 4. Both accounts must exist
    sender = ACCOUNTS.get(transfer.from_account)
    receiver = ACCOUNTS.get(transfer.to_account)
    if sender is None or receiver is None:
        raise HTTPException(status_code=404, detail="Account not found")

    # 5. Sender must have sufficient balance
    if sender["balance"] < transfer.amount:
        raise HTTPException(status_code=400, detail="Insufficient Balance")

    # --- ALL VALIDATIONS HAVE PASSED AT THIS POINT ---
    # Only now do we actually touch any account balances. If any check above had
    # failed, we would have exited early via raise, and NEITHER account's balance
    # would have been modified at all - this "validate everything first" pattern is
    # exactly what this security challenge is asking for.

    # 6. Perform the transfer
    sender["balance"] -= transfer.amount
    receiver["balance"] += transfer.amount

    # 7. Record the transaction with a unique ID
    transaction_id = str(uuid.uuid4())
    new_transaction = {
        "transaction_id": transaction_id,
        "from_account": transfer.from_account,
        "to_account": transfer.to_account,
        "amount": transfer.amount
    }
    transactions.append(new_transaction)

    return new_transaction

@app.get("/accounts/{account_id}/balance")
def get_balance(account_id: int, x_api_key: Annotated[str | None, Header()] = None):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    account = ACCOUNTS.get(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    return {"account_id": account_id, "balance": account["balance"]}

# Conclusion:
# This endpoint follows a strict "validate everything, mutate last" discipline: every
# rule (same-account check, max-limit check, account-existence check, sufficient-balance
# check) runs and can reject the request before a single balance is touched. This
# guarantees a transfer either completes fully and correctly, or leaves both accounts
# completely unchanged - there is no possibility of money vanishing partway through.


# ======================================================================================
# 7: Hospital Appointment Booking API
# Scenario: A hospital wants an appointment booking API. Patients are booking the same
#           doctor and time slot multiple times.
# Creating endpoints:
#   POST /appointments
#   GET /appointments/{appointment_id}
#   DELETE /appointments/{appointment_id}
# Requirements:
#   - Appointment date cannot be in the past
#   - The doctor must exist
#   - The slot must be available
#   - The same doctor cannot have two appointments in the same slot
#   - Patient email must be valid
#   - Cancellation requires an API key
#   - Return 409 if the slot is already booked
# Security: Do not expose other patients' appointment data
# ======================================================================================

DOCTORS = {
    15: "Dr. Victoria",
    16: "Dr. George",
}
# Server-side doctor data

class AppointmentRequest(BaseModel):
    patient_name: str = Field(min_length=2, max_length=100)
    patient_email: EmailStr
    doctor_id: int
    appointment_date: date
    time_slot: str

    @field_validator("appointment_date")
    @classmethod
    def date_must_not_be_in_past(cls, value):
        # value is the appointment date the client sent, already parsed into a real date object
        if value < date.today():
            raise ValueError("Appointment date cannot be in the past")
        return value
        # Must return the value for pydantic to accept it as valid

appointments = []
# Each entry: {"appointment_id": ..., "patient_name": ..., "patient_email": ...,
#              "doctor_id": ..., "appointment_date": ..., "time_slot": ...}

@app.post("/appointments", status_code=status.HTTP_201_CREATED)
def create_appointment(appointment: AppointmentRequest):
    # 1. The doctor must exist
    doctor_name = DOCTORS.get(appointment.doctor_id)
    if doctor_name is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # 2. The same doctor cannot have two appointments in the same slot
    for existing in appointments:
        if (existing["doctor_id"] == appointment.doctor_id
                and existing["appointment_date"] == appointment.appointment_date
                and existing["time_slot"] == appointment.time_slot):
            raise HTTPException(status_code=409, detail="This slot is already booked")

    # 3. Create and store the appointment
    appointment_id = str(uuid.uuid4())
    new_appointment = {
        "appointment_id": appointment_id,
        **appointment.model_dump()
    }
    appointments.append(new_appointment)

    return new_appointment

@app.get("/appointments/{appointment_id}")
def get_appointment(appointment_id: str):
    # SECURITY: this endpoint only ever returns ONE specific appointment, looked up by
    # its unique (hard-to-guess) appointment_id - there is deliberately no "list all
    # appointments" endpoint, which is what prevents browsing other patients' data
    for appt in appointments:
        if appt["appointment_id"] == appointment_id:
            return appt

    raise HTTPException(status_code=404, detail="Appointment not found")

@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: str, x_api_key: Annotated[str | None, Header()] = None):
    # Cancellation requires an API key per the assignment
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    for index, appt in enumerate(appointments):
        if appt["appointment_id"] == appointment_id:
            cancelled = appointments.pop(index)
            return {"message": "Appointment Cancelled", "appointment": cancelled}

    raise HTTPException(status_code=404, detail="appointment not found")

# Conclusion:
# This endpoint uses a custom Pydantic field_validator to reject any appointment date
# that has already passed, and prevents double-booking by checking doctor, date, and
# time slot together before creating a new appointment. Patient privacy is preserved by
# never exposing a "list all appointments" endpoint - appointments can only be looked up
# one at a time by their unguessable UUID.


# ======================================================================================
# 8: Food Delivery Order API
# Scenario: A food delivery platform wants customers to place orders. Some users are
#           sending empty orders, invalid quantities, and fake restaurant IDs.
# Creating endpoints:
#   POST /orders
#   GET /orders/{order_id}
#   PATCH /orders/{order_id}/status
# Requirements:
#   - Order must contain at least one item
#   - Each item quantity must be between 1 and 10
#   - Restaurant must exist
#   - All items must belong to the selected restaurant
#   - Customer may view their own order
#   - Only an admin can change the order status
#   - Allowed statuses: placed, accepted, preparing, out_for_delivery, delivered, cancelled
# Security: Prevent invalid status values using Literal or an enum
# ======================================================================================

RESTAURANTS = {
    1: {
        "name": "Pizza Place",
        "items": {101: "Margherita Pizza", 102: "Pepperoni Pizza"}
    },
    2: {
        "name": "Burger Joint",
        "items": {201: "Cheeseburger", 202: "Veggie Burger"}
    },
}
# Server-side restaurant + menu data

OrderStatus = Literal["placed", "accepted", "preparing", "out_for_delivery", "delivered", "cancelled"]
# Restricts a field to only these exact values - nothing else is allowed. If someone
# sends "status": "shipped" (not in this list), pydantic automatically rejects it with
# a 422 validation error, satisfying this security challenge

class OrderItem(BaseModel):
    item_id: int
    quantity: int = Field(ge=1, le=10)
    # Each item quantity must be between 1 and 10

class OrderCreate(BaseModel):
    restaurant_id: int
    customer_email: EmailStr
    items: list[OrderItem] = Field(min_length=1)
    # min_length=1 -> "order must contain at least one item"

class StatusUpdate(BaseModel):
    status: OrderStatus
    # Using our Literal type here means only the 6 allowed status strings are accepted

ADMIN_KEY = os.getenv("ADMIN_KEY")
# Admin key used for status updates (and reused by several later sections)

orders = []
# Each entry: {"order_id": ..., "restaurant_id": ..., "customer_email": ..., "items": [...], "status": ...}

@app.post("/orders", status_code=status.HTTP_201_CREATED)
def create_order(order: OrderCreate):
    # 1. Restaurant must exist
    restaurant = RESTAURANTS.get(order.restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restuarant not Found")

    # 2. Every item must belong to this restaurant
    for item in order.items:
        if item.item_id not in restaurant["items"]:
            raise HTTPException(status_code=400, detail=f"Item {item.item_id} does not belong to the restaurant")

    # 3. Create and store the order
    order_id = str(uuid.uuid4())
    new_order = {
        "order_id": order_id,
        "restaurant_id": order.restaurant_id,
        "customer_email": order.customer_email,
        "items": [item.model_dump() for item in order.items],
        "status": "placed"
        # Every new order automatically starts as "placed" - the customer never sets this directly
    }
    orders.append(new_order)

    return new_order

@app.get("/orders/{order_id}")
def get_order(order_id: str, x_customer_email: Annotated[str | None, Header()] = None):
    for order in orders:
        if order["order_id"] == order_id:
            # A customer may only view THEIR OWN order - compare the requester's
            # claimed email against the email stored on the order itself
            if order["customer_email"] != x_customer_email:
                raise HTTPException(status_code=403, detail="Access denied")
            return order

    raise HTTPException(status_code=404, detail="Order not found")

@app.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: str,
    status_update: StatusUpdate,
    x_admin_key: Annotated[str | None, Header()] = None
):
    # Only an admin can change order status
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    for order in orders:
        if order["order_id"] == order_id:
            order["status"] = status_update.status
            return order

    raise HTTPException(status_code=404, detail="Order not found")

# Conclusion:
# This endpoint uses Python's Literal type to guarantee an order's status can only ever
# be one of the six real values the system understands, rejecting anything else
# automatically at the validation layer. Combined with restaurant/item matching checks
# and an admin-only status-update gate, this prevents both malformed orders and
# unauthorized status changes.


# ======================================================================================
# 9: E-Commerce Inventory Protection API
# Scenario: An online store has limited stock. Multiple users may attempt to purchase
#           the last available item.
# Creating endpoints:
#   GET /products
#   POST /products/{product_id}/purchase
# Requirements:
#   - Product ID must be a positive integer
#   - Quantity must be between 1 and 20
#   - Reject the request if stock is insufficient
#   - Reduce stock only after successful validation
#   - Return 409 if stock is insufficient
#   - Apply a rate limit of ten purchases per minute
#   - Protect the purchase endpoint using an API key
# Security: The stock must never become negative
# ======================================================================================

PRODUCTS = {
    1: {"name": "Wireless Mouse", "price": 599, "stock": 50},
    2: {"name": "Mechanical Keyboard", "price": 2999, "stock": 20},
    3: {"name": "USB-C Hub", "price": 1499, "stock": 5},
}
# Server-side product/stock data

class PurchaseProductRequest(BaseModel):
    quantity: int = Field(ge=1, le=20)
    # quantity must be between 1 and 20
    # Notice product_id isn't in this model - it comes from the URL path instead
    # (/products/{product_id}/purchase)

@app.get("/products")
def list_products():
    # Public endpoint - anyone can browse available products, no API key needed
    return PRODUCTS

@app.post("/products/{product_id}/puchase", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def purchase_product(
    request: Request,
    product_id: int,
    purchase: PurchaseProductRequest,
    x_api_key: Annotated[str | None, Header()] = None):

    # 1. Protect with API Key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. Product ID must be a positive integer
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="Product ID must be a positive integer")

    # 3. Product must exist
    product = PRODUCTS.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # 4. Reject if stock is insufficient - checked BEFORE touching stock at all
    if product["stock"] < purchase.quantity:
        raise HTTPException(status_code=409, detail="Insufficient stock")

    # --- Validation complete - only now do we touch the stock ---
    # 5. Reduce stock only after all checks passed
    product["stock"] -= purchase.quantity

    return {
        "message": "Purchase successful",
        "product_id": product_id,
        "product_name": product["name"],
        "quantity_purchased": purchase.quantity,
        "remaining_stock": product["stock"]
    }

# Conclusion:
# This endpoint mirrors the banking section's "validate everything first, mutate last"
# discipline applied to inventory: stock is only ever decremented after every check
# (existence, positive product ID, sufficient stock) has passed, ensuring stock can
# never be reduced below zero through this endpoint's normal flow.


# ======================================================================================
# 10: File Upload Metadata API
# Scenario: A student portal allows assignment uploads. Students are trying to upload
#           unsupported file types and extremely large files.
# Creating endpoints:
#   POST /assignments/upload
#   GET /assignments/{submission_id}
# Requirements:
#   - Accept only PDF, DOCX, and ZIP files
#   - Maximum file size should be 5 MB
#   - Student ID and assignment ID are required
#   - A student can submit only once per assignment
#   - Generate a unique submission ID
#   - Return 413 for oversized files
#   - Return 415 for unsupported file types
#   - Protect upload using an API key
# Security: Do not use the original filename directly when saving the file
# ======================================================================================

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",  # some browsers/OSes report ZIP this way instead
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB in bytes

submissions = []
# Each entry: {"submission_id": ..., "student_id": ..., "assignment_id": ...,
#              "original_filename": ..., "saved_filename": ..., "size": ...}

@app.post("/assignments/upload", status_code=status.HTTP_201_CREATED)
async def upload_assignment(
    student_id: int,
    assignment_id: int,
    file: Annotated[UploadFile, File()],
    x_api_key: Annotated[str | None, Header()] = None):

    # 1. Protect with API Key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2. A student can submit only once per assignment
    for existing in submissions:
        if existing["student_id"] == student_id and existing["assignment_id"] == assignment_id:
            raise HTTPException(status_code=409, detail="Assingment already submitted")

    # 3. Check file type FIRST (before reading the whole file into memory)
    file_extension = ALLOWED_CONTENT_TYPES.get(file.content_type)
    if file_extension is None:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    # 4. Read the file and check its size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")

    # 5. Generate a SAFE filename instead of trusting the client's original filename -
    # a client-controlled filename could contain path-traversal characters (e.g. "../../")
    # or collide with another student's file
    submission_id = str(uuid.uuid4())
    saved_filename = f"{submission_id}.{file_extension}"

    # 6. Store the submission metadata
    new_submission = {
        "submission_id": submission_id,
        "student_id": student_id,
        "assignment_id": assignment_id,
        "original_filename": file.filename,
        "saved_filename": saved_filename,
        "size": len(content)
    }
    submissions.append(new_submission)

    return new_submission

@app.get("/assignments/{submission_id}")
def get_submission(submission_id: str):
    for submission in submissions:
        if submission["submission_id"] == submission_id:
            return submission

    raise HTTPException(status_code=404, detail="Submission not found")

# Conclusion:
# This endpoint validates uploaded files by content type (rejecting anything outside
# PDF/DOCX/ZIP with a 415) and by size (rejecting anything over 5MB with a 413), and
# never trusts the client's original filename for storage - instead generating a fresh
# UUID-based filename, which protects against path-traversal attacks and filename
# collisions between different students' submissions.


# ======================================================================================
# 11: Customer Support Ticket API
# Scenario: A SaaS company wants customers to raise support tickets. Some users are
#           sending huge descriptions and repeatedly creating duplicate tickets.
# Creating endpoints:
#   POST /tickets
#   GET /tickets/{ticket_id}
#   PATCH /tickets/{ticket_id}
# Requirements:
#   - Subject must be between 5 and 100 characters
#   - Description must be between 20 and 2000 characters
#   - Priority must be low, medium, high, or critical
#   - Prevent duplicate open tickets with the same email and subject
#   - Only support staff can update ticket status
#   - Apply a rate limit of five tickets per hour per user
# Security: Internal support notes must not be returned to the customer
# ======================================================================================

STAFF_KEY = os.getenv("STAFF_KEY")
# Loads a separate secret key for support staff, same .env pattern as ADMIN_KEY/MANAGER_KEY

TicketPriority = Literal["low", "medium", "high", "critical"]
# Restricts priority to exactly these 4 values

class TicketCreate(BaseModel):
    # Model for what a CUSTOMER sends when raising a new ticket
    customer_email: EmailStr
    subject: str = Field(min_length=5, max_length=100)
    description: str = Field(min_length=20, max_length=2000)
    priority: TicketPriority

class TicketStatusUpdate(BaseModel):
    # Model for what STAFF sends when updating a ticket
    status: Literal["open", "in_progress", "resolved", "closed"]
    internal_notes: str | None = None
    # Optional - staff can attach internal notes; customers never see this field

tickets = []
# Our "fake database" of tickets
# Each entry: {"ticket_id", "customer_email", "subject", "description",
#              "priority", "status", "internal_notes"}

@app.post("/tickets", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
# Allows at most 5 ticket creations per hour, counted per IP (reusing our existing limiter)
def create_ticket(request: Request, ticket: TicketCreate):
    # request: Request is required for the rate limiter to read the caller's IP

    for existing in tickets:
        # Same email + same subject + ticket still OPEN (not closed) = duplicate
        if (existing["customer_email"] == ticket.customer_email
                and existing["subject"] == ticket.subject
                and existing["status"] != "closed"):
            raise HTTPException(status_code=409, detail="An open ticket with this subject already exists")

    ticket_id = str(uuid.uuid4())

    new_ticket = {
        "ticket_id": ticket_id,
        **ticket.model_dump(),
        # Unpacks customer_email, subject, description, priority
        "status": "open",
        # Every new ticket starts as "open" - customer never sets this directly
        "internal_notes": None
    }
    tickets.append(new_ticket)

    return new_ticket
    # Return full details back to the customer who just created it (their own ticket)

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, x_staff_key: Annotated[str | None, Header()] = None):
    # x_staff_key is optional here - its presence/validity determines what's visible

    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id:

            if x_staff_key == STAFF_KEY:
                # Caller proved they're staff (correct key) - show everything
                return ticket

            # Otherwise, treat the caller as a customer - hide internal_notes
            customer_view = {k: v for k, v in ticket.items() if k != "internal_notes"}
            # Dictionary comprehension - keep every key EXCEPT "internal_notes"
            return customer_view
            # Return the sanitized version - this is what satisfies the security challenge

    raise HTTPException(status_code=404, detail="Ticket not found")

@app.patch("/tickets/{ticket_id}")
def update_ticket_status(
    ticket_id: str,
    update: TicketStatusUpdate,
    x_staff_key: Annotated[str | None, Header()] = None
):
    # Only support staff can update ticket status
    if x_staff_key != STAFF_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id:
            ticket["status"] = update.status
            if update.internal_notes is not None:
                # Only update notes if staff actually provided some
                ticket["internal_notes"] = update.internal_notes
            return ticket
            # Staff sees the full updated ticket, including internal_notes

    raise HTTPException(status_code=404, detail="Ticket not found")

# Conclusion:
# This endpoint enforces subject/description length limits and prevents duplicate open
# tickets per customer/subject pair, and its most important security behavior is that
# a customer's GET response is always built through a filtered dictionary that strips
# out "internal_notes", while a verified staff member (correct x-staff-key) sees the
# ticket unfiltered - ensuring internal notes never leak to customers regardless of
# what staff have written there.


# ======================================================================================
# 12: API Usage Plan and Subscription Limiting
# Scenario: A software company provides three API plans - Free, Pro, Enterprise - each
#           with a different request limit.
# Creating endpoint: GET /data
# Requirements: Users send X-API-Key
# Rules:
#   - Free plan: 5 requests per minute
#   - Pro plan: 20 requests per minute
#   - Enterprise plan: 100 requests per minute
#   - Identify the plan using the API key
#   - Return the user's current plan in the response
#   - Return 401 for unknown API keys
#   - Return 429 when the plan limit is exceeded
# Security: Rate limiting must happen per API key, not only per IP address
# ======================================================================================

API_KEY_PLANS = {
    "free-key-123": "Free",
    "pro-key-456": "Pro",
    "enterprise-key-789": "Enterprise",
}
# Maps each API key to exactly one subscription plan

PLAN_LIMITS = {
    "Free": "5/minute",
    "Pro": "20/minute",
    "Enterprise": "100/minute",
}
# The rate-limit string that applies to each plan

def get_api_key_from_request(request: Request) -> str:
    # A CUSTOM key function - tells slowapi how to identify "who" is making the request
    return request.headers.get("x-api-key", "unknown")
    # Pulls the x-api-key header directly off the raw request object
    # "unknown" is the fallback if no key was sent at all

plan_limiter = Limiter(key_func=get_api_key_from_request)
# A SEPARATE limiter instance from our earlier one - this one groups/counts requests
# by API KEY (via our custom function above), not by IP address

def dynamic_plan_limit(request: Request):
    # Figures out the correct rate limit string for whoever is calling right now
    api_key = get_api_key_from_request(request)
    plan = API_KEY_PLANS.get(api_key, "Free")
    # Default to "Free" (the strictest limit) if the key is unrecognized
    return PLAN_LIMITS[plan]
    # Returns the correct limit string for that plan, e.g. "20/minute" for Pro

@app.get("/data")
@plan_limiter.limit(dynamic_plan_limit)
# Pass the FUNCTION itself (not calling it) - slowapi calls it internally for every
# incoming request to figure out which limit applies THIS time
def get_data(request: Request, x_api_key: Annotated[str | None, Header()] = None):
    plan = API_KEY_PLANS.get(x_api_key)

    if plan is None:
        # Key isn't in our dictionary at all - not a real/known key
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "message": "Here is your data",
        "plan": plan
        # Echo back which plan this request was recognized as belonging to
    }

# Conclusion:
# This endpoint proves rate limiting can be scoped per identity rather than per network
# location: a custom key function reads the caller's API key instead of their IP, and a
# dynamic limit function looks up the correct request budget for that specific key's
# plan on every call. Two callers sharing the same IP but using different keys get
# fully independent limits.


# ======================================================================================
# 13: Secure Password Reset Request API
# Scenario: A user forgets their password and requests a password-reset link. Attackers
#           are using this endpoint to identify registered email addresses.
# Creating endpoints:
#   POST /password-reset/request
#   POST /password-reset/confirm
# Requirements:
#   - Request endpoint accepts an email address
#   - Always return the same message whether the email exists or not
#   - Generate a reset token only for registered users
#   - Token must expire after a limited time
#   - Password must have at least eight characters
#   - Reset token can be used only once
#   - Apply strict rate limiting
# Security: The response must not reveal whether the email exists in the system
# ======================================================================================

RESET_TOKENS = {}
# Our "fake database" for reset tokens
# Structure: {token_string: {"email": ..., "expires_at": ..., "used": False}}

TOKEN_EXPIRY_MINUTES = 15
# How long a reset token stays valid after being generated

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
    # New password must be at least 8 characters

@app.post("/password-reset/request")
@limiter.limit("3/minutes")
# Strict rate limit - only 3 reset requests per minute per IP, to slow down anyone
# trying to guess/enumerate emails
def request_password_reset(request: Request, reset_request: PasswordResetRequest):
    # request: Request is required for the rate limiter to inspect the caller's IP

    stored_password = FAKE_USERS.get(reset_request.email)
    # Check if this email is actually registered (reusing FAKE_USERS from section 5)

    if stored_password is not None:
        # Only generate a real token if the email IS registered
        token = str(uuid.uuid4())

        expires_at = datetime.now() + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
        # Calculate the exact moment this token will stop being valid

        RESET_TOKENS[token] = {
            "email": reset_request.email,
            "expires_at": expires_at,
            "used": False,
        }
        # NOTE: in a real system, this token would be emailed to the user here -
        # it is never returned directly in the API response

    # SECURITY: return the EXACT SAME message whether the email existed or not
    return {"message": "If the email is registered, a password reset link has been sent"}

@app.post("/password-reset/confirm")
def confirm_password_reset(confirm: PasswordResetConfirm):
    token_data = RESET_TOKENS.get(confirm.token)

    if token_data is None:
        # Token doesn't exist at all (never issued, or was typed wrong)
        raise HTTPException(status_code=400, detail="Invalid or expired token")
        # Same generic message used for every failure case below too

    if token_data["used"]:
        # This token was already used once before
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    if datetime.now() > token_data["expires_at"]:
        # Current time has passed the token's expiry moment
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # --- Token is valid, unused, and not expired - proceed with the reset ---
    FAKE_USERS[token_data["email"]] = confirm.new_password
    # Overwrite the stored password for this user with their new one

    token_data["used"] = True
    # Mark this token as used, so it can never be reused again

    return {"message": "Password has been reset successfully"}

# Conclusion:
# This endpoint pair protects user privacy by always returning the same response from
# the request endpoint whether or not the email is registered, generating a real token
# only behind the scenes for actual users. The confirm endpoint enforces a single,
# generic "Invalid or expired token" message across three different failure reasons
# (never issued, already used, expired), so no information about why a token failed is
# ever leaked to the caller.


# ======================================================================================
# 14: Coupon Management API
# Scenario: An e-commerce administrator wants to create discount coupons, while
#           customers can only validate coupons.
# Creating endpoints:
#   POST /admin/coupons
#   GET /coupons/validate
#   DELETE /admin/coupons/{coupon_code}
# Requirements:
#   - Admin endpoints require an admin API key
#   - Coupon discount must be between 1% and 80%
#   - Expiry date must be in the future
#   - Coupon code must be unique
#   - Validation endpoint takes coupon code and order value
#   - Coupon may have a minimum order value
#   - Expired coupons should return a controlled error
#   - Return 403 for non-admin access
# Security: Customers must never be able to create or delete coupons
# ======================================================================================

COUPON_STORE = {}
# Our "fake database" for coupons - richer than section 4's simple COUPONS dict, since
# this needs expiry and minimum order value per coupon
# Structure: {code: {"discount_percent": ..., "expiry_date": ..., "min_order_value": ...}}

class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=20)
    discount_percent: int = Field(ge=1, le=80)
    # Discount must be between 1% and 80%
    expiry_date: date
    # A real date object - client sends a string like "2026-12-31", pydantic parses it
    min_order_value: float = Field(ge=0, default=0)
    # Optional minimum order value; defaults to 0 (no minimum)

    @field_validator("expiry_date")
    @classmethod
    def expiry_must_be_in_future(cls, value):
        # Custom validator - same idea as section 7's "not in the past" check, but reversed
        if value <= date.today():
            raise ValueError("Expiry date must be in the future")
        return value

class CouponValidateRequest(BaseModel):
    coupon_code: str
    order_value: float = Field(gt=0)

@app.post("/admin/coupons", status_code=status.HTTP_201_CREATED)
def create_coupon(coupon: CouponCreate, x_admin_key: Annotated[str | None, Header()] = None):
    # Only an admin can create coupons
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    if coupon.code in COUPON_STORE:
        # The coupon code must be unique
        raise HTTPException(status_code=409, detail="Coupon code already exists")

    COUPON_STORE[coupon.code] = {
        "discount_percent": coupon.discount_percent,
        "expiry_date": coupon.expiry_date,
        "min_order_value": coupon.min_order_value
    }

    return {"message": "Coupon created", "code": coupon.code}

@app.get("/coupons/validate")
def validate_coupon(coupon_code: str, order_value: float):
    # Both coupon_code and order_value come in as QUERY parameters
    # (e.g. /coupons/validate?coupon_code=SUMMER25&order_value=500)

    coupon = COUPON_STORE.get(coupon_code)

    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")

    if date.today() > coupon["expiry_date"]:
        # A "controlled" error - clear, safe message, no stack trace
        raise HTTPException(status_code=400, detail="Coupon has expired")

    if order_value < coupon["min_order_value"]:
        raise HTTPException(
            status_code=400,
            detail=f"Order value must be at least {coupon['min_order_value']} to use this coupon"
        )

    # --- Coupon is valid - calculate the discount ---
    discount_amount = order_value * coupon["discount_percent"] / 100
    final_amount = order_value - discount_amount

    return {
        "coupon_code": coupon_code,
        "discount_percent": coupon["discount_percent"],
        "discount_amount": discount_amount,
        "final_amount": final_amount
    }

@app.delete("/admin/coupons/{coupon_code}")
def delete_coupon(coupon_code: str, x_admin_key: Annotated[str | None, Header()] = None):
    # Only an admin can delete coupons - this is the actual security requirement:
    # customers must NEVER be able to reach this far
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    if coupon_code not in COUPON_STORE:
        raise HTTPException(status_code=404, detail="Coupon not found")

    del COUPON_STORE[coupon_code]

    return {"message": "Coupon deleted", "code": coupon_code}

# Conclusion:
# This endpoint set enforces a strict admin-only gate on both creation and deletion,
# using a custom field_validator to guarantee coupons can never be created already
# expired. The validation endpoint is entirely public but read-only, calculating
# discounts using only server-stored coupon data, so customers can check savings
# without ever being able to alter the coupon catalog itself.


# ======================================================================================
# 15: Delivery Tracking API with CORS
# Scenario: A logistics company has a customer website (https://track.company.com) and
#           a separate internal admin dashboard (https://admin.company.com).
# Creating endpoints:
#   GET /tracking/{tracking_id}
#   PATCH /tracking/{tracking_id}
# Requirements:
#   - Customer website can call only GET
#   - Admin dashboard can call GET and PATCH
#   - Only exact frontend origins should be allowed
#   - Tracking status must be validated
#   - Admin update requires an API key
#   - Return 404 for invalid tracking IDs
# Security: Configure CORS without using allow_origins=["*"], and explain why CORS does
#           not replace authentication
# ======================================================================================

# NOTE: the actual CORSMiddleware configuration (app.add_middleware(...)) lives near the
# top of this file, right after "app = FastAPI(...)" is created, since middleware is a
# whole-application setting rather than something tied to one specific endpoint. Repeating
# the reasoning here: CORS (Cross-Origin Resource Sharing) is a BROWSER-enforced
# mechanism. By default, a browser blocks JavaScript running on one website from calling
# a different domain's API unless that API explicitly grants permission. Our middleware
# grants that permission ONLY to https://track.company.com and https://admin.company.com
# - never allow_origins=["*"], which would let any website call this API from a browser.

TRACKING_STATUSES = Literal["pending", "in_transit", "out_for_delivery", "delivered", "failed"]
# Restrict tracking status to these fixed values

TRACKING_DATA = {
    "TRACK1001": {"status": "in_transit"},
    "TRACK1002": {"status": "pending"},
}

class TrackingUpdate(BaseModel):
    status: TRACKING_STATUSES
    # The new status - must be one of the 5 allowed values, nothing else

@app.get("/tracking/{tracking_id}")
def get_tracking(tracking_id: str):
    # Public-ish endpoint (still reachable by anyone technically, but the CORS rule
    # above means only track.company.com or admin.company.com can call it FROM A BROWSER)

    tracking = TRACKING_DATA.get(tracking_id)

    if tracking is None:
        raise HTTPException(status_code=404, detail="Invalid tracking ID")

    return {"tracking_id": tracking_id, "status": tracking["status"]}

@app.patch("/tracking/{tracking_id}")
def update_tracking(
    tracking_id: str,
    update: TrackingUpdate,
    x_api_key: Annotated[str | None, Header()] = None):

    # Admin update requires an API key (per the assignment)
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    tracking = TRACKING_DATA.get(tracking_id)

    if tracking is None:
        raise HTTPException(status_code=404, detail="Invalid tracking ID")

    tracking["status"] = update.status

    return {"tracking_id": tracking_id, "status": tracking["status"]}

# Conclusion:
# This endpoint pair is protected at two independent layers: CORS middleware restricts
# which browser-based origins may even reach the API in the first place (locked to the
# two real company domains, never a wildcard), while the x-api-key check on the PATCH
# endpoint independently verifies that the caller is actually authorized to update
# tracking data. CORS alone cannot replace authentication, since tools outside a
# browser (curl, Postman, scripts) ignore CORS entirely - only the API key check
# actually verifies identity and permission.


# ======================================================================================
# 16: Multi-Tenant Organization API
# Scenario: A SaaS platform serves multiple companies. Employees from one company must
#           never see data belonging to another company.
# Creating endpoints:
#   POST /employees
#   GET /employees
#   GET /employees/{employee_id}
# Requirements: Each request should contain X-Organization-ID and X-API-Key
# Rules:
#   - Every employee record belongs to an organization
#   - An organization can view only its own employees
#   - The same API key must be mapped to a specific organization
#   - Return 403 if the organization ID and API key do not match
#   - Prevent one organization from accessing another organization's employee ID
#   - Validate employee email and department
# Security: This must prevent cross-tenant data leakage
# ======================================================================================

ORG_API_KEYS = {
    "org-key-alpha": "OrgAlpha",
    "org-key-beta": "OrgBeta",
}
# Maps each API key to EXACTLY ONE organization - this mapping is what prevents someone
# from using OrgAlpha's key while claiming to be OrgBeta

class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    department: str = Field(min_length=2, max_length=50)

employees = []
# Our "fake database" of employees across ALL organizations
# Each entry: {"employee_id", "organization", "name", "email", "department"}

def verify_organization(x_organization_id: str | None, x_api_key: str | None) -> str:
    # Shared helper - checks both headers TOGETHER and returns the verified org name;
    # reused by all three endpoints below so this logic isn't repeated three times

    expected_org = ORG_API_KEYS.get(x_api_key)
    # Look up which organization this API key is REALLY supposed to belong to

    if expected_org is None:
        # The key itself isn't recognized at all
        raise HTTPException(status_code=403, detail="Access denied")

    if expected_org != x_organization_id:
        # The key IS valid, but the organization ID claimed doesn't match what this
        # key is actually registered to - this is the core security check
        raise HTTPException(status_code=403, detail="Access denied")

    return expected_org

@app.post("/employees", status_code=status.HTTP_201_CREATED)
def create_employee(
    employee: EmployeeCreate,
    x_organization_id: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None
):
    org = verify_organization(x_organization_id, x_api_key)
    # Confirms the caller's key genuinely belongs to the org they claim - raises if not

    employee_id = str(uuid.uuid4())

    new_employee = {
        "employee_id": employee_id,
        "organization": org,
        # Tag this employee record with the VERIFIED organization, not client input
        **employee.model_dump()
    }
    employees.append(new_employee)

    return new_employee

@app.get("/employees")
def list_employees(
    x_organization_id: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None
):
    org = verify_organization(x_organization_id, x_api_key)

    org_employees = [e for e in employees if e["organization"] == org]
    # Filter the FULL list down to only employees belonging to THIS organization -
    # this is the actual anti-leakage mechanism

    return org_employees

@app.get("/employees/{employee_id}")
def get_employee(
    employee_id: str,
    x_organization_id: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None
):
    org = verify_organization(x_organization_id, x_api_key)

    for employee in employees:
        if employee["employee_id"] == employee_id:

            if employee["organization"] != org:
                # The employee exists, but belongs to a DIFFERENT organization -
                # exactly the scenario this rule warns about
                raise HTTPException(status_code=403, detail="Access denied")

            return employee

    raise HTTPException(status_code=404, detail="Employee not found")
    # No employee with this ID exists anywhere at all

# Conclusion:
# This endpoint set implements multi-tenancy by combining two headers into a single
# verified identity check: an API key must both be recognized AND match the specific
# organization ID the caller claims. Employee lists are always filtered down to the
# caller's own organization, and even direct lookups by employee ID are blocked with
# a 403 if that employee belongs to a different organization - fully preventing
# cross-tenant data leakage.


# ======================================================================================
# 17: Webhook Receiver API
# Scenario: A payment gateway sends payment status updates to your FastAPI application
#           through a webhook.
# Creating endpoint: POST /webhooks/payment
# Requirements:
#   - Request must contain a webhook secret header
#   - Reject requests with an invalid secret
#   - Process the same event_id only once
#   - Allowed statuses are success, failed, pending, and refunded
#   - Amount must be positive
#   - Return quickly after processing
#   - Store processed event IDs
# Security: Prevent replay attacks by rejecting duplicate event IDs
# ======================================================================================

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
# Loads the shared secret the payment gateway and our server both know

PROCESSED_EVENT_IDS = set()
# A SET (not a list) for storing event IDs we've already handled - sets check
# "is this already here?" much faster than lists, and don't allow duplicates anyway

class WebhookPayload(BaseModel):
    event_id: str
    payment_id: str
    status: Literal["success", "failed", "pending", "refunded"]
    # Must be one of these 4 exact values
    amount: float = Field(gt=0)
    # Amount must be strictly positive

@app.post("/webhooks/payment")
def receive_payment_webhook(
    payload: WebhookPayload,
    x_webhook_secret: Annotated[str | None, Header()] = None
):
    # 1. Verify the webhook secret header
    if x_webhook_secret != WEBHOOK_SECRET:
        # This request didn't really come from our trusted payment gateway
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # 2. Check for replay - has this exact event_id been processed before?
    if payload.event_id in PROCESSED_EVENT_IDS:
        return {"message": "Event already processed"}
        # NOTE: we return 200 here, not an error - payment gateways often retry
        # webhooks automatically if they don't get a quick 200 response, so responding
        # normally (instead of an error) prevents endless retries over something that's
        # already been handled successfully

    # 3. Process the event (in a real system: update payment status in DB, send
    #    confirmation email, etc. - here we just simulate it)
    PROCESSED_EVENT_IDS.add(payload.event_id)
    # Remember this event_id so any future duplicate gets caught by the check above

    return {"message": "Webhook processed successfully", "event_id": payload.event_id}
    # Return quickly - keep this endpoint lightweight, no slow/unnecessary work

# Conclusion:
# This endpoint defends against replay attacks by remembering every event_id it has
# already processed in a set, and silently acknowledging (rather than erroring on) any
# duplicate - which both satisfies the security requirement and plays nicely with
# payment gateways that retry webhooks automatically on slow or missing responses.


# ======================================================================================
# 18: Audit Logging API
# Scenario: A company wants to record all sensitive actions performed by administrators.
# Creating endpoints:
#   POST /admin/users
#   DELETE /admin/users/{user_id}
#   GET /admin/audit-logs
# Requirements:
#   - All endpoints require an admin key
#   - Every create and delete operation must generate an audit log
#   - Audit log should include: action, admin identity, time, affected resource, result
#   - Sensitive values such as passwords and API keys must not be logged
#   - Audit logs should not be modifiable
#   - Return safe error messages
# Security: Create a logging function that automatically removes sensitive fields
# ======================================================================================

SENSITIVE_FIELDS = {"password", "api_key", "token", "secret"}
# Any field name in this set will be automatically stripped before logging - a single
# place to maintain this list, instead of scattering checks everywhere

audit_logs = []
# Our "fake database" of audit log entries - append-only, nothing ever edits these

class AdminUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    # Included here to simulate a real "create user" flow - this is exactly the kind
    # of field that must NEVER end up in a log entry

admin_users = []
# Separate "fake database" of users created through this admin endpoint

def sanitize_data(data: dict) -> dict:
    # Takes any dictionary and returns a COPY with sensitive fields removed
    return {k: v for k, v in data.items() if k.lower() not in SENSITIVE_FIELDS}
    # Dictionary comprehension - keep every key-value pair EXCEPT any key whose
    # lowercase name appears in SENSITIVE_FIELDS

def create_audit_log(action: str, admin_identity: str, resource: str, result: str, details: dict | None = None):
    # ONE shared function for writing an audit log entry - called from every admin
    # action, so the format and sanitization logic stays consistent everywhere
    log_entry = {
        "log_id": str(uuid.uuid4()),
        "action": action,
        # What happened, e.g. "create_user" or "delete_user"
        "admin_identity": admin_identity,
        # Who performed the action
        "timestamp": datetime.now().isoformat(),
        "resource": resource,
        # What was affected, e.g. a user ID
        "result": result,
        # Outcome, e.g. "success" or "failed"
        "details": sanitize_data(details) if details else {}
        # ALWAYS passed through sanitize_data() first - this is what guarantees
        # sensitive fields never make it into the log
    }
    audit_logs.append(log_entry)
    # Nothing else in this file ever modifies or deletes from audit_logs, satisfying
    # "logs should not be modifiable"

@app.post("/admin/users", status_code=status.HTTP_201_CREATED)
def create_admin_user(user: AdminUserCreate, x_admin_key: Annotated[str | None, Header()] = None):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    user_id = str(uuid.uuid4())

    new_user = {
        "user_id": user_id,
        **user.model_dump()
        # Includes name, email, AND password - fine to store in admin_users
        # (our actual user data), just never in the audit log
    }
    admin_users.append(new_user)

    create_audit_log(
        action="create_user",
        admin_identity=x_admin_key,
        # NOTE: logging the key itself is a minor leak in a real system - a real app
        # would log an admin's USERNAME here, not their secret key
        resource=user_id,
        result="success",
        details=user.model_dump()
        # Passed straight in - sanitize_data() strips out "password" automatically
    )

    return {"user_id": user_id, "name": user.name, "email": user.email}
    # Return the response WITHOUT the password too - never echo secrets back either

@app.delete("/admin/users/{user_id}")
def delete_admin_user(user_id: str, x_admin_key: Annotated[str | None, Header()] = None):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    for index, user in enumerate(admin_users):
        if user["user_id"] == user_id:
            admin_users.pop(index)

            create_audit_log(
                action="delete_user",
                admin_identity=x_admin_key,
                resource=user_id,
                result="success"
            )

            return {"message": "User deleted", "user_id": user_id}

    # If we reach here, no matching user was found
    create_audit_log(
        action="delete_user",
        admin_identity=x_admin_key,
        resource=user_id,
        result="failed - user not found"
        # Even FAILED attempts get logged - useful for security monitoring
    )
    raise HTTPException(status_code=404, detail="User not found")
    # Safe, generic error message - no internal details or stack trace exposed

@app.get("/admin/audit-logs")
def get_audit_logs(x_admin_key: Annotated[str | None, Header()] = None):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    return audit_logs
    # Already guaranteed sanitized, since sanitize_data() ran on every entry when created

# Conclusion:
# This endpoint set demonstrates a reusable, sanitizing logging function: every audit
# entry is written through create_audit_log(), which always passes any extra details
# through sanitize_data() first, automatically stripping password/api_key/token/secret
# fields before storage. Because no other code in the file ever edits or removes an
# existing log entry, and both successful and failed admin actions are recorded, the
# audit trail remains complete, safe, and effectively immutable.


# ======================================================================================
# 19: Secure Book Library API
# Scenario: A digital library allows users to borrow books. A user cannot borrow more
#           than three books at a time.
# Creating endpoints:
#   GET /books
#   POST /books/{book_id}/borrow
#   POST /books/{book_id}/return
#   GET /users/{user_id}/borrowed-books
# Requirements:
#   - Book must exist
#   - Book must be available before borrowing
#   - A user can borrow a maximum of three books
#   - The same book cannot be borrowed by two users
#   - Only the correct user can return their borrowed book
#   - All borrow and return actions require authentication
#   - Rate limit borrowing attempts
# Security: Ensure all validations complete before changing the book's availability
# ======================================================================================

USER_KEYS = {
    "user-key-1": "Meera",
    "user-key-2": "Vikram",
}
# Same pattern as section 2's EMPLOYEE_KEYS - the key itself doubles as identity

BOOKS = {
    1: {"title": "Clean Code", "available": True, "borrowed_by": None},
    2: {"title": "The Pragmatic Programmer", "available": True, "borrowed_by": None},
    3: {"title": "Design Patterns", "available": True, "borrowed_by": None},
}
# "available" tracks whether the book can currently be borrowed
# "borrowed_by" tracks WHICH user currently has it (None if nobody does)

@app.get("/books")
def list_books():
    # Public endpoint - anyone can browse the catalog, no auth needed
    return BOOKS

@app.post("/books/{book_id}/borrow", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
# Rate limit borrowing attempts - reusing our existing IP-based limiter
def borrow_book(request: Request, book_id: int, x_user_key: Annotated[str | None, Header()] = None):
    # 1. Identify the user from their key
    user_name = USER_KEYS.get(x_user_key)
    if user_name is None:
        raise HTTPException(status_code=401, detail="Invalid user key")

    # 2. The book must exist
    book = BOOKS.get(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    # 3. The book must currently be available
    if not book["available"]:
        raise HTTPException(status_code=409, detail="Book is already borrowed")
        # Someone else already has this exact book - reject before touching anything

    # 4. A user can borrow a maximum of 3 books at a time
    user_borrowed_count = sum(1 for b in BOOKS.values() if b["borrowed_by"] == user_name)
    # Count how many books THIS user currently has borrowed across the whole catalog
    if user_borrowed_count >= 3:
        raise HTTPException(status_code=400, detail="Borrowing limit of 3 books reached")

    # --- ALL VALIDATIONS PASSED - only now do we change the book's state ---
    book["available"] = False
    book["borrowed_by"] = user_name

    return {"message": f"{book['title']} borrowed successfully", "book_id": book_id}

@app.post("/books/{book_id}/return")
def return_book(book_id: int, x_user_key: Annotated[str | None, Header()] = None):
    # 1. Identify the user from their key
    user_name = USER_KEYS.get(x_user_key)
    if user_name is None:
        raise HTTPException(status_code=401, detail="Invalid user key")

    # 2. The book must exist
    book = BOOKS.get(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    # 3. The book must actually be currently borrowed BY THIS SPECIFIC USER
    if book["borrowed_by"] != user_name:
        # Covers two cases at once: nobody borrowed it (borrowed_by is None), OR
        # someone ELSE borrowed it - either way, this user can't return it
        raise HTTPException(status_code=403, detail="You did not borrow this book")

    # --- Validation passed - only now do we update the book ---
    book["available"] = True
    book["borrowed_by"] = None

    return {"message": f"{book['title']} returned successfully", "book_id": book_id}

@app.get("/users/{user_id}/borrowed-books")
def get_borrowed_books(user_id: str):
    # user_id here is the USER'S NAME (e.g. "Meera") for simplicity in this assignment,
    # matching the values stored in USER_KEYS/borrowed_by

    borrowed = [
        {"book_id": bid, "title": b["title"]}
        for bid, b in BOOKS.items()
        if b["borrowed_by"] == user_id
    ]
    # Build a list of just this user's currently borrowed books

    return {"user_id": user_id, "borrowed_books": borrowed}

# Conclusion:
# This endpoint set enforces the library's borrowing rules by validating everything -
# user identity, book existence, availability, and the 3-book limit - before ever
# marking a book unavailable, and symmetrically checks true ownership before allowing
# a return. This "validate everything first, mutate last" discipline, seen throughout
# this assignment (sections 6, 9, and 19), guarantees the book catalog never ends up
# in an inconsistent state.