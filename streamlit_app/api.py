import requests

BASE_URL = "http://127.0.0.1:8000"


def get_health():
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False


def get_deadlines(
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
    filtering, sorting and pagination.
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
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def upload_file(file):
    """
    Upload a file to the FastAPI backend.
    """
    files = {"file": (file.name, file.getvalue(), file.type)}
    response = requests.post(f"{BASE_URL}/upload", files=files, timeout=30)
    response.raise_for_status()
    return response.json()

def get_deadline_calendar(deadline_id):
    """
    Download the .ics calendar file for a single deadline from the
    FastAPI backend. Returns the raw file bytes plus the filename
    suggested by the backend's Content-Disposition header.
    """
    response = requests.get(
        f"{BASE_URL}/deadlines/{deadline_id}/calendar",
        timeout=20,
    )
    response.raise_for_status()

    filename = f"deadline_{deadline_id}.ics"
    content_disposition = response.headers.get("Content-Disposition", "")
    if "filename=" in content_disposition:
        filename = content_disposition.split("filename=")[-1].strip('"; ')

    return response.content, filename