-- Everbloom production repair: audit FAILs on 2026-10-10
-- Exactly two missing columns: categories.active and custom_requests.linked_product_id
-- Additive, repeatable; does NOT drop existing rows, rebuild tables, or relax RLS.
-- Review, back up your Supabase database, and preferably run on staging first.
-- Assumes public.products.id is UUID as defined in migration 001.
BEGIN;

-- Category archive and public visibility status (migration 011).
-- All existing categories will remain active by default.
ALTER TABLE public.categories
  ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;

-- Optional link from a custom request to an existing catalogue product.
-- UUID FK matches migration 001 and the convert_custom_request RPC.
ALTER TABLE public.custom_requests
  ADD COLUMN IF NOT EXISTS linked_product_id uuid REFERENCES public.products(id);

COMMIT;

-- Ask PostgREST to refresh its table/column schema cache.
NOTIFY pgrst, 'reload schema';

-- Must return two PASS rows after the migration.
SELECT v.table_name || '.' || v.column_name AS object,
       CASE WHEN c.column_name IS NULL THEN 'FAIL' ELSE 'PASS' END AS status,
       c.data_type
FROM (VALUES
  ('categories', 'active'),
  ('custom_requests', 'linked_product_id')
) AS v(table_name, column_name)
LEFT JOIN information_schema.columns AS c
       ON c.table_schema = 'public'
      AND c.table_name = v.table_name
      AND c.column_name = v.column_name
ORDER BY object;
