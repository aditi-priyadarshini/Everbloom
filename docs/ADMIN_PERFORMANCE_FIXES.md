# Everbloom admin and speed patch — 10 October 2026

## What was actually changed

- **Backend reads/writes:** Supabase REST now uses an HTTP connection pool, separate connection/read timeouts and explicit errors when PostgREST rejects a query. A missing table/permission no longer silently looks like an empty result.
- **Admin settings:** saving ~26 settings uses one `INSERT ... ON CONFLICT DO UPDATE` equivalent via PostgREST upsert, rather than a SELECT and write for *every* key. Settings are cached briefly after read, and invalidated immediately after save.
- **Storefront:** a 30-second, process-local catalogue/settings cache avoids repeating seven or more Supabase queries per request on a warm instance; request-local reuse remains. Admin pages skip unnecessary storefront navigation/settings requests. `PUBLIC_CACHE_TTL=0` turns cross-request caching off.
- **Admin save feedback:** major creation/edit/archive actions now check database responses before displaying success. The admin blueprint handles validation and Supabase errors and returns to the prior admin form rather than a generic 500.
- **Products:** new products are listed by default when creating a product; malformed numeric/image inputs result in visible feedback; failed image uploads do not silently finish a product save. Catalogue cache invalidates after publishing and merchandising edits.
- **Images:** user-supplied PNG/JPEG/WebP uploads are converted to WebP at up to 1600 px, with lower CPU-intensive encoding and async image decoding for secondary media.
- **Inventory costing:** expensive per-line material lookups are batched; recipe writes use one bulk insert with best-effort rollback of old recipe if the new data is rejected.
- **Diagnostics:** `/admin/system-health` is a read-only, admin-only interface that probes required Supabase tables and columns with zero-row requests. The System sidebar contains a link.
- **Reliability:** audit-log errors no longer convert an otherwise successful admin POST into HTTP 500; backend logs still record the audit failure. Public image-upload errors are handled on checkout/custom-order forms.
- **Emails:** one misleading 'email sent' message was corrected; actual SMTP delivery still requires a real-service test.

## Essential steps for deployment

1. **Back up the production Supabase database first.** Do not blindly run the baseline migration against real customer data.
2. Restore the backup into a staging Supabase project. Review and apply migrations `supabase/migrations/001_legacy_baseline.sql` through `012_product_insert_repair.sql` in ascending order as appropriate to that database. Most optional admin features require these migrations. In particular `003_transactions.sql`, `004_inventory_operations.sql`, `005_merchandising.sql`, `006_custom_conversion.sql`, `007_order_states.sql`, `008_order_validation.sql`, `009_order_updates.sql`, `010_backend_permissions.sql`, , `011_ui_metadata.sql`, and `012_product_insert_repair.sql` provide the inventory, merchandising, RPC, RLS and image-alt-text features.
3. Ensure Vercel server-side environment contains `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a random `SECRET_KEY` of at least 32 characters. Do not put the service key in frontend variables, screenshots or git.
4. Deploy this code, log in as a real administrator, and open **`/admin/system-health`**. Fix failed checks before testing the corresponding admin feature.
5. Smoke test create/edit/archive product (with image), add category/collection/occasion, save settings twice, gift card/coupon create, inventory purchase/recipe, and update order status. Check in Supabase that data actually persisted.
6. Run the complete test suite in an environment with dependencies installed: `pip install -r requirements.txt -r requirements-dev.txt && pytest -q` (the project specifies Python 3.12).
7. Confirm Vercel function logs and the browser Network tab, especially 4xx/5xx responses, cold-start time and Supabase request duration. `PUBLIC_CACHE_TTL=30` is default; set to `0` if public catalogue must reflect external edits instantly.

## Known limitations (do not treat this as live-verified)

- The production Supabase project, deployed Vercel environment and SMTP/Storage credentials were **not available** to this offline code audit. Neither remote schema compatibility nor end-to-end admin writes have been verified.
- Recipe replacement still uses separate HTTP transactions; if the database fails mid-operation, it attempts restoration but **cannot guarantee atomicity**. Production-grade atomic recipe edits require database RPCs/transactions. Orders/inventory critical paths already rely on database RPC migrations.
- This patch does not remove Vercel cold starts or guarantee a particular page speed; only production measurements can validate performance.
- Cached public catalogue data can be stale for up to 30 seconds **per warm serverless instance**. Writes from outside this app may also take up to the TTL to appear.
- Admin log rows currently track successful HTTP POST responses, not an independently audited record of each underlying mutation. Missing `audit_log` permissions are reported in logs and System health.

## Verification in this environment

- 25 isolated tests covering image handling, pricing/cart calculations, pooled Supabase adapter, one-request settings upsert, HTTP error handling, cache invalidation and batch component costs: **passed**.
- Python `compileall` across the whole repository: **passed**.
- Jinja syntax parsing across 67 templates, including the new diagnostic page: **passed**.
- Node JavaScript syntax check on `static/js/main.js`: **passed**.
- Flask integration tests are included under `tests/` but **not run** in this environment because Flask, Flask-WTF and Authlib could not be installed from the disconnected package index. Run them in CI/staging before deploying.

### Product insert 400 follow-up
See `docs/PRODUCT_INSERT_400_FIX.md`. The prior `schema.sql` omitted migration 011, but the form always supplied `image_alt_texts`. The schema loader now includes 011 and a targeted 012 repair. Production root cause needs confirmation from actual PostgREST error code.
