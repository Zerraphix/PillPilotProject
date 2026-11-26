
from apiflask import APIBlueprint

from device_auth import device_auth

api = APIBlueprint(
    "enhed",
    __name__,
    url_prefix="/api/enhed"
)


@api.get("/test")
@api.auth_required(device_auth)
def test_enhed():
    """Test om en ESP32 er godkendt."""

    enhed = device_auth.current_user

    return {
        "message": "Enheden er godkendt",
        "enhed_id": enhed["enhed_id"]
    }
