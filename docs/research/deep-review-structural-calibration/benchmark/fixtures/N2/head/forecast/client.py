"""Forecast provider access: one place that knows both payload versions and the error policy."""

from typing import Protocol

from forecast.models import Forecast, ForecastUnavailable


class Transport(Protocol):
    def get_json(self, path: str) -> dict: ...


class ForecastClient:
    def __init__(self, transport: Transport):
        self._transport = transport

    def forecast(self, station: str) -> Forecast:
        try:
            payload = self._transport.get_json(f"/stations/{station}/forecast")
        except (OSError, TimeoutError, ValueError) as error:
            raise ForecastUnavailable(station) from error
        try:
            return self._translate(station, payload)
        except (KeyError, IndexError, TypeError) as error:
            raise ForecastUnavailable(station) from error

    def _translate(self, station, payload):
        version = payload.get("version", 1)
        if version == 1:
            return Forecast(station, payload["max"], payload["min"], payload.get("rain", 0.0))
        if version == 2:
            today = payload["days"][0]
            return Forecast(
                station,
                today["temperature"]["high"],
                today["temperature"]["low"],
                today["precipitation"]["mm"],
            )
        raise ForecastUnavailable(station)
