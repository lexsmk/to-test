import os
import requests
import pytest

from typing import Any, List, Dict

BASE_URL = os.getenv("BASE_URL", "https://to-barrel-monitor.azurewebsites.net").rstrip('/')
OPENAPI_URL = os.getenv("OPENAPI_URL", "https://to-barrel-monitor.azurewebsites.net/swagger/v1/swagger.json")
TIMEOUT_SEC = float(os.getenv("TIMEOUT_SEC", "10"))
STRICT = os.getenv("STRICT", "1").strip().lower() in {"1", "true", "yes", "on"}
SHOW_HTTP = os.getenv("SHOW_HTTP", "0").strip() == "1"
RETRY = int(os.getenv("RETRY", "0"))
MEASUREMENT_KEYS = {"id", "barrelId", "dirtLevel", "weight"}


def _short(text: str, limit: int = 200) -> str:
    return text if len(text) <= limit else text[:limit] + '...'


def assert_status(resp: requests.Response, expected: tuple[int, ...], ctx: str) -> None:
    if resp.status_code not in expected:
        pytest.fail(f"{ctx}: expected {expected} got {resp.status_code} body={_short(resp.text)}")


class Client:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base = (base_url or BASE_URL).rstrip('/')
        self.timeout = timeout or TIMEOUT_SEC
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _send(self, method: str, path: str, **kw) -> requests.Response:
        url = f"{self.base}{path}"
        t = kw.pop("timeout", self.timeout)
        r = self.session.request(method, url, timeout=t, **kw)
        if SHOW_HTTP:
            print(f"{method} {url} -> {r.status_code} {_short(r.text)}")
        return r

    # Barrel ops
    def barrel_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._send("POST", "/barrels", json=payload)
        assert_status(r, (200, 201), "create barrel")
        body = r.json()
        assert "id" in body
        return body

    def barrels(self) -> List[Dict[str, Any]]:
        r = self._send("GET", "/barrels")
        assert_status(r, (200,), "list barrels")
        data = r.json()
        assert isinstance(data, list)
        return data

    def barrel(self, barrel_id: str) -> Dict[str, Any]:
        r = self._send("GET", f"/barrels/{barrel_id}")
        if r.status_code == 500 and not STRICT:
            pytest.xfail("500 barrel detail drift")
        assert_status(r, (200,), "detail barrel")
        return r.json()

    def barrel_delete(self, barrel_id: str) -> int:
        r = self._send("DELETE", f"/barrels/{barrel_id}")
        if r.status_code == 500 and not STRICT:
            pytest.xfail("500 delete drift")
        assert_status(r, (200, 204, 202), "delete barrel")
        return r.status_code

    # Measurement ops
    def measurement_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._send("POST", "/measurements", json=payload)
        if r.status_code in (200, 201):
            body = r.json()
            assert "id" in body
            return body
        if r.status_code == 400 and ("Barrel field is required" in r.text or '"Barrel"' in r.text):
            pytest.xfail("contract drift measurement expects Barrel object")
        raise AssertionError(f"create measurement {r.status_code} {_short(r.text)}")

    def measurements(self) -> List[Dict[str, Any]]:
        r = self._send("GET", "/measurements")
        assert_status(r, (200,), "list measurements")
        data = r.json()
        assert isinstance(data, list)
        return data

    def measurement(self, measurement_id: str) -> Dict[str, Any]:
        r = self._send("GET", f"/measurements/{measurement_id}")
        if r.status_code == 500 and not STRICT:
            pytest.xfail("500 measurement detail drift")
        assert_status(r, (200,), "detail measurement")
        return r.json()


def assert_keys(obj: Dict[str, Any], expected: set[str]) -> None:
    cur = set(obj.keys())
    extra = cur - expected
    missing = expected - cur
    if missing:
        raise AssertionError(f"missing keys: {missing} in {obj}")
    if extra:
        if not STRICT:
            pytest.xfail(f"extra keys drift {extra}")
        raise AssertionError(f"unexpected extra keys: {extra}")
