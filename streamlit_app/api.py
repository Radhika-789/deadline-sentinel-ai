import requests

BASE_URL = "http://127.0.0.1:8000"


class AuthError(Exception):
    """Raised when a request fails because the JWT is missing, invalid,
    or expired (backend returned 401). The caller (app.py) should clear
    the session and send the user back to the login page."""
    pass


def _auth_headers(token: str) -> dict:
    """Build the Authorization header for a protected request."""
    return {"Authorization": f"Bearer {token}"}


def _raise_for_status(response: requests.Response) -> None:
    """Like response.raise_for_status(), but turns a 401 into AuthError
    so the frontend can distinguish 'session expired' from other errors."""
    if response.status_code == 401:
        raise AuthError("Session expired or invalid. Please log in again.")
    response.raise_for_status()


def get_health():
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False


# --- Auth -------------------------------------------------------------

def signup(email: str, password: str, username: str | None = None):
    """
    Register a new user account.
    Raises requests.HTTPError (e.g. 409 if the email is already taken,
    400/422 on validation errors) on failure.
    """
    payload = {"email": email, "password": password}
    if username:
        payload["username"] = username

    response = requests.post(f"{BASE_URL}/auth/signup", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def login(email: str, password: str):
    """
    Authenticate and return the token payload: {"access_token", "token_type"}.
    Raises requests.HTTPError (401 on bad credentials) on failure.
    Uses OAuth2 form-encoded body since the backend's /auth/login endpoint
    expects OAuth2PasswordRequestForm (username=email, password=password).
    """
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": email, "password": password},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_current_user(token: str):
    """Fetch the authenticated user's profile. Raises AuthError on 401."""
    response = requests.get(
        f"{BASE_URL}/users/me", headers=_auth_headers(token), timeout=10
    )
    _raise_for_status(response)
    return response.json()


# --- Deadlines (all scoped server-side to the authenticated user) -----

def get_deadlines(
    token,
    company_name=None,
    category=None,
    status=None,
    deadline_from=None,
    deadline_to=None,
    skip=0,
    limit=20,
    sort_by="deadline",
    order="asc",
):
    """
    Fetch deadlines from the FastAPI backend using optional
    filtering, sorting and pagination. Requires a valid JWT; the
    backend scopes results to the calling user.
    """

    params = {
        "skip": skip,
        "limit": limit,
        "sort_by": sort_by,
        "order": order,
    }

    if company_name:
        params["company_name"] = company_name

    if category:
        params["category"] = category

    if status:
        params["status"] = status

    if deadline_from:
        params["deadline_from"] = deadline_from.isoformat()

    if deadline_to:
        params["deadline_to"] = deadline_to.isoformat()

    response = requests.get(
        f"{BASE_URL}/deadlines",
        params=params,
        headers=_auth_headers(token),
        timeout=20,
    )

    _raise_for_status(response)

    return response.json()


def upload_file(token, file):
    """
    Upload a file to the FastAPI backend for the authenticated user.
    """
    files = {"file": (file.name, file.getvalue(), file.type)}
    response = requests.post(
        f"{BASE_URL}/upload",
        files=files,
        headers=_auth_headers(token),
        timeout=30,
    )
    _raise_for_status(response)
    return response.json()


def get_deadline_calendar(token, deadline_id):
    """
    Download the .ics calendar file for a single deadline owned by the
    authenticated user. Returns the raw file bytes plus the filename
    suggested by the backend's Content-Disposition header.
    """
    response = requests.get(
        f"{BASE_URL}/deadlines/{deadline_id}/calendar",
        headers=_auth_headers(token),
        timeout=20,
    )
    _raise_for_status(response)

    filename = f"deadline_{deadline_id}.ics"
    content_disposition = response.headers.get("Content-Disposition", "")
    if "filename=" in content_disposition:
        filename = content_disposition.split("filename=")[-1].strip('"; ')

    return response.content, filename