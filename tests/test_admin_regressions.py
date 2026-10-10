"""Admin write-path regressions. Requires dependencies from requirements-dev.txt."""
import pytest
import models
import supa
from app import create_app


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.setattr(supa, 'select', lambda *a, **k: [])
    monkeypatch.setattr(supa, 'insert', lambda *a, **k: {'id': 'fake'})
    monkeypatch.setattr(models, 'get_user_by_id', lambda uid: {'id': uid, 'is_admin': True})
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 'admin'
        sess['is_admin'] = True
    return client


def test_store_settings_are_written_together(admin_client, monkeypatch):
    captured = []
    monkeypatch.setattr(models, 'save_settings', lambda values: captured.append(values) or True)
    response = admin_client.post('/admin/settings', data={
        'store_name': 'Flower Shop', 'hero_headline': 'Handmade', 'processing_buffer': '3',
    })
    assert response.status_code == 302
    assert len(captured) == 1
    assert captured[0]['store_name'] == 'Flower Shop'
    assert captured[0]['hero_headline'] == 'Handmade'


def test_new_product_starts_listed_by_default(admin_client, monkeypatch):
    response = admin_client.get('/admin/products/new')
    assert response.status_code == 200
    assert b'name="is_listed" checked' in response.data


def test_invalid_product_price_is_handled_without_500(admin_client):
    response = admin_client.post('/admin/products/new', data={
        'title': 'Test Gift', 'price': 'not a price', 'availability_mode': 'READY_TO_SHIP',
    })
    assert response.status_code == 200
    assert b'not a price' in response.data


def test_failed_coupon_creation_shows_error(admin_client, monkeypatch):
    monkeypatch.setattr(models, 'create_coupon', lambda data: None)
    response = admin_client.post('/admin/coupons/new', data={
        'code': 'NOPE', 'discount_percent': '10', 'max_uses': '10',
    })
    assert response.status_code == 302
    with admin_client.session_transaction() as sess:
        assert any(category == 'error' for category, _ in sess.get('_flashes', []))


def test_system_health_reports_migration_gap(admin_client, monkeypatch):
    def probe(table, columns):
        if table == 'collections': raise supa.SupabaseError('HTTP 404')
        return True
    monkeypatch.setattr(supa, 'probe_table', probe)
    response = admin_client.get('/admin/system-health')
    assert response.status_code == 200
    assert b'Collections' in response.data
    assert b'HTTP 404' in response.data
