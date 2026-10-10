"""Storage preflight regression tests without live Supabase."""
import pytest
import supa

class FakeResponse:
    status_code = 200
    content = b'{}'
    def __init__(self, visible): self.visible = visible
    def json(self): return {'public': self.visible, 'name': 'bucket'}

def test_storage_checks_privacy(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'example-test-key')
    requests = []
    def fake(method,url,**kwargs):
        requests.append((method,url,kwargs['headers']['Authorization']))
        return FakeResponse(False)
    monkeypatch.setattr(supa._http, 'request', fake)
    assert supa.probe_bucket('payment-receipts', expected_public=False)
    with pytest.raises(supa.SupabaseError, match='must be public'):
        supa.probe_bucket('everbloom', expected_public=True)
    assert requests[0][:2] == ('GET', 'https://test.supabase.co/storage/v1/bucket/payment-receipts')

def test_storage_never_falls_back_to_anon_key(monkeypatch):
    monkeypatch.delenv('SUPABASE_SERVICE_ROLE_KEY', raising=False)
    monkeypatch.delenv('SUPABASE_SERVICE_KEY', raising=False)
    monkeypatch.setenv('SUPABASE_ANON_KEY', 'anon-test-key')
    monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
    with pytest.raises(supa.SupabaseError, match='service-role'):
        supa.probe_bucket('everbloom', expected_public=True)
    assert supa._get_service_key() is None

def test_full_setup_sql_includes_all_migrations():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    setup=(root/'supabase/FRESH_PROJECT_SQL_EDITOR_SETUP.sql').read_text()
    assert len(list((root/'supabase/migrations').glob('*.sql'))) == 15
    assert 'payment-receipts' in setup
    for i in range(1,16):
        assert f'/{i:03d}_' not in setup  # setup has SQL, not external file references
        assert f'-- ==================== {i:03d}_' in setup


def test_coupons_not_exposed_to_browser_roles():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    sql=(root/'supabase/migrations/015_coupon_rls_permissions.sql').read_text().lower()
    assert 'alter table public.coupons enable row level security' in sql
    assert 'revoke all on table public.coupons from anon, authenticated' in sql
    assert 'grant select, insert, update, delete on table public.coupons to service_role' in sql
