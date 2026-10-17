import pytest
from fastapi.testclient import TestClient

from app.main import app, store

client = TestClient(app)

SENSOR = "room-01-temperature"


@pytest.fixture(autouse=True)
def clean_store():
    # The store is global, so reset it before every test
    store.clear()


def make_reading(
    event_id="event-001",
    value=22.4,
    observed_at="2026-10-12T10:00:00Z",
    sensor_id=SENSOR,
):
    return {
        "event_id": event_id,
        "sensor_id": sensor_id,
        "value": value,
        "observed_at": observed_at,
    }


def post(payload):
    return client.post("/readings", json=payload)


def get_latest(sensor_id=SENSOR):
    return client.get(f"/sensors/{sensor_id}/latest")


def test_accept_and_read_latest():
    response = post(make_reading())
    assert response.status_code == 201
    assert response.json() == {"status": "accepted"}

    latest = get_latest()
    assert latest.status_code == 200
    assert latest.json() == make_reading()


def test_exact_duplicate_returns_200_and_keeps_state():
    post(make_reading())

    response = post(make_reading())
    assert response.status_code == 200
    assert response.json() == {"status": "duplicate"}
    assert get_latest().json()["event_id"] == "event-001"


def test_conflicting_event_id_returns_409_and_keeps_state():
    post(make_reading())

    response = post(make_reading(value=25.0))
    assert response.status_code == 409
    assert get_latest().json()["value"] == 22.4


def test_event_id_is_unique_across_sensors():
    post(make_reading())

    response = post(make_reading(sensor_id="room-02-temperature"))
    assert response.status_code == 409
    assert get_latest("room-02-temperature").status_code == 404


def test_older_reading_does_not_replace_latest():
    post(make_reading(event_id="event-001", observed_at="2026-10-12T10:00:00Z"))

    response = post(make_reading(event_id="event-002", observed_at="2026-10-12T09:59:00Z"))
    assert response.status_code == 201
    assert get_latest().json()["event_id"] == "event-001"

    # The old reading was stored: repeating it is a duplicate, not a new event
    repeat = post(make_reading(event_id="event-002", observed_at="2026-10-12T09:59:00Z"))
    assert repeat.status_code == 200


def test_equal_time_keeps_first_accepted_reading():
    post(make_reading(event_id="event-001", value=20.0))
    post(make_reading(event_id="event-002", value=30.0))

    assert get_latest().json()["event_id"] == "event-001"


def test_int_and_float_values_are_the_same():
    post(make_reading(value=22.0))

    response = post(make_reading(value=22))
    assert response.status_code == 200
    assert response.json() == {"status": "duplicate"}


def test_fractional_seconds_do_not_change_the_moment():
    post(make_reading(observed_at="2026-10-12T10:00:00Z"))

    response = post(make_reading(observed_at="2026-10-12T10:00:00.000Z"))
    assert response.status_code == 200
    assert response.json() == {"status": "duplicate"}


def test_unknown_sensor_returns_404_with_json():
    response = get_latest("no-such-sensor")
    assert response.status_code == 404
    assert "detail" in response.json()


INVALID_PAYLOADS = [
    pytest.param({**make_reading(), "value": "22.4"}, id="value-is-string"),
    pytest.param({**make_reading(), "value": True}, id="value-is-bool"),
    pytest.param({**make_reading(), "value": None}, id="value-is-null"),
    pytest.param({**make_reading(), "event_id": ""}, id="empty-event-id"),
    pytest.param({**make_reading(), "event_id": "   "}, id="blank-event-id"),
    pytest.param({**make_reading(), "sensor_id": ""}, id="empty-sensor-id"),
    pytest.param({**make_reading(), "observed_at": "2026-10-12T10:00:00"}, id="time-without-z"),
    pytest.param({**make_reading(), "observed_at": "2026-10-12T10:00:00+00:00"}, id="time-with-offset"),
    pytest.param({**make_reading(), "observed_at": "2026-13-45T10:00:00Z"}, id="time-not-a-real-date"),
    pytest.param({**make_reading(), "observed_at": 1760263200}, id="time-is-number"),
    pytest.param({**make_reading(), "extra": 1}, id="unknown-field"),
    pytest.param(
        {k: v for k, v in make_reading().items() if k != "value"}, id="missing-field"
    ),
]


@pytest.mark.parametrize("payload", INVALID_PAYLOADS)
def test_invalid_request_returns_422_and_changes_nothing(payload):
    response = post(payload)
    assert response.status_code == 422
    assert "detail" in response.json()

    # Nothing was stored for this sensor...
    assert get_latest().status_code == 404
    # ...and the event_id is still free, so a valid request is "accepted"
    assert post(make_reading()).status_code == 201


@pytest.mark.parametrize("bad_number", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_value_returns_422_and_changes_nothing(bad_number):
    # json= in httpx refuses NaN, so send the raw body
    body = (
        '{"event_id": "event-001", "sensor_id": "room-01-temperature", '
        f'"value": {bad_number}, "observed_at": "2026-10-12T10:00:00Z"}}'
    )
    response = client.post(
        "/readings", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert get_latest().status_code == 404


def test_full_scenario_from_the_task():
    r = post(make_reading("event-001", 22.4, "2026-10-12T10:00:00Z"))
    assert r.status_code == 201
    assert get_latest().json()["event_id"] == "event-001"

    r = post(make_reading("event-001", 22.4, "2026-10-12T10:00:00Z"))
    assert (r.status_code, r.json()) == (200, {"status": "duplicate"})
    assert get_latest().json()["event_id"] == "event-001"

    r = post(make_reading("event-002", 21.8, "2026-10-12T09:59:00Z"))
    assert r.status_code == 201
    assert get_latest().json()["event_id"] == "event-001"

    r = post(make_reading("event-001", 25.0, "2026-10-12T10:00:00Z"))
    assert r.status_code == 409
    assert get_latest().json()["event_id"] == "event-001"

    r = post(make_reading("event-003", 23.0, "2026-10-12T10:01:00Z"))
    assert r.status_code == 201
    assert get_latest().json()["event_id"] == "event-003"