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