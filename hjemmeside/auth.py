"""Login, passwordkontrol og bearer tokens til API'et.

Alle aktive kontaktpersoner har samme adgang. Der er ingen roller eller
begrænsning til egne borgere i denne prototype.
"""

import os
import time

from apiflask import HTTPTokenAuth
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from werkzeug.security import check_password_hash

from database.kontaktperson_db import get_kontaktperson, get_login_kontaktperson

TOKEN_LIFETIME_SECONDS = 30 * 60
secret = os.environ.get("JWT_SECRET_KEY", "")
if len(secret) < 32:
    raise RuntimeError("Sæt JWT_SECRET_KEY i .env til en tilfældig værdi på mindst 32 tegn.")
SECRET_KEY = OctKey.import_key(secret)
REQUIRED_CLAIMS = jwt.JWTClaimsRegistry(
    exp={"essential": True}, sub={"essential": True},
    aud={"essential": True, "value": "pillpilot-personale-enkel"}
)
auth = HTTPTokenAuth(scheme="Bearer")


def check_login(
    password: str, email: str | None = None, kontaktperson_id: int | None = None
) -> dict | None:
    """Returnér en aktiv kontaktperson, hvis password passer, ellers None."""
    user = get_login_kontaktperson(email, kontaktperson_id)
    if user is None or not user["aktiv"]:
        return None
    try:
        if not check_password_hash(user["password_hash"], password):
            return None
    except (ValueError, TypeError):
        return None
    return get_kontaktperson(user["kontaktperson_id"])


def create_token(kontaktperson_id: int) -> str:
    """Lav et token med kontaktpersonens id og et udløbstidspunkt."""
    payload = {
        "sub": str(kontaktperson_id), "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS,
        "aud": "pillpilot-personale-enkel",
    }
    return jwt.encode({"alg": "HS256"}, payload, SECRET_KEY)


def read_token(token: str) -> int | None:
    """Kontrollér signatur, udløb og modtager. Gamle enhedstokens accepteres ikke."""
    try:
        claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"]).claims
        REQUIRED_CLAIMS.validate(claims)
        if not isinstance(claims["sub"], str):
            return None
        kontaktperson_id = int(claims["sub"])
        return kontaktperson_id if kontaktperson_id > 0 else None
    except (JoseError, ValueError, TypeError, KeyError):
        return None


@auth.verify_token
def verify_token(token: str) -> dict | None:
    """Kontrollér også i databasen, at kontaktpersonen stadig er aktiv."""
    kontaktperson_id = read_token(token)
    if kontaktperson_id is None:
        return None
    user = get_kontaktperson(kontaktperson_id)
    if user is None or not user["aktiv"]:
        return None
    return user
