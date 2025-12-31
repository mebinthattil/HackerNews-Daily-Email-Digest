import os
import pathlib
from typing import Tuple, Optional
from dotenv import load_dotenv
import re
from logger import setup_logger

load_dotenv()

logger = setup_logger(__name__)


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


def _prepare_mailgun(email: str):
    """Validate email, import requests and load mailgun config.

    Returns (sanitized_email, requests_module, api_key, list_name, domain_name).
    Raises InvalidEmailError, DependencyError, ConfigError.
    """
    valid, sanitized_email = validate_email(email)
    if not valid:
        raise InvalidEmailError(sanitized_email)

    requests_mod, err = _get_requests_module()
    if requests_mod is None:
        raise DependencyError(err)

    api_key, list_name, domain_name, cfg_err = _get_mailgun_config()
    if cfg_err:
        raise ConfigError(cfg_err)

    return sanitized_email, requests_mod, api_key, list_name, domain_name


def add_subscriber(email: str) -> Tuple[bool, str]:
    """Return (True, message) on success (or already subscribed), or (False, error_message).

    Performs pre-check for existing subscriber
    Handles exceptions by converting them to error messages so callers need only inspect the boolean.
    """
    try:
        sanitized_email, requests, api_key, list_name, domain_name = _prepare_mailgun(email)
    except (InvalidEmailError, DependencyError, ConfigError, MailgunError) as exc:
        return False, str(exc)

    try:
        exists, is_subscribed = existing_subscriber(sanitized_email)
    except (InvalidEmailError, DependencyError, ConfigError, MailgunError) as exc:
        return False, str(exc)

    if exists and is_subscribed:
        return True, "You are already subscribed to the mailing list."

    url = _members_base_url(list_name, domain_name)

    data = {"address": sanitized_email, "subscribed": True, "upsert": "yes"}

    try:
        resp = requests.post(url, auth=("api", api_key), data=data, timeout=10)
    except requests.RequestException as exc:
        msg = f"Request error: {exc}"
        logger.info("Trying to add subscriber, errored out with " + msg)
        return (False, msg)

    if resp.status_code == 200:
        msg = f"Added {sanitized_email} to mailing list"
        logger.info(msg)
        #send greeting email
        try:
            sent, send_msg = send_greeting_mail(sanitized_email)
            if sent:
                msg += "; greeting email sent, check your inbox."
        except Exception as exc:
            logger.info("Greeting email failed: %s", str(exc))
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


def existing_subscriber(email: str) -> Tuple[bool, bool]:
    """Return (exists, is_subscribed) tuple.

    Returns:
      (True, True): subscriber exists and is subscribed.
      (True, False): subscriber exists but is unsubscribed.
      (False, False): subscriber does not exist.

    Raises:
      InvalidEmailError: when email is invalid.
      DependencyError: when `requests` is unavailable.
      ConfigError: when mailgun env configs are missing.
      MailgunError: for network/API errors.
    """
    sanitized_email, requests, api_key, list_name, domain_name = _prepare_mailgun(email)
    url = _member_url(list_name, domain_name, sanitized_email)

    try:
        resp = requests.get(url, auth=("api", api_key), timeout=8)
    except requests.RequestException as exc:
        logger.info("Trying to check if existing_subscriber, errored out with request error: %s", exc)
        raise MailgunError(f"Request error: {exc}")

    if resp.status_code == 200:
        try:
            member_data = resp.json().get("member", {})
            is_subscribed = member_data.get("subscribed", False)
            logger.info("Subscriber exists: %s, subscribed: %s", sanitized_email, is_subscribed)
            return True, is_subscribed
        except Exception as exc:
            logger.info("Error parsing member data: %s", exc)
            # If we can't parse, assume subscribed for backward compatibility
            return True, True
    elif resp.status_code == 404:
        return False, False
    elif resp.status_code == 429:
        logger.info("Trying to check if existing_subscriber, errored out with: Too many requests")
        raise MailgunError("Too many requests")

    try:
        detail = resp.json()
    except Exception:
        detail = getattr(resp, 'text', str(resp))

    logger.info("existing_subscriber Mailgun error (%s): %s", resp.status_code, detail)
    raise MailgunError(f"Mailgun error ({resp.status_code}): {detail}")


def send_greeting_mail(email: str) -> Tuple[bool, str]:
    """Send a small confirmation email to `email` via Mailgun.

    Returns (True, message) on success or (False, error_message) on failure.
    """
    try:
        sanitized_email, requests, api_key, list_name, domain_name = _prepare_mailgun(email)
    except (InvalidEmailError, DependencyError, ConfigError, MailgunError) as exc:
        return False, str(exc)

    from_addr = f"{list_name}@{domain_name}".strip()
    url = f"https://api.mailgun.net/v3/{domain_name}/messages"
    
    template_dir = pathlib.Path(__file__).parents[1] / "templates"
    css_path = template_dir / "greetingMail.css"
    html_path = template_dir / "greetingMail.html"
    
    if not css_path.exists() or not html_path.exists():
        msg = f"greeting templates missing: {html_path} or {css_path}"
        logger.info(msg)
        raise ConfigError(msg)
    try:
        css = css_path.read_text()
        html_template = html_path.read_text()
        html = html_template.replace("{{ css }}", css)
    except Exception as exc:
        logger.info("Error loading greeting templates: %s", exc)
        raise ConfigError(f"Error loading greeting templates: {exc}")

    text = (
        "HackerNews Digest - Subscription confirmed\n\n"
        "Thanks for subscribing to the HackerNews Digest. "
        "To ensure delivery, add this sender to your contacts list."
    )

    data = {
        "from": from_addr,
        "to": sanitized_email,
        "subject": "HackerNews Digest: Subscription confirmed",
        "text": text,
        "html": html,
    }

    try:
        resp = requests.post(url, auth=("api", api_key), data=data, timeout=10)
    except requests.RequestException as exc:
        msg = f"Request error when sending email: {exc}"
        logger.info(msg)
        return False, msg

    if resp.status_code == 200:
        msg = f"Greeting email sent to {sanitized_email}"
        logger.info(msg)
        return True, msg

    try:
        detail = resp.json()
    except Exception:
        detail = getattr(resp, 'text', str(resp))

    msg = f"Mailgun send error ({resp.status_code}): {detail}"
    logger.info(msg)
    return False, msg