# Everbloom — audit and Supabase deployment

## What was checked

- Offline review covers Flask route decorators, template endpoint references, CSRF form tokens, required PostgREST table/column names, and 8 RPC signatures.
- Isolated tests exercise mocked Supabase errors, caching, product insert diagnostics and idempotent custom-order conversion. These are **not** live DB or browser tests.
- Admin `/admin/system-health` sends zero-row GET requests to important tables and checks public `everbloom` / private `payment-receipts` Storage buckets. It does **not** validate write permissions or run conversion RPCs.

## Fresh Supabase project

1. Create a Supabase project in the Supabase dashboard. Save the project URL and **server-side** service-role key. Never paste the service-role key into chats or client JS.
2. In Supabase > SQL Editor, review then execute `supabase/FRESH_PROJECT_SQL_EDITOR_SETUP.sql` **only for a brand-new empty project**. It installs ordered schema, RPCs, grants, and storage buckets. It is NOT a safe repair script for an existing database (some migrations contain unguarded constraints/triggers).
3. Create a test **admin** using an existing safe signup, then set `is_admin` for that selected user through a privileged SQL Editor statement. Do not change every user or weaken RLS.
4. Add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, a strong `SECRET_KEY`, and `SITE_URL` as Vercel server-side environment variables. Configure SMTP separately. Redeploy.
5. Run `supabase/LIVE_READ_ONLY_VERIFICATION.sql` in SQL Editor; resolve all FAIL items. Open `/admin/system-health` and verify every check, including both buckets.
6. In staging, test product creation, category membership, image upload, guest checkout, cart stock, admin order status transitions, inventory purchase/production, custom conversion **once**, payment proof upload and signed receipt, returns, verification/reset SMTP, and emails.

## Existing Supabase project

1. **Back up production** and clone the schema/data to staging.
2. Run `LIVE_READ_ONLY_VERIFICATION.sql` first.
3. Do NOT run FRESH setup on existing data. Apply only migrations missing from your existing schema, in order. `012_product_insert_repair.sql` and `013_custom_conversion_repair.sql` are additive, but always review backups and PostgreSQL types. `014_storage_setup.sql` creates the expected buckets without touching objects. `015_coupon_rls_permissions.sql` closes a coupon-table RLS/permissions gap.
4. SQL Editor can execute standalone numbered migration files directly; the root `schema.sql` contains psql `\ir` commands that **SQL Editor cannot execute**.
5. Refresh PostgREST cache with `NOTIFY pgrst, 'reload schema';` after schema changes.

## What cannot be confirmed offline

This audit does not prove working live Supabase permissions, object ownership, data types on a customized database, SMTP/OAuth, Storage access, background jobs, Vercel cold starts, or individual end-to-end user actions. No live secrets/database were connected for this audit. Errors such as `PGRST202`/`42883` identify missing RPC/signature, `42703`/`PGRST204` missing columns, and `42501` rights. **Do not grant table rights to `anon` to make errors disappear.**

## Performance / follow-up

Public catalogue caching is per process with a short TTL, not globally consistent on serverless; consider shared Redis for rate limits and precomputed aggregate totals after you measure real production latency. Per-request admin pages still fetch some large order lists; a proper server-side pagination/index pass should follow actual query timings.

## Security issue fixed in migration 015

`coupons` was present in the baseline but omitted from both the table-hardening list in 002 and grants list in 010. Without RLS, the table can be exposed through Supabase PostgREST under default project grants. Migration 015 enables RLS, revokes browser-role access, and grants service-role CRUD. Apply this to existing production projects even if coupon operations appear functional.

See `docs/OPERATION_CHECKLIST.md` and `docs/STATIC_ROUTE_INVENTORY.md` for the route-by-route dependency matrix and endpoint inventory.
