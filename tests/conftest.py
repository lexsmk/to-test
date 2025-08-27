import json
import pytest
import hashlib
import uuid
import logging
import sys
import requests

from pathlib import Path
from src.client import Client, OPENAPI_URL, STRICT

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_DRIFTS: list[str] = []

SNAPSHOT_FILE = Path(__file__).parent / 'openapi.snapshot'

def _hash_spec(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]

@pytest.fixture(scope="session")
def openapi_spec():
    if not OPENAPI_URL:
        pytest.fail("OPENAPI_URL environment variable is required")
    resp = requests.get(OPENAPI_URL, timeout=15)
    if resp.status_code != 200:
        pytest.fail(f"failed to download OpenAPI spec {OPENAPI_URL} -> {resp.status_code}")
    raw = resp.content
    try:
        (Path.cwd() / 'openapi.remote.cached.json').write_bytes(raw)
    except Exception as e:
        logging.getLogger('fixtures').warning(f"could not cache remote spec: {e}")
    spec = json.loads(raw)
    current = _hash_spec(raw)
    if SNAPSHOT_FILE.exists():
        saved = SNAPSHOT_FILE.read_text().strip()
        if saved != current:
            _DRIFTS.append(f"openapi hash drift: was {saved} now {current}")
            if STRICT.lower() in {"1","true","yes","on"}:
                pytest.fail(f"OpenAPI snapshot drift (expected {saved} got {current})")
    else:
        SNAPSHOT_FILE.write_text(current, encoding='utf-8')
    return spec

@pytest.fixture(scope="session", autouse=True)
def _ensure_openapi_snapshot(openapi_spec):
    """Force evaluation of openapi_spec so snapshot file is always created."""
    return None

def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    if _DRIFTS and STRICT:
        print("DRIFT:")
        for d in _DRIFTS:
            print(" -", d)

def pytest_configure(config: pytest.Config):
    config.addinivalue_line("markers", "contract: contract tests")
    config.addinivalue_line("markers", "behavior: system behavior")
    config.addinivalue_line("markers", "robustness: robustness / negative cases")

logger = logging.getLogger("fixtures")

@pytest.fixture(scope="module")
def client() -> Client:
    return Client()

@pytest.fixture(autouse=True, scope="module")
def _healthcheck(client: Client):
    try:
        client.barrels()
    except Exception as exc:
        pytest.fail(f"healthcheck failed {exc}")

@pytest.fixture()
def barrel_factory(client: Client, request: pytest.FixtureRequest):
    created: list[str] = []

    def make(**override):
        payload = {"qr": f"qr-{uuid.uuid4()}", "rfid": f"rfid-{uuid.uuid4()}", "nfc": f"nfc-{uuid.uuid4()}"}
        payload.update(override)
        barrel = client.barrel_create(payload)
        created.append(barrel["id"])
        return barrel

    def fin():
        for bid in created:
            resp = client._send('DELETE', f'/barrels/{bid}')
            if resp.status_code not in (200, 202, 204, 404):
                pytest.fail(f"cleanup delete barrel {bid} -> {resp.status_code}")
    request.addfinalizer(fin)
    return make

