# Frost watch

Sends frost warnings and daily summaries for orchard weather stations.

The upstream forecast provider serves two payload versions. Version 1 is the legacy flat payload; version 2 nests daily values. Stations migrate one at a time, so both versions stay in production until the provider retires version 1. Provider and transport failures must surface as `ForecastUnavailable`; callers never see transport exceptions or raw payloads.

Python 3.11 standard library only. Run `python -m unittest discover -s tests`.
