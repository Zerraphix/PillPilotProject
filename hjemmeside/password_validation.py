"""Fælles regler for nye passwords."""

import re

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
PASSWORD_PATTERN = rf"(?=.*[A-ZÆØÅ])(?=.*[a-zæøå])(?=.*[0-9]).{{{PASSWORD_MIN_LENGTH},{PASSWORD_MAX_LENGTH}}}"
PASSWORD_ERROR = (
    f"Password skal være {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} tegn og indeholde mindst "
    "ét stort bogstav, ét lille bogstav og ét tal."
)


def validate_password(password: str) -> None:
    """Kontrollér et nyt password før oprettelse eller ændring."""
    if not isinstance(password, str) or re.fullmatch(PASSWORD_PATTERN, password) is None:
        raise ValueError(PASSWORD_ERROR)
