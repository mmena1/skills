import unittest

from forecast.alerts import frost_warning
from forecast.client import ForecastClient
from forecast.models import Forecast, ForecastUnavailable
from forecast.report import daily_summary


class FakeTransport:
    def __init__(self, payloads):
        self.payloads = payloads

    def get_json(self, path):
        payload = self.payloads[path]
        if isinstance(payload, Exception):
            raise payload
        return payload


V1 = {"version": 1, "max": 9.0, "min": -1.0, "rain": 0.4}
V2 = {"version": 2, "days": [{"temperature": {"high": 12.0, "low": 3.0}, "precipitation": {"mm": 0.0}}]}


class ClientTests(unittest.TestCase):
    def client(self, **payloads):
        return ForecastClient(FakeTransport({f"/stations/{k}/forecast": v for k, v in payloads.items()}))

    def test_translates_both_versions(self):
        client = self.client(a=V1, b=V2)
        self.assertEqual(client.forecast("a"), Forecast("a", 9.0, -1.0, 0.4))
        self.assertEqual(client.forecast("b"), Forecast("b", 12.0, 3.0, 0.0))

    def test_transport_and_payload_failures_become_unavailable(self):
        client = self.client(a=TimeoutError(), b={"version": 2, "days": []}, c={"version": 9})
        for station in "abc":
            with self.assertRaises(ForecastUnavailable):
                client.forecast(station)

    def test_callers(self):
        client = self.client(a=V1, b=OSError())
        self.assertEqual(frost_warning(client, "a"), "Frost risk at a: low -1.0 C")
        self.assertEqual(daily_summary(client, ["a", "b"]), ["a: -1.0 to 9.0 C, 0.4 mm", "b: no forecast"])


if __name__ == "__main__":
    unittest.main()
