import unittest

from forecast.models import ForecastUnavailable


class ModelTests(unittest.TestCase):
    def test_unavailable_names_station(self):
        self.assertEqual(ForecastUnavailable("orchard-3").station, "orchard-3")


if __name__ == "__main__":
    unittest.main()
