"""
Helper functions for communicating with the FastAPI backend.

Keeping HTTP logic here keeps Streamlit UI code clean and makes it
easy to change the backend URL or add authentication later.
"""

from typing import Any

import requests

BASE_URL = "http://127.0.0.1:8000"


def get_health() -> bool:
    """
    Returns True if backend is healthy.
    """

    try:
        response = requests.get(
            f"{BASE_URL}/health",
            timeout=3,
        )

        return response.status_code == 200

    except requests.RequestException:
        return False


def get_deadlines() -> list[dict[str, Any]]:
    """
    Fetch all deadlines from FastAPI.
    """

    response = requests.get(
        f"{BASE_URL}/deadlines",
        timeout=10,
    )

    response.raise_for_status()

    return response.json()