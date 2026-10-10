# Everbloom live failure triage

A passing SQL structure/grant audit cannot demonstrate that your admin writes or RPC calls succeed.

1. Check Vercel Production environment variable `SUPABASE_URL` points to the same Supabase project as the SQL Editor. Check that `SUPABASE_SERVICE_ROLE_KEY` is present, server-side, and belongs to that project. Do not share the key.
2. Back up the database. Run `supabase/LIVE_ROOT_CAUSE_CHECK.sql` in the **existing** Supabase project. Do not run the fresh setup script against a live project.
3. If `categories.active` or `custom_requests.linked_product_id` is missing, review and apply migration 016. If the updated token generator is missing, review migration 013; do not apply the original 006 over it.
4. Run `NOTIFY pgrst, 'reload schema';` after any permitted schema repairs.
5. Reproduce the **specific** failing admin action once, and capture the full admin error including PostgREST code and reason from Vercel function logs. Do not include tokens or customer data.
6. Verify the latest code was deployed to the correct Vercel Production deployment before retrying.

The source `schema.sql` has been corrected to include migration 016 for **future** psql migration runs. This cannot apply migration 016 to an already-running Supabase database simply by deploying code.
