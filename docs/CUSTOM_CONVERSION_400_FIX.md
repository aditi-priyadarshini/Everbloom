# Fix: HTTP 400 on RPC `convert_custom_request`

The failure happens **inside a PostgREST RPC**, not a normal product insert. The production cause cannot be confirmed from an HTTP status alone. The patched admin shows PostgREST error **code and message** on failed actions (server-side only).

## Why the old RPC may fail

- Migration `006_custom_conversion.sql` calls `gen_random_bytes(32)` with `search_path=public`. Supabase commonly installs `pgcrypto` functions under `extensions`. If this is the problem, PostgREST should return `42883` (`function gen_random_bytes(integer) does not exist`). Migration 013 replaces this call with two built-in UUIDv4 values.
- Missing columns in `orders` (email, tracking_token, internal_notes) or `order_items` (availability_mode, personalization) can raise `42703`. Migration 013 adds **only those columns** if missing.
- A missing or stale RPC signature may surface as `PGRST202`; use the function check below.
- A closed/rejected request, invalid quote or incompatible existing constraints can also return HTTP 400 with **different** codes; don't assume a migration fixes all such errors.

## Safe deployment

1. Back up Supabase and run this on staging first.
2. In Supabase **SQL Editor** run these read-only checks:

   ```sql
   SELECT to_regprocedure('public.convert_custom_request(uuid,numeric,text)') AS rpc_signature;
   SELECT has_function_privilege('service_role', 'public.convert_custom_request(uuid,numeric,text)', 'EXECUTE') AS service_role_can_execute;
   SELECT table_name, column_name FROM information_schema.columns
   WHERE table_schema='public'
     AND ((table_name='orders' AND column_name IN ('email','tracking_token','internal_notes'))
       OR (table_name='order_items' AND column_name IN ('personalization','availability_mode')))
   ORDER BY table_name, column_name;
   ```
   If the function doesn't exist, the `has_function_privilege` query may itself error; run it **after** migration 013.
3. Review and run `supabase/migrations/013_custom_conversion_repair.sql` in SQL Editor. It **replaces the RPC definition**, adds only absent conversion columns, grants service-role privileges, and refreshes PostgREST metadata. It does not change existing orders or disable RLS.
4. Deploy the matching Python source to Vercel, with **server-only** `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from the same project.
5. Open `/admin/system-health` and verify the custom-order table checks. This is read-only, so it **cannot** prove that the RPC's INSERT will work. Test conversion on a disposable staging request first.

## Error-code reference

| Code | What to check |
| --- | --- |
| `42883` | RPC dependency not on SQL `search_path`, or wrong function signature |
| `PGRST202` | Missing RPC or stale PostgREST function cache |
| `42703` | Missing column, likely commerce migration drift |
| `42501` / HTTP 401–403 | Wrong JWT role, GRANT, or server credentials |
| `23502` / `23503` / `23514` | Database constraints; inspect request/linked product |
| `22023` / `P0001` | Business-state error (e.g. closed request or invalid quote) |

### Operational warning

Never replace `convert_custom_request` with separate application-side inserts into orders/order_items. Atomicity and request row locking are needed to prevent duplicate orders. If you see an error after an RPC attempt, inspect `converted_order_id` **before retrying**; the patched implementation is idempotent.
