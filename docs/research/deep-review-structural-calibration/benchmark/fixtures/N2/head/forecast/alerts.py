from forecast.client import ForecastClient

FROST_THRESHOLD_C = 0.5


def frost_warning(client: ForecastClient, station: str) -> str | None:
    forecast = client.forecast(station)
    if forecast.low_c <= FROST_THRESHOLD_C:
        return f"Frost risk at {station}: low {forecast.low_c:.1f} C"
    return None
