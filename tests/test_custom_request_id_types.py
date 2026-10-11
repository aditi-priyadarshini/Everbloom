"""Regression tests: custom_requests.id may be an integer (legacy DB) or a uuid.

Reproduces: RPC convert_custom_request -> HTTP 400, 22P02,
            invalid input syntax for type uuid: "9"
No credentials or live database required.
"""
from pathlib import Path

import pytest

import models
import supa
from app import create_app

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'supabase' / 'migrations' / '016_custom_request_id_type_agnostic.sql'


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.setattr(supa, 'select', lambda *a, **k: [])
    monkeypatch.setattr(models, 'get_user_by_id', lambda uid: {'id': uid, 'is_admin': True})
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 'admin'
        sess['is_admin'] = True
    return client


def _flashes(client):
    with client.session_transaction() as sess:
        return list(sess.get('_flashes', []))


# ── App layer: ids are opaque strings, never coerced to uuid/int ──────────────

@pytest.mark.parametrize('rid', ['9', '123', '84ad71ce-1e56-4724-ba04-53697f10e057'])
def test_any_request_id_type_is_passed_through_unchanged(monkeypatch, rid):
    monkeypatch.setattr(models, 'get_custom_request', lambda r: {'id': r, 'status': 'quoted'})
    calls = []
    monkeypatch.setattr(supa, 'rpc', lambda name, params: calls.append(params) or {'id': 'order-1'})
    order, err = models.convert_custom_to_order(rid, '500.00', 'note')
    assert err is None and order['id'] == 'order-1'
    assert calls[0]['p_request_id'] == rid
    assert isinstance(calls[0]['p_request_id'], str)


def test_admin_convert_route_with_integer_id_succeeds(admin_client, monkeypatch):
    monkeypatch.setattr(models, 'get_custom_request', lambda r: {'id': r, 'status': 'quoted'})
    seen = []
    monkeypatch.setattr(supa, 'rpc', lambda name, params: seen.append((name, params)) or {'id': 'abcdef123', 'total': 500})
    response = admin_client.post('/admin/custom-requests/9/convert', data={'agreed_price': '500', 'note': 'n'})
    assert response.status_code == 302
    assert seen == [('convert_custom_request', {'p_request_id': '9', 'p_price': 500.0, 'p_note': 'n'})]
    assert any(cat == 'success' for cat, _ in _flashes(admin_client))


def test_22p02_from_rpc_is_flashed_with_actionable_hint_not_a_500(admin_client, monkeypatch):
    monkeypatch.setattr(models, 'get_custom_request', lambda r: {'id': r, 'status': 'quoted'})

    def boom(name, params):
        raise supa.SupabaseError(
            'Backend rejected RPC convert_custom_request (HTTP 400)', status=400, code='22P02',
            backend_message='invalid input syntax for type uuid: "9"',
            hint=supa._backend_hint(400, '22P02', 'RPC convert_custom_request'))
    monkeypatch.setattr(supa, 'rpc', boom)
    response = admin_client.post('/admin/custom-requests/9/convert', data={'agreed_price': '500'})
    assert response.status_code == 302  # redirected back with a flash, not a 500
    message = ' '.join(m for c, m in _flashes(admin_client) if c == 'error')
    assert '22P02' in message and '016_custom_request_id_type_agnostic.sql' in message


def test_hint_for_ambiguous_overload():
    hint = supa._backend_hint(300, 'PGRST203', 'RPC convert_custom_request')
    assert '016_custom_request_id_type_agnostic.sql' in hint


def test_other_22p02_hints_are_unchanged():
    assert 'wrong data type' in supa._backend_hint(400, '22P02', 'insert products')


# ── Error pages must render everywhere (they used to crash under /admin) ─────

def test_non_admin_gets_a_real_403_page(monkeypatch):
    monkeypatch.setattr(supa, 'select', lambda *a, **k: [])
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
    response = app.test_client().get('/admin/')
    assert response.status_code == 403
    assert b'This page is private' in response.data


def test_failed_admin_get_renders_503_page_instead_of_crashing(admin_client, monkeypatch):
    def boom(*a, **k):
        raise supa.SupabaseError('Backend rejected select custom_requests (HTTP 400)', status=400, code='22P02')
    monkeypatch.setattr(models, 'get_custom_request', boom)
    response = admin_client.get('/admin/custom-requests/9')
    assert response.status_code == 503
    assert b'Traceback' not in response.data


# ── Migration 016 contents ──────────────────────────────────────────────────

def test_migration_016_accepts_text_ids_and_drops_uuid_overload():
    sql = MIGRATION.read_text()
    assert 'DROP FUNCTION IF EXISTS public.convert_custom_request(uuid, numeric, text)' in sql
    assert 'p_request_id text' in sql
    assert 'c.id::text = v_key' in sql          # id compared as text: uuid, bigint, int
    for expected in ('FOR UPDATE', 'r.converted_order_id IS NOT NULL', 'INSERT INTO public.orders',
                     'INSERT INTO public.order_items', 'INSERT INTO public.tracking',
                     'REVOKE ALL ON FUNCTION public.convert_custom_request(text, numeric, text)',
                     'GRANT EXECUTE ON FUNCTION public.convert_custom_request(text, numeric, text) TO service_role',
                     "NOTIFY pgrst, 'reload schema'"):
        assert expected in sql
    body = sql.split('AS $$', 1)[-1].split('$$;', 1)[0]
    assert 'gen_random_bytes' not in body


def test_bundles_end_with_the_text_signature_only():
    for name in ('FRESH_PROJECT_SQL_EDITOR_SETUP.sql', 'EXISTING_PROJECT_REPAIR_012_TO_017.sql'):
        sql = (ROOT / 'supabase' / name).read_text()
        assert '016_custom_request_id_type_agnostic.sql' in sql
        # the 016 section must come after 013 so the uuid overload is dropped last
        assert sql.rindex('DROP FUNCTION IF EXISTS public.convert_custom_request(uuid, numeric, text)') > \
               sql.index('013_custom_conversion_repair.sql')


def test_google_login_without_credentials_redirects_instead_of_500(monkeypatch):
    monkeypatch.setattr(supa, 'select', lambda *a, **k: [])
    monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
    monkeypatch.delenv('GOOGLE_CLIENT_SECRET', raising=False)
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
    response = app.test_client().get('/auth/google/login')
    assert response.status_code == 302 and '/auth/login' in response.headers['Location']
