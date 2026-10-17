from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import AcceptRequest
from app.storage import Service

app = FastAPI()
store = Service()

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Do not echo the raw input back: values like NaN are not valid JSON
    errors = [
        {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.post("/readings")
def post_reading(reading: AcceptRequest) -> JSONResponse:
    result = store.add(reading)
    if result == "accepted":
        return JSONResponse(status_code=201, content={"status": "accepted"})
    if result == "duplicate":
        return JSONResponse(status_code=200, content={"status": "duplicate"})
    return JSONResponse(
        status_code=409,
        content={"detail": "event_id already exists with different data"},
    )


@app.get("/sensors/{sensor_id}/latest")
def get_latest(sensor_id: str) -> dict:
    reading = store.get_latest(sensor_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings for this sensor")
    return {
        "event_id": reading.event_id,
        "sensor_id": reading.sensor_id,
        "value": reading.value,
        "observed_at": reading.observed_at.isoformat().replace("+00:00", "Z"),
    }