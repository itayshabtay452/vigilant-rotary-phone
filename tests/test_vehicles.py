"""
Tests for the /vehicles/ router.

Covers: CRUD happy paths, input validation, pagination bounds,
plate-normalisation lookup, auth enforcement, and explicit-null rejection.
"""
import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PLATE = "1234567"
_VALID_PAYLOAD: dict = {
    "license_plate": _VALID_PLATE,
    "customer_name": "Jane Doe",
    "phone_number": "0501234567",
    "reason": "annual",
}


def _create(client: TestClient, overrides: dict | None = None) -> dict:
    payload = {**_VALID_PAYLOAD, **(overrides or {})}
    r = client.post("/vehicles/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ===========================================================================
# CRUD — happy paths
# ===========================================================================


def test_create_vehicle(client: TestClient) -> None:
    data = _create(client)
    assert data["license_plate"] == _VALID_PLATE
    assert data["status"] == "ticket_opened"
    assert data["reason"] == "annual"
    assert data["customer_name"] == "Jane Doe"
    assert "created_at" in data
    assert "updated_at" in data


def test_create_vehicle_with_eight_digit_plate(client: TestClient) -> None:
    data = _create(client, {"license_plate": "12345678"})
    assert data["license_plate"] == "12345678"


def test_create_vehicle_strips_plate_separators(client: TestClient) -> None:
    data = _create(client, {"license_plate": "123-45-67"})
    assert data["license_plate"] == "1234567"


def test_create_duplicate_across_hyphenated_variants_returns_409(client: TestClient) -> None:
    """Two plate inputs that differ only in embedded hyphens/spaces must
    collide on the same primary key, so the second create returns 409."""
    _create(client, {"license_plate": "1234567"})
    r = client.post(
        "/vehicles/",
        json={**_VALID_PAYLOAD, "license_plate": "123-45-67"},
    )
    assert r.status_code == 409


def test_list_vehicles(client: TestClient) -> None:
    _create(client)
    r = client.get("/vehicles/")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_vehicle(client: TestClient) -> None:
    _create(client)
    r = client.get(f"/vehicles/{_VALID_PLATE}")
    assert r.status_code == 200
    assert r.json()["license_plate"] == _VALID_PLATE


def test_update_vehicle(client: TestClient) -> None:
    _create(client)
    r = client.patch(f"/vehicles/{_VALID_PLATE}", json={"customer_name": "John Smith"})
    assert r.status_code == 200
    assert r.json()["customer_name"] == "John Smith"


def test_update_vehicle_reason(client: TestClient) -> None:
    _create(client)
    r = client.patch(f"/vehicles/{_VALID_PLATE}", json={"reason": "accident"})
    assert r.status_code == 200
    assert r.json()["reason"] == "accident"


def test_delete_vehicle(client: TestClient) -> None:
    _create(client)
    r = client.delete(f"/vehicles/{_VALID_PLATE}")
    assert r.status_code == 204
    assert client.get(f"/vehicles/{_VALID_PLATE}").status_code == 404


# ===========================================================================
# Plate normalisation
# ===========================================================================


def test_get_vehicle_case_insensitive(client: TestClient) -> None:
    _create(client)
    assert client.get(f"/vehicles/{_VALID_PLATE.lower()}").status_code == 200


def test_patch_vehicle_status_ready(client: TestClient) -> None:
    _create(client)
    r = client.patch(
        f"/vehicles/{_VALID_PLATE}", json={"status": "ready"}
    )
    assert r.status_code == 200


def test_delete_vehicle_case_insensitive(client: TestClient) -> None:
    _create(client)
    assert client.delete(f"/vehicles/{_VALID_PLATE.lower()}").status_code == 204


# ===========================================================================
# URL plate normalisation — path must strip the same separators as the body
# ===========================================================================


def test_get_vehicle_hyphenated_url(client: TestClient) -> None:
    _create(client, {"license_plate": "1234567"})
    r = client.get("/vehicles/123-45-67")
    assert r.status_code == 200
    assert r.json()["license_plate"] == "1234567"


def test_patch_vehicle_hyphenated_url(client: TestClient) -> None:
    _create(client, {"license_plate": "1234567"})
    r = client.patch("/vehicles/123-45-67", json={"status": "ready"})
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_delete_vehicle_hyphenated_url(client: TestClient) -> None:
    _create(client, {"license_plate": "1234567"})
    r = client.delete("/vehicles/123-45-67")
    assert r.status_code == 204
    assert client.get("/vehicles/1234567").status_code == 404


# ===========================================================================
# Conflict / not-found
# ===========================================================================


def test_create_duplicate_returns_409(client: TestClient) -> None:
    _create(client)
    r = client.post("/vehicles/", json=_VALID_PAYLOAD)
    assert r.status_code == 409


def test_get_not_found(client: TestClient) -> None:
    assert client.get("/vehicles/9999999").status_code == 404


def test_patch_not_found(client: TestClient) -> None:
    assert client.patch("/vehicles/9999999", json={"status": "ready"}).status_code == 404


def test_delete_not_found(client: TestClient) -> None:
    assert client.delete("/vehicles/9999999").status_code == 404


# ===========================================================================
# Input validation — create
# ===========================================================================


@pytest.mark.parametrize(
    "field,value",
    [
        ("license_plate", "ABC1234"),      # letters not allowed
        ("license_plate", "123456"),       # too short (6 digits)
        ("license_plate", "123456789"),    # too long (9 digits)
        ("customer_name", "Jane"),         # only one word
        ("customer_name", "Jane123 Doe"),  # contains digits
        ("customer_name", "Jane  Doe"),    # two spaces
        ("phone_number", "0511234567"),    # invalid 3rd digit
        ("phone_number", "050123456"),     # only 9 digits
        ("phone_number", "05012345678"),   # 11 digits
        ("phone_number", "0401234567"),    # does not start with 05
        ("reason", "unknown"),             # not in enum
    ],
)
def test_create_invalid_fields(client: TestClient, field: str, value: str) -> None:
    payload = {**_VALID_PAYLOAD, field: value}
    assert client.post("/vehicles/", json=payload).status_code == 422


def test_create_missing_reason_rejected(client: TestClient) -> None:
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "reason"}
    assert client.post("/vehicles/", json=payload).status_code == 422


# ===========================================================================
# Input validation — update (explicit null rejection)
# ===========================================================================


@pytest.mark.parametrize("field", ["customer_name", "phone_number", "status", "reason"])
def test_patch_explicit_null_rejected(client: TestClient, field: str) -> None:
    _create(client)
    r = client.patch(f"/vehicles/{_VALID_PLATE}", json={field: None})
    assert r.status_code == 422, f"Expected 422 for {field}=null, got {r.status_code}"


# ===========================================================================
# Pagination
# ===========================================================================


def _create_n(client: TestClient, n: int) -> None:
    for i in range(n):
        _create(client, {"license_plate": f"{1000000 + i}"})


def test_list_pagination_limit(client: TestClient) -> None:
    _create_n(client, 5)
    r = client.get("/vehicles/?limit=3")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_list_pagination_skip(client: TestClient) -> None:
    _create_n(client, 5)
    all_plates = [v["license_plate"] for v in client.get("/vehicles/").json()]
    skipped = [v["license_plate"] for v in client.get("/vehicles/?skip=2").json()]
    assert skipped == all_plates[2:]


def test_list_limit_over_max_rejected(client: TestClient) -> None:
    assert client.get("/vehicles/?limit=1001").status_code == 422


def test_list_limit_zero_rejected(client: TestClient) -> None:
    assert client.get("/vehicles/?limit=0").status_code == 422


def test_list_negative_skip_rejected(client: TestClient) -> None:
    assert client.get("/vehicles/?skip=-1").status_code == 422


# ===========================================================================
# Authentication
# ===========================================================================


def test_auth_passthrough_when_no_key_set(client: TestClient) -> None:
    """When ADMIN_API_KEY is empty, all requests pass through."""
    r = client.get("/vehicles/")
    assert r.status_code == 200


def test_auth_correct_key_accepted(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    r = client.get("/vehicles/", headers={"X-API-Key": "secret"})
    assert r.status_code == 200


def test_auth_wrong_key_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    r = client.get("/vehicles/", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == "ApiKey"


def test_auth_missing_key_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    r = client.get("/vehicles/")
    assert r.status_code == 401


# ===========================================================================
# _UTCDateTime — direct ORM write guard
# ===========================================================================


def test_utc_datetime_rejects_naive_bind_param() -> None:
    """_UTCDateTime.process_bind_param must refuse naive datetimes so they are
    never silently stored and later read back tagged as UTC."""
    from datetime import datetime

    from app.models.vehicle import _UTCDateTime

    col = _UTCDateTime()
    with pytest.raises(ValueError, match="Naive datetime"):
        col.process_bind_param(datetime(2026, 6, 1, 9, 0, 0), dialect=None)


def test_utc_datetime_accepts_aware_bind_param() -> None:
    """Timezone-aware datetimes must be normalised to naive UTC for storage."""
    from datetime import datetime, timezone

    from app.models.vehicle import _UTCDateTime

    col = _UTCDateTime()
    aware = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
    result = col.process_bind_param(aware, dialect=None)
    assert result is not None
    assert result.tzinfo is None
    assert result == datetime(2026, 6, 1, 9, 0, 0)
