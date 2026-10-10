from dataclasses import dataclass


@dataclass(frozen=True)
class Forecast:
    station: str
    high_c: float
    low_c: float
    precipitation_mm: float


class ForecastUnavailable(Exception):
    """The forecast for a station could not be obtained or understood."""

    def __init__(self, station):
        super().__init__(f"forecast unavailable for {station}")
        self.station = station
