# Supabase audit 2026-10-10: 2 missing columns

Audit file: 207 PASS, 2 FAIL.

- `categories.active`: Required by admin category archive/visibility. Introduced in migration 011.
- `custom_requests.linked_product_id`: Required by linked custom products and `convert_custom_request`. Originally part of baseline migration 001.

Existing database: **DO NOT** run the fresh setup script. Back up, test in staging, then run only `supabase/migrations/016_missing_columns_repair.sql` in the Supabase SQL Editor. This migration is additive and idempotent. It sets existing categories to `active = true` by default; confirm that is your desired storefront visibility. No custom requests will be linked to products automatically. The migration references `products(id)` and expects a UUID primary key.

If the migration succeeds, its final query returns two `PASS` rows. Rerun `supabase/LIVE_READ_ONLY_VERIFICATION.sql` to confirm all audit checks pass. Deploying the same app ZIP by itself **does not** change the database.

A schema audit only checks structures/grants; it cannot prove production writes, custom-order conversions, or emails work. Use staging test records and the admin `/admin/system-health` page to validate those flows.
