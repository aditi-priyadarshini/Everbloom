-- Everbloom: read-only root-cause diagnostics for admin failures.
-- Run in Supabase > SQL Editor on the SAME Supabase project used by Vercel.
-- This query does not modify orders, permissions, users, tables, or RPCs.
-- Copy the result rows, especially any FAIL or UNKNOWN, without sharing credentials.
WITH checks AS (
  SELECT 'MIGRATION 016'::text AS section, 'categories.active'::text AS object,
     EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='categories' AND column_name='active') AS ok,
     'Archive and public visibility actions need this column'::text AS notes
  UNION ALL SELECT 'MIGRATION 016','custom_requests.linked_product_id',
     EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='custom_requests' AND column_name='linked_product_id'),
     'Required for custom request product linking and conversion'
  UNION ALL SELECT 'MIGRATION 005','custom_requests.listed_in_shop',
     EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='custom_requests' AND column_name='listed_in_shop'),
     'Create-product-from-request writes this field; not checked in the earlier audit'
  UNION ALL SELECT 'MIGRATION 011','products.image_alt_texts',
     EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='products' AND column_name='image_alt_texts'),
     'Admin product save payload includes this field'
  UNION ALL SELECT 'MIGRATION 013','convert_custom_request RPC installed',
     to_regprocedure('public.convert_custom_request(uuid,numeric,text)') IS NOT NULL,
     'RPC signature required by backend'
  UNION ALL SELECT 'MIGRATION 013','convert_custom_request updated token generator',
     coalesce(position('gen_random_uuid' IN pg_get_functiondef(to_regprocedure('public.convert_custom_request(uuid,numeric,text)')))>0, false),
     'PASS means the 013 replacement body is installed, not the old 006 body'
  UNION ALL SELECT 'MIGRATION 013','RPC service_role EXECUTE',
     coalesce(has_function_privilege('service_role', to_regprocedure('public.convert_custom_request(uuid,numeric,text)'), 'EXECUTE'), false),
     'Only checks a database grant; cannot verify the key configured in Vercel'
  UNION ALL SELECT 'DATABASE','products.id is UUID',
     EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='products' AND column_name='id' AND udt_name='uuid'),
     'The product-link foreign key expects UUID identifiers'
  UNION ALL SELECT 'DATABASE','linked_product_id is UUID',
     EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='custom_requests' AND column_name='linked_product_id' AND udt_name='uuid'),
     'Must match products.id type'
  UNION ALL SELECT 'STORAGE','everbloom bucket public',
     EXISTS(SELECT 1 FROM storage.buckets WHERE id='everbloom' AND public),
     'Public catalogue media bucket'
  UNION ALL SELECT 'STORAGE','payment-receipts bucket private',
     EXISTS(SELECT 1 FROM storage.buckets WHERE id='payment-receipts' AND NOT public),
     'Private payment evidence bucket'
)
SELECT section, object, CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END AS status, notes
FROM checks ORDER BY CASE WHEN ok THEN 1 ELSE 0 END, section, object;

-- These values allow you to confirm the SQL editor is connected to the expected database.
-- They do not reveal the service-role key or any customer data.
SELECT current_database() AS database_name,
       current_schema() AS current_schema,
       current_user AS executing_role,
       inet_server_addr()::text AS database_server_address;
