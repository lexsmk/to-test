import os
import uuid
import requests
import jsonschema
import pytest
from src.client import Client, OPENAPI_URL

resp = requests.get(OPENAPI_URL, timeout=15)
if resp.status_code != 200:
    raise RuntimeError(f"Failed to fetch OpenAPI spec {OPENAPI_URL} -> {resp.status_code}")
_spec = resp.json()

_cases: list[tuple[str, str]] = []
paths = _spec.get('paths', {})
for p, cfg in paths.items():
    if '{' in p:
        continue
    get_cfg = cfg.get('get') or {}
    responses = get_cfg.get('responses', {})
    r200 = responses.get('200') or {}
    content = r200.get('content', {})
    model = None
    for _mime, meta in content.items():
        sch = meta.get('schema') or {}
        if sch.get('type') == 'array':
            items = sch.get('items') or {}
            ref = items.get('$ref')
            if ref and ref.startswith('#/components/schemas/'):
                model = ref.split('/')[-1]
                break
    if model:
        _cases.append((p, model))

def _schema(name: str):
    return _spec['components']['schemas'][name]

@pytest.mark.contract
@pytest.mark.parametrize('path,model', _cases)
def test_openapi_list_shape(client: Client, path: str, model: str):
    """List endpoints return JSON arrays whose first element matches the declared item schema.

    If the collection is empty, seed minimal data (one entity) to assert the shape end‑to‑end.
    """
    r = client._send('GET', path)
    if r.status_code != 200:
        pytest.fail(f"{path} returned {r.status_code}")
    data = r.json()
    assert isinstance(data, list)
    if not data:
        if model == 'Barrel':
            client.barrel_create({
                'qr': f'qr-{uuid.uuid4()}',
                'rfid': f'rfid-{uuid.uuid4()}',
                'nfc': f'nfc-{uuid.uuid4()}'
            })
        elif model == 'Measurement':
            barrel = client.barrel_create({
                'qr': f'qr-{uuid.uuid4()}',
                'rfid': f'rfid-{uuid.uuid4()}',
                'nfc': f'nfc-{uuid.uuid4()}'
            })
            client.measurement_create({
                'barrelId': barrel['id'],
                'dirtLevel': 0.01,
                'weight': 1.23
            })
        r = client._send('GET', path)
        if r.status_code != 200:
            pytest.fail(f"{path} returned {r.status_code} post-seed")
        data = r.json()
        if not isinstance(data, list) or not data:
            pytest.skip('still empty after seed')
    jsonschema.validate(data[0], _schema(model))
