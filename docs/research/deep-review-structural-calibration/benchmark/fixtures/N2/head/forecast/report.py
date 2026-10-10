from forecast.client import ForecastClient
from forecast.models import ForecastUnavailable


def daily_summary(client: ForecastClient, stations: list[str]) -> list[str]:
    lines = []
    for station in stations:
        try:
            forecast = client.forecast(station)
        except ForecastUnavailable:
            lines.append(f"{station}: no forecast")
            continue
        lines.append(f"{station}: {forecast.low_c:.1f} to {forecast.high_c:.1f} C, {forecast.precipitation_mm:.1f} mm")
    return lines
