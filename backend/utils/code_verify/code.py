import secrets
import string


def generate_verification_code(length: int = 6) -> str:
    """Generate a random numeric code."""
    return "".join(secrets.choice(string.digits) for _ in range(length))
