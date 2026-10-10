# Product creation HTTP 400: safe diagnosis and repair

## Confirmed code-level mismatch

The admin product editor always sends `image_alt_texts` and the other commerce columns.
The previous top-level `schema.sql` listed only migrations 001–010, while
`image_alt_texts` was added in migration **011_ui_metadata.sql**. A database
initialized through that entrypoint could therefore reject every product POST
with HTTP **400 / PGRST204**, even if the service-role credential is correct.
**The actual production cause is unverified without its PostgREST error JSON.**

## Deploy / repair (never paste secrets into logs or chat)

1. Back up Supabase and test the SQL on a staging copy first.
2. Supabase Dashboard > SQL Editor: run the read-only check:

   ```sql
   select column_name, data_type
   from information_schema.columns
   where table_schema='public' and table_name='products'
     and column_name in (
       'availability_mode', 'accepting_orders', 'lead_time_min',
       'lead_time_max', 'max_order_quantity', 'sale_price',
       'slug', 'personalization_fields', 'image_alt_texts'
     )
   order by column_name;
   ```

3. If any are missing, review and run `supabase/migrations/012_product_insert_repair.sql`
   in the SQL Editor (after your backup). This script only adds absent columns,
   grants table privileges to `service_role`, and reloads PostgREST's cache.
   **It does not complete other missing migrations**, nor fix incompatible existing
   column types; do not re-run the older non-idempotent migrations blindly.
4. In Vercel > Project > Settings > Environment Variables, ensure both
   `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are configured for Production
   and refer to the SAME Supabase project. Redeploy to apply changed variables.
   Keep the service-role secret server-side only. Do not use the public `anon` key.
5. Open `/admin/system-health`. The new **Product creation schema** check probes
   all editor columns; two additional checks probe product collection/occasion
   junction tables. Retry adding a product with title and price and check the
   browser flash plus Vercel function logs.

## Interpret errors

| Code | Typical issue | Action |
| --- | --- | --- |
| `PGRST204` | Column absent from API schema cache | Apply missing column migration, reload PostgREST schema |
| `PGRST205` / `42P01` | Table missing | Apply and review missing table migrations |
| `42501` / HTTP 401 or 403 | Wrong key or SQL privilege | Check server-side service-role key and GRANTs |
| `23503` | Category ID references nonexistent row | Pick a real category |
| `23514` | Constraint violation: invalid stock/price/discount | Correct values |
| `23505` | Unique violation | Use unique value |
| `22P02` | Invalid numeric/date/UUID representation | Correct form data |

`SupabaseError` now preserves a limited PostgREST code/message/hint for the
**admin UI only** while the default exception string remains generic, so
storefront error handling does not reveal backend internals.

## Caveats

- Read-only checks cannot prove INSERT permission; only a staging write test can.
- The repair script does not magically resolve every possible 400. In particular,
  a legacy schema with incompatible data types or additional NOT NULL columns
  may still need a custom reviewed migration.
- Creating a product and writing its collection/occasion associations are
  separate database transactions. If association linking fails, the editor now
  explicitly says the product exists and redirects to its edit page to avoid
  making an accidental duplicate on retry.
