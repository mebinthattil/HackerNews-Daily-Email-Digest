import os
from typing import Tuple
from dotenv import load_dotenv
import re
import logging

load_dotenv()

logger = logging.getLogger(__name__)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO)


def validate_email(email: str) -> (bool, str):
    """return (True, sanitized_email) or (False, error_message)."""
    email = email.strip()
    if not email:
        msg = "Email is required."
        logger.info("Trying to validate email, errored out with " + msg)
        return (False, msg)

    pattern = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    if not pattern.match(email):
        msg = "Invalid email format."
        logger.info("Trying to validate email, errored out with " + msg)
        return (False, msg)

    msg = email
    return (True, msg)

def add_subscriber(email: str) -> Tuple[bool, str]:
    """return (True, success_message) or (False, error_message)."""
    emailOK, email = validate_email(email)
    if not emailOK:
        err_msg = email # because validate_email returns (False, err_msg)
        return (False, err_msg)

    try:
        import requests
    except Exception:
        msg = "Missing dependency: requests"
        logger.info("Trying to add subscriber, errored out with " + msg)
        return (False, msg)

    api_key = (os.getenv("MAILGUN_API_KEY") or "").strip()
    list_name = (os.getenv("MAILGUN_LIST_NAME") or "").strip()
    domain_name = (os.getenv("DOMAIN_NAME") or "").strip()

    if not api_key or not list_name or not domain_name:
        msg = "Mailgun configuration missing (MAILGUN_API_KEY, MAILGUN_LIST_NAME, or DOMAIN_NAME). Update ENV"
        logger.info("Trying to add subscriber, errored out with " + msg)
        return (False, msg)

    url = f"https://api.mailgun.net/v3/lists/{list_name}@{domain_name}/members"

    data = {
        "address": email,
        "subscribed": True,
        "upsert": "yes",
    }

    try:
        resp = requests.post(url, auth=("api", api_key), data=data, timeout=10)
    except requests.RequestException as exc:
        msg = f"Request error: {exc}"
        logger.info("Trying to add subscriber, errored out with " + msg)
        return (False, msg)

    if resp.status_code == 200:
        msg = f"Added {email} to mailing list"
        logger.info(msg)
        return (True, msg)
    elif resp.status_code == 429:
        msg = "Too many requests"
        logger.info("Trying to add subscriber, errored out with " + msg)
        return (False, msg)
    else:
        # Try to extract useful error
        try:
            detail = resp.json()
        except Exception:
            detail = getattr(resp, 'text', str(resp))

        msg = f"Mailgun error ({resp.status_code}): {detail}"
        logger.info("Trying to add subscriber, errored out with " + msg)
        return (False, msg)