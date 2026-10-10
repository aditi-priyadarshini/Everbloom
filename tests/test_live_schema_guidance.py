"""Missing-column diagnostics correctly reference the actual repair."""
import supa
from pathlib import Path

def test_missing_admin_columns_point_to_migration_016():
    for scope in ("probe categories", "probe custom_requests"):
        for code in ("42703", "PGRST204"):
            hint=supa._backend_hint(400,code,scope)
            assert "016_missing_columns_repair.sql" in hint
            assert "SUPABASE_URL" in hint

def test_product_hint_still_points_to_012():
    assert "012_product_insert_repair.sql" in supa._backend_hint(400, "PGRST204", "insert products")

def test_admin_displays_project_host_only():
    tpl=(Path(__file__).resolve().parents[1]/"templates/admin/system_health.html").read_text()
    assert "supabase_host" in tpl
    assert "SUPABASE_SERVICE_ROLE_KEY" not in tpl
