"""Product write diagnostics (offline; no real Supabase credentials needed)."""
import pytest
import supa


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload

    def json(self):
        return self.payload


def _post(monkeypatch, status, payload):
    monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'fake-test-key')
    monkeypatch.setattr(supa._http, 'request', lambda *a, **k: FakeResponse(status, payload))
    with pytest.raises(supa.SupabaseError) as err:
        supa.insert('products', {'title': 'Flower', 'price': 100, 'image_alt_texts': []})
    return err.value


def test_missing_product_column_has_actionable_admin_diagnostic(monkeypatch):
    exc = _post(monkeypatch, 400, {
        'code': 'PGRST204',
        'message': "Could not find the 'image_alt_texts' column of 'products' in the schema cache",
        'hint': None,
        'details': None,
    })
    assert 'HTTP 400' in str(exc)
    assert 'PGRST204' not in str(exc)  # storefront error paths don't expose details
    assert 'PGRST204' in exc.admin_detail
    assert 'image_alt_texts' in exc.admin_detail
    assert '012_product_insert_repair.sql' in exc.admin_detail


def test_foreign_key_error_is_not_mistaken_for_missing_migration(monkeypatch):
    exc = _post(monkeypatch, 400, {
        'code': '23503', 'message': 'insert violates foreign key constraint',
    })
    assert 'selected category' in exc.admin_detail.lower()
    assert 'repair.sql' not in exc.admin_detail


def test_permissions_error_points_to_server_credentials(monkeypatch):
    exc = _post(monkeypatch, 403, {
        'code': '42501', 'message': 'permission denied for table products',
    })
    assert 'SUPABASE_SERVICE_ROLE_KEY' in exc.admin_detail


def test_database_error_limits_untrusted_text(monkeypatch):
    exc = _post(monkeypatch, 400, {
        'code': 'PGRST204', 'message': 'bad ' * 1000,
    })
    assert len(exc.backend_message) <= 240
    assert '\n' not in exc.admin_detail
