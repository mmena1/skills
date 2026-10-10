import json
import urllib.request


class HttpTransport:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_json(self, path: str) -> dict:
        with urllib.request.urlopen(self._base_url + path, timeout=self._timeout) as response:
            return json.loads(response.read().decode("utf-8"))
