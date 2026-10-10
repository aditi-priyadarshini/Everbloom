"""Custom order RPC regression tests; no credentials or live DB required."""
from pathlib import Path

import pytest
import supa
import models


class Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload
        self.content = b'{}'

    def json(self):
        return self.payload


def _rpc_error(monkeypatch, code, message, status=400):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'fake-test-key')
    monkeypatch.setattr(supa._http, 'request', lambda *a, **kw: Response(status, {'code': code, 'message': message}))
    with pytest.raises(supa.SupabaseError) as info:
        supa.rpc('convert_custom_request', {'p_request_id': 'uuid', 'p_price': 50})
    return info.value


@pytest.mark.parametrize('code,message,hint', [
    ('42883', 'function gen_random_bytes(integer) does not exist', '013_custom_conversion_repair.sql'),
    ('PGRST202', 'Could not find the function', '013_custom_conversion_repair.sql'),
    ('42703', 'column internal_notes does not exist', '013_custom_conversion_repair.sql'),
    ('22023', 'Closed or rejected requests cannot be converted', 'verify the request state'),
])
def test_rpc_errors_show_actionable_admin_diagnostics(monkeypatch, code, message, hint):
    error = _rpc_error(monkeypatch, code, message)
    assert error.code == code
    assert message in error.admin_detail
    assert hint in error.admin_detail
    assert message not in str(error)  # never expose database internals to public views


def test_conversion_requires_backend_service_role(monkeypatch):
    for env_key in ('SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_SERVICE_KEY'):
        monkeypatch.delenv(env_key, raising=False)
    monkeypatch.setenv('SUPABASE_ANON_KEY', 'public-key-not-authorized-for-admin')
    monkeypatch.setenv('SUPABASE_URL', 'https://example.supabase.co')
    with pytest.raises(supa.SupabaseError, match='service-role credential'):
        supa.rpc('convert_custom_request', {'p_request_id': 'uuid', 'p_price': 50})


def test_conversion_calls_single_rpc_and_limits_note(monkeypatch):
    monkeypatch.setattr(models, 'get_custom_request', lambda rid: {'id': rid, 'status': 'quoted'})
    calls=[]
    monkeypatch.setattr(supa, 'rpc', lambda name, params: calls.append((name, params)) or {'id': 'order-123'})
    order, err = models.convert_custom_to_order('request-123', '12.50', 'x' * 22000)
    assert err is None and order['id'] == 'order-123'
    assert len(calls) == 1
    assert calls[0][0] == 'convert_custom_request'
    assert calls[0][1]['p_price'] == 12.5
    assert len(calls[0][1]['p_note']) == 20000


@pytest.mark.parametrize('bad_price', ['NaN', 'Infinity', '-10', '0', '4.999', '999999999999', 'garbage'])
def test_invalid_prices_rejected_before_database_call(monkeypatch, bad_price):
    monkeypatch.setattr(models, 'get_custom_request', lambda rid: {'id': rid})
    monkeypatch.setattr(supa, 'rpc', lambda *args: pytest.fail('Should not call RPC for invalid price'))
    order, err = models.convert_custom_to_order('request', bad_price)
    assert order is None and err


def test_existing_conversion_returns_order_without_new_rpc(monkeypatch):
    monkeypatch.setattr(models, 'get_custom_request', lambda rid: {'converted_order_id': 'order-1'})
    monkeypatch.setattr(models, 'get_order', lambda oid: {'id': oid})
    monkeypatch.setattr(supa, 'rpc', lambda *args: pytest.fail('Repeated conversion must not create another order'))
    assert models.convert_custom_to_order('request', 200) == ({'id': 'order-1'}, None)


def test_missing_converted_order_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(models, 'get_custom_request', lambda rid: {'converted_order_id': 'deleted-order'})
    monkeypatch.setattr(models, 'get_order', lambda oid: None)
    order, err = models.convert_custom_to_order('request', 200)
    assert order is None and 'missing' in err


def test_repair_sql_has_atomic_idempotent_rpc_and_backend_only_execution():
    file = Path(__file__).resolve().parents[1] / 'supabase' / 'migrations' / '013_custom_conversion_repair.sql'
    sql = file.read_text()
    for expected in (
        'CREATE OR REPLACE FUNCTION public.convert_custom_request',
        'FOR UPDATE',
        'r.converted_order_id IS NOT NULL',
        'INSERT INTO public.orders',
        'INSERT INTO public.order_items',
        'INSERT INTO public.tracking',
        'ADD COLUMN IF NOT EXISTS internal_notes text',
        'ADD COLUMN IF NOT EXISTS personalization jsonb',
        'REVOKE ALL ON FUNCTION public.convert_custom_request',
        'GRANT EXECUTE ON FUNCTION public.convert_custom_request',
        "NOTIFY pgrst, 'reload schema'",
    ):
        assert expected in sql
    assert 'gen_random_bytes' not in sql.split('AS $$', 1)[-1].split('$$;', 1)[0]
