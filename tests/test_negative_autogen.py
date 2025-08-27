import itertools
import json
import os
import uuid
import pytest
import requests
from src.client import OPENAPI_URL, Client

# Auto-generated negative payload cases based on OpenAPI required/minLength rules.
# Strategy:
# 1. For each schema, build a valid base object (synthetic) then derive mutations:
#    a) remove each required property one at a time
#    b) for each string property with minLength>=1 set to '' and to whitespace
# 2. POST endpoints only (Barrel, Measurement) mapped from schemas.
# 3. Each mutation must be rejected with 4xx (not 2xx).
#
# Assumptions:
# - Measurement requires an existing barrelId -> we create a barrel first for base payload.
# - API returns 400/422 on validation failure (relaxed set per existing tests).
# - If the backend erroneously accepts an invalid payload (2xx) we fail explicitly.

_spec = requests.get(OPENAPI_URL, timeout=15).json()
_components = _spec.get('components', {}).get('schemas', {})

SCHEMA_TO_ENDPOINT = {
    'Barrel': '/barrels',
    'Measurement': '/measurements',
}

STRING_FALLBACK = 'x'


def _example_value(prop_name: str, schema: dict):
    t = schema.get('type')
    fmt = schema.get('format')
    if t == 'string':
        if fmt == 'uuid':
            return str(uuid.uuid4())
        return f"{prop_name}-" + STRING_FALLBACK
    if t == 'number':
        return 1.0
    if t == 'integer':
        return 1
    return STRING_FALLBACK


def _base_valid_objects(client: Client):
    barrel_base = {}
    barrel_schema = _components['Barrel']
    for p in barrel_schema['required']:
        barrel_base[p] = _example_value(p, barrel_schema['properties'][p])
    barrel_base.update({k: f"{k}-{uuid.uuid4()}" for k in barrel_base})
    barrel_created = client.barrel_create(barrel_base.copy())

    measurement_schema = _components['Measurement']
    measurement_base = {}
    for p in measurement_schema['required']:
        if p == 'barrelId':
            measurement_base[p] = barrel_created['id']
        else:
            measurement_base[p] = _example_value(p, measurement_schema['properties'][p])
    return barrel_base, measurement_base


def _mutations(schema_name: str, base_obj: dict, schema: dict):
    required = schema.get('required', [])
    props = schema.get('properties', {})
    for req in required:
        mutated = base_obj.copy()
        mutated.pop(req, None)
        yield f"missing_{req}", mutated
    for name, prop in props.items():
        if prop.get('type') == 'string' and prop.get('minLength', 0) >= 1:
            for variant, label in [("", "empty"), (" \t", "ws")]:
                mutated = base_obj.copy()
                mutated[name] = variant
                yield f"{name}_{label}", mutated


_cases = []  # хз(endpoint, case_name, payload)
for schema_name, endpoint in SCHEMA_TO_ENDPOINT.items():
    schema = _components.get(schema_name)
    if not schema:
        continue
    _cases.append((schema_name, endpoint))


@pytest.mark.robustness
@pytest.mark.parametrize('schema_name,endpoint', _cases)
def test_negative_autogen(schema_name: str, endpoint: str, client: Client):
    barrel_base, measurement_base = _base_valid_objects(client)
    base = barrel_base if schema_name == 'Barrel' else measurement_base
    schema = _components[schema_name]
    seen_hashes = set()
    mutations = list(_mutations(schema_name, base, schema))
    assert mutations, 'no mutations generated'
    for case_name, payload in mutations:
        key = json.dumps(payload, sort_keys=True)
        if key in seen_hashes:
            continue
        seen_hashes.add(key)
        r = client._send('POST', endpoint, json=payload)
        if r.status_code in (200, 201):
            pytest.fail(f"accepted invalid payload {schema_name}/{case_name} -> {r.status_code} {r.text[:120]}")
        assert r.status_code in (400, 422), f"unexpected status {r.status_code} for {schema_name}/{case_name}"
