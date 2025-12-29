import re

def validate_email(email: str) -> (bool, str):
    """return (True, sanitized_email) or (False, error_message)."""
    email = email.strip()
    if not email:
        return (False, "Email is required.")

    pattern = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    if not pattern.match(email):
        return (False, "Invalid email format.")

    return (True, email)