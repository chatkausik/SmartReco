import re

# Dependency-free email check (avoids pulling in email-validator for "keep auth simple").
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email)) and len(email) <= 255
