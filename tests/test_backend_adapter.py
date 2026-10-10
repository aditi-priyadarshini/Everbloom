"""Database adapter + public cache regressions. No credentials or Flask needed."""
import pytest
import supa
import models
from services import cache


class Response:
    status_code = 201
    content = b'[{}]'
    text = '[]'

    def __init__(self, value):
        self.value = value

    def json(self):
        return self.value


def test_settings_batch_upsert_is_one_request(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'fake-test-credential')
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response(kwargs['json'])

    monkeypatch.setattr(supa._http, 'request', request)
    assert models.save_settings({'store_name': 'Everbloom', 'hero_headline': 'Hello'})
    assert len(calls) == 1
    method, url, kwargs = calls[0]
    assert (method, url) == ('POST', 'https://test.supabase.co/rest/v1/settings')
    assert kwargs['params'] == {'on_conflict': 'key'}
    assert 'resolution=merge-duplicates' in kwargs['headers']['Prefer']
    assert len(kwargs['json']) == 2


def test_errors_not_disguised_as_empty_data(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'fake-test-credential')

    class Failure:
        status_code = 403
        text = 'permission denied'

    monkeypatch.setattr(supa._http, 'request', lambda *a, **k: Failure())
    with pytest.raises(supa.SupabaseError, match='HTTP 403'):
        supa.select('products')


def test_read_only_schema_probe(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'fake-test-credential')
    seen = []

    def request(method, url, **kwargs):
        seen.append((method, kwargs.get('params')))
        return Response([])

    monkeypatch.setattr(supa._http, 'request', request)
    assert supa.probe_table('products', 'id,image_alt_texts')
    assert seen == [('GET', {'select': 'id,image_alt_texts', 'limit': 0})]


def test_public_cache_invalidates_and_returns_isolated_copies(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('PUBLIC_CACHE_TTL', '30')
    cache.invalidate('test_catalogue')
    calls = []

    def load():
        calls.append(True)
        return [{'id': len(calls)}]

    first = cache.cached('test_catalogue', load)
    first[0]['id'] = 777
    assert cache.cached('test_catalogue', load) == [{'id': 1}]
    assert len(calls) == 1
    cache.invalidate('test_catalogue')
    assert cache.cached('test_catalogue', load) == [{'id': 2}]


def test_component_cost_uses_one_material_batch(monkeypatch):
    calls = []
    monkeypatch.setattr(models, 'get_component_bom', lambda cid: [
        {'material_id': 1, 'quantity_used': 2},
        {'material_id': 2, 'quantity_used': 3},
    ])

    def materials():
        calls.append(True)
        return [{'id': 1, 'cost_per_unit': 10}, {'id': 2, 'cost_per_unit': 5}]

    monkeypatch.setattr(models, 'get_raw_materials', materials)
    assert models.calculate_component_cost(1) == 35
    assert len(calls) == 1
