# LIVE health check: PostgREST HTTP 400, PostgreSQL 42703

`42703` means the deployed PostgreSQL query referenced a column that does not exist.

Observed failures:
- `public.categories.active`
- `public.custom_requests.linked_product_id`

1. Back up the existing production database.
2. Verify the admin `/admin/system-health` **Connected Supabase host** matches the host in the Supabase project's API settings. Do not share API credentials.
3. In that exact project, open SQL Editor and apply `supabase/migrations/016_missing_columns_repair.sql`. Check that it **completes successfully**, and that both result rows say `PASS`. The repair expects `public.products.id` to be `uuid` (as in the baseline schema).
4. Run `NOTIFY pgrst, 'reload schema';` if needed, wait until it takes effect, and refresh `/admin/system-health`.
5. If SQL shows PASS but HTTP still returns 42703, check the Vercel Production `SUPABASE_URL`, environment scope, and deployed version. It points to a different project or you are hitting a different deployment/database (barring rare caching or replica issues).

**Do not** recreate tables, change your service key, disable RLS, or run the full fresh setup to fix two missing columns.

The admin health page is an **existence/access probe** only: it does not prove successful insert/update/RPC execution.
