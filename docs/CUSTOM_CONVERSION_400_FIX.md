# Fix: HTTP 400 on RPC `convert_custom_request`

The failure happens **inside a PostgREST RPC**, not a normal product insert. The production cause cannot be confirmed from an HTTP status alone. The patched admin shows PostgREST error **code and message** on failed actions (server-side only).

## Update: `22P02 invalid input syntax for type uuid: "9"` (fixed by migration 016)

**Cause:** on databases created before migration 001, `custom_requests.id` is an integer, but the RPC
declared `p_request_id uuid`. The admin URL carries the real id (`9`), and PostgREST fails the cast
before the function body runs. **Fix:** run `supabase/migrations/016_custom_request_id_type_agnostic.sql`
(or the matching section of the bundle files). It drops the uuid-only function and installs one that
accepts the id as text, so uuid, bigint and integer ids all work. It is idempotent and does not touch
existing data. Afterwards `SELECT oid::regprocedure FROM pg_proc WHERE proname='convert_custom_request'`
must return exactly one row: `convert_custom_request(text,numeric,text)`. Never re-run 013 alone afterwards.
Run the "ID TYPE CHECK" section of `LIVE_READ_ONLY_VERIFICATION.sql` to see your real column types.

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
| `22P02` | Id type mismatch (integer id sent to a uuid parameter): run migration 016 |
| `PGRST203` | Two overloads of the RPC exist: run migration 016 (drops the uuid one) |
| `22023` / `P0001` | Business-state error (e.g. closed request or invalid quote) |

### Operational warning

Never replace `convert_custom_request` with separate application-side inserts into orders/order_items. Atomicity and request row locking are needed to prevent duplicate orders. If you see an error after an RPC attempt, inspect `converted_order_id` **before retrying**; the patched implementation is idempotent.

## Running the database function tests

`tests/all_functions.sql` (86 checks over every RPC, trigger and state rule) and `tests/transactions.sql`
run on a **disposable** migrated Postgres, never on production. Both work whether `custom_requests.id`
is a uuid or an integer, and each rolls back its own data:

    psql -v ON_ERROR_STOP=1 -f tests/all_functions.sql     # prints "ALL 86 CHECKS PASSED"
    psql -v ON_ERROR_STOP=1 -f tests/transactions.sql

`pytest tests` covers the Flask layer (no database needed).

Migration 017 hardens `receive_material`: a purchase with a missing cost or quantity is now rejected
instead of silently blanking the material's cost price.

## End-to-end journeys

`tests/e2e/` runs 36 complete customer and admin journeys against a real Postgres + PostgREST stack
(see `tests/e2e/README.md`). It found two bugs that mocked tests could not: product recipes mixing
materials and components failed to save (PostgREST requires identical keys in bulk inserts), and a
customer accepting a quote saw a raw 500 page when the backend call failed.
