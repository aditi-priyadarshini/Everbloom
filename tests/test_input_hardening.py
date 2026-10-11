"""Admin numeric-input hardening and route-crash regressions (no live DB needed)."""
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
        sess['user_id'] = 'admin'; sess['is_admin'] = True
    return client


def _errors(client):
    with client.session_transaction() as sess:
        return [m for c, m in sess.get('_flashes', []) if c == 'error']


@pytest.mark.parametrize('raw', ['nan', 'NaN', 'inf', '-inf', 'Infinity', '1e999', '1e13', 'abc', '', ' ', '1,5'])
def test_flt_rejects_non_finite_and_garbage(raw):
    from routes.admin import _flt
    with pytest.raises(ValueError):
        _flt(raw, 'price')


@pytest.mark.parametrize('raw,expected', [('12.50', 12.5), (' 7 ', 7.0), ('0', 0.0), ('-3.25', -3.25), (5, 5.0)])
def test_flt_accepts_normal_numbers(raw, expected):
    from routes.admin import _flt
    assert _flt(raw) == expected


@pytest.mark.parametrize('raw', ['3.5', 'x', 'inf', '99999999999', ''])
def test_int_rejects_fractions_garbage_and_overflow(raw):
    from routes.admin import _int
    with pytest.raises(ValueError):
        _int(raw, 'stock')


def test_int_accepts_whole_numbers():
    from routes.admin import _int
    assert _int('12') == 12 and _int(' 3 ') == 3 and _int('4.0') == 4 and _int(0) == 0


def test_create_product_from_request_with_infinite_stock_is_a_clean_error(admin_client, monkeypatch):
    monkeypatch.setattr(models, 'get_custom_request', lambda r: {'id': r, 'status': 'quoted'})
    response = admin_client.post('/admin/custom-requests/9/create-product',
                                 data={'title': 'T', 'price': '10', 'stock': '1e999'})
    assert response.status_code == 302
    assert any('stock' in m.lower() for m in _errors(admin_client))


def test_variant_delete_without_product_id_does_not_crash_after_deleting(admin_client, monkeypatch):
    deleted = []
    monkeypatch.setattr(models, 'delete_variant', lambda vid: deleted.append(vid) or True)
    response = admin_client.post('/admin/variants/9/delete', data={})
    assert deleted == ['9']
    assert response.status_code == 302 and '/admin/products' in response.headers['Location']


def test_variant_delete_with_product_id_returns_to_that_product(admin_client, monkeypatch):
    monkeypatch.setattr(models, 'delete_variant', lambda vid: True)
    response = admin_client.post('/admin/variants/9/delete', data={'product_id': 'abc'})
    assert response.headers['Location'].endswith('/admin/products/abc/edit')


@pytest.mark.parametrize('qty,cost', [('0', '5'), ('-2', '5'), ('3', '-1'), ('nan', '1'), ('1', 'inf')])
def test_stock_purchase_rejects_bad_input_with_a_message_and_no_rpc(admin_client, monkeypatch, qty, cost):
    monkeypatch.setattr(models, 'add_expenditure', lambda d: pytest.fail('RPC must not be called'))
    response = admin_client.post('/admin/inventory/3/purchase', data={'quantity': qty, 'cost_per_unit': cost})
    assert response.status_code == 302
    assert _errors(admin_client)


def test_stock_purchase_valid_calls_rpc_once(admin_client, monkeypatch):
    calls = []
    monkeypatch.setattr(models, 'add_expenditure', lambda d: calls.append(d) or {'id': 1})
    admin_client.post('/admin/inventory/3/purchase', data={'quantity': '5', 'cost_per_unit': '2.5', 'supplier': 'S'})
    assert len(calls) == 1 and calls[0]['material_id'] == 3 and calls[0]['quantity'] == 5.0


def test_migration_017_is_null_safe_and_bundled():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sql = (root / 'supabase/migrations/017_receive_material_validation.sql').read_text()
    assert 'qty IS NULL OR cpu IS NULL' in sql and 'REVOKE ALL ON FUNCTION public.receive_material' in sql
    for name in ('FRESH_PROJECT_SQL_EDITOR_SETUP.sql', 'EXISTING_PROJECT_REPAIR_012_TO_017.sql'):
        assert '017_receive_material_validation.sql' in (root / 'supabase' / name).read_text()


# ── Found by the end-to-end journeys (real PostgREST), invisible to mocks ────

def test_mixed_material_and_component_recipe_rows_have_identical_keys(monkeypatch):
    """PostgREST rejects bulk inserts whose rows have different keys (PGRST102)."""
    inserted = []
    monkeypatch.setattr(models, 'get_product_bom', lambda pid: [])
    monkeypatch.setattr(supa, 'delete', lambda *a, **k: True)
    monkeypatch.setattr(supa, 'insert', lambda table, rows: inserted.append(rows) or {'id': 1})
    models.save_product_bom('p1', [
        {'item_type': 'material', 'material_id': '3', 'component_id': None, 'quantity_used': 2},
        {'item_type': 'component', 'material_id': None, 'component_id': '7', 'quantity_used': 1}])
    rows = inserted[0]
    assert len(rows) == 2
    assert {frozenset(r) for r in rows} == {frozenset(rows[0])}, 'all rows must have the same keys'
    assert rows[0]['material_id'] == 3 and rows[0]['component_id'] is None
    assert rows[1]['component_id'] == 7 and rows[1]['material_id'] is None


def test_customer_accepting_quote_gets_friendly_message_not_500_when_backend_fails(monkeypatch):
    monkeypatch.setattr(models, 'get_custom_request_by_token',
                        lambda t: {'id': '5', 'status': 'quoted', 'quoted_price': 100, 'tracking_token': t})
    def boom(*a, **k):
        raise supa.SupabaseError('Backend rejected RPC convert_custom_request (HTTP 400)', status=400, code='22P02')
    monkeypatch.setattr(models, 'convert_custom_to_order', boom)
    monkeypatch.setattr(supa, 'select', lambda *a, **k: [])
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
    client = app.test_client()
    response = client.post('/custom-order/respond/tok123/accepted')
    assert response.status_code == 302 and '/custom-order/track/tok123' in response.headers['Location']
    with client.session_transaction() as sess:
        message = ' '.join(m for c, m in sess.get('_flashes', []) if c == 'error')
    assert 'could not confirm' in message and 'HTTP 400' not in message  # no technical detail for customers
