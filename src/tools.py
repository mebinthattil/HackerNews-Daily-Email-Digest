import os
from typing import Tuple
from dotenv import load_dotenv
import re
import logging

load_dotenv()

logger = logging.getLogger(__name__)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO)


class MailgunError(Exception):
    """Base exception for Mailgun-related errors."""


class DependencyError(MailgunError):
    pass


class ConfigError(MailgunError):
    pass


class InvalidEmailError(MailgunError):
    pass


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


def _get_requests_module():
    try:
        import requests
        return requests, None
    except Exception:
        msg = "Missing dependency: requests"
        logger.info(msg)
        return None, msg


def _get_mailgun_config():
    api_key = (os.getenv("MAILGUN_API_KEY") or "").strip()
    list_name = (os.getenv("MAILGUN_LIST_NAME") or "").strip()
    domain_name = (os.getenv("DOMAIN_NAME") or "").strip()
    if not api_key or not list_name or not domain_name:
        msg = "Mailgun configuration missing (MAILGUN_API_KEY, MAILGUN_LIST_NAME, or DOMAIN_NAME). Update ENV"
        logger.info(msg)
        return None, None, None, msg
    return api_key, list_name, domain_name, None


def _members_base_url(list_name: str, domain_name: str) -> str:
    return f"https://api.mailgun.net/v3/lists/{list_name}@{domain_name}/members"


def _member_url(list_name: str, domain_name: str, email: str) -> str:
    return f"{_members_base_url(list_name, domain_name)}/{email}"

def add_subscriber(email: str) -> Tuple[bool, str]:
    """Return (True, message) on success (or already subscribed), or (False, error_message).

    Performs pre-check for existing subscriber
    Handles exceptions by converting them to error messages so callers need only inspect the boolean.
    """
    try:
        already_subscribed = existing_subscriber(email)
    except (InvalidEmailError, DependencyError, ConfigError, MailgunError) as exc:
        return False, str(exc)

    if already_subscribed:
        return True, "You are already subscribed to the mailing list."

    requests, err = _get_requests_module()
    if requests is None:
        return False, err

    api_key, list_name, domain_name, cfg_err = _get_mailgun_config()
    if cfg_err:
        return False, cfg_err

    url = _members_base_url(list_name, domain_name)

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


def existing_subscriber(email: str) -> bool:
    """Return True if subscriber exists, False if not.

    Raises:
      InvalidEmailError: when email is invalid.
      DependencyError: when `requests` is unavailable.
      ConfigError: when mailgun env configs are missing.
      MailgunError: for network/API errors.
    """
    valid, email = validate_email(email)
    if not valid:
        logger.info("existing_subscriber: invalid email -> %s", email)
        raise InvalidEmailError(email)

    requests, err = _get_requests_module()
    if requests is None:
        raise DependencyError(err)

    api_key, list_name, domain_name, cfg_err = _get_mailgun_config()
    if cfg_err:
        raise ConfigError(cfg_err)

    url = _member_url(list_name, domain_name, email)

    try:
        resp = requests.get(url, auth=("api", api_key), timeout=8)
    except requests.RequestException as exc:
        logger.info("Trying to check if existing_subscriber, errored out with request error: %s", exc)
        raise MailgunError(f"Request error: {exc}")

    if resp.status_code == 200:
        logger.info("Subscriber exists: %s", email)
        return True
    elif resp.status_code == 404:
        return False
    elif resp.status_code == 429:
        logger.info("Trying to check if existing_subscriber, errored out with: Too many requests")
        raise MailgunError("Too many requests")

    try:
        detail = resp.json()
    except Exception:
        detail = getattr(resp, 'text', str(resp))

    logger.info("existing_subscriber Mailgun error (%s): %s", resp.status_code, detail)
    raise MailgunError(f"Mailgun error ({resp.status_code}): {detail}")