
import hashlib

from apiflask import APIKeyHeaderAuth
from database import pilledispenser_db

device_auth = APIKeyHeaderAuth(
    name="DeviceAuth",
    param_name="X-Device-Key"
)


@device_auth.verify_token
def verify_device(api_key: str):
    """Godkend en enhed uden kontaktperson-login."""

    if not api_key or len(api_key) < 40 or len(api_key) > 256:
        return None

    key_hash = hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()

    return pilledispenser_db.get_enhed_by_key_hash(
        key_hash
    )
