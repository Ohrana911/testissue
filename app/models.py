import re
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator

GLOBAL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

class AcceptRequest(BaseModel):

    model_config = ConfigDict(extra='forbid')

    event_id: str = Field(min_length=1)
    sensor_id: str = Field(min_length=1)
    value: StrictInt | Annotated[StrictFloat, Field(allow_inf_nan=False)]
    observed_at: datetime

    @field_validator('event_id', 'sensor_id')
    @classmethod
    def is_not_empty(cls, id_arg: str) -> str:
        if not id_arg.strip():
            raise ValueError('not empty or any whitespace')
        return id_arg

    @field_validator('observed_at', mode="before")
    @classmethod
    def time_checker(cls, obs):
        if not isinstance(obs, str) or not GLOBAL_RE.match(obs):
            raise ValueError('must be like year-month-day-daytime-timezone')
        try:
            return datetime.fromisoformat(obs)
        except ValueError:
            raise ValueError('not valid date and time')
