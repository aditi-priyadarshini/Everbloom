-- READ-ONLY diagnostic for a live Everbloom Supabase instance.
-- Run in Supabase SQL Editor. No data is modified, no test orders are created.
-- status=FAIL means fix the specific item before retesting that operation.
WITH
expected_tables(table_name) AS (VALUES
  ('users'),
  ('products'),
  ('categories'),
  ('coupons'),
  ('variants'),
  ('orders'),
  ('order_items'),
  ('tracking'),
  ('notifications'),
  ('reviews'),
  ('wishlists'),
  ('settings'),
  ('custom_requests'),
  ('raw_materials'),
  ('components'),
  ('component_bom'),
  ('product_bom'),
  ('product_materials'),
  ('product_costs'),
  ('expenditures'),
  ('manufacture_log'),
  ('order_requirements'),
  ('auth_tokens'),
  ('gift_cards'),
  ('returns'),
  ('faqs'),
  ('broadcasts'),
  ('back_in_stock_alerts'),
  ('email_templates'),
  ('email_log'),
  ('artisans'),
  ('newsletter_subscribers'),
  ('inventory_movements'),
  ('audit_log'),
  ('collections'),
  ('occasions'),
  ('collection_products'),
  ('product_occasions'),
  ('testimonials')
),
expected_columns(table_name, column_name) AS (VALUES
  ('products','id'),
  ('products','title'),
  ('products','price'),
  ('products','stock'),
  ('products','category_id'),
  ('products','images'),
  ('products','availability_mode'),
  ('products','accepting_orders'),
  ('products','lead_time_min'),
  ('products','lead_time_max'),
  ('products','max_order_quantity'),
  ('products','sale_price'),
  ('products','slug'),
  ('products','personalization_fields'),
  ('products','image_alt_texts'),
  ('orders','id'),
  ('orders','name'),
  ('orders','email'),
  ('orders','total'),
  ('orders','status'),
  ('orders','tracking_token'),
  ('orders','idempotency_key'),
  ('orders','payment_status'),
  ('orders','fulfilment_status'),
  ('orders','internal_notes'),
  ('orders','payment_screenshot_url'),
  ('orders','custom_request_id'),
  ('order_items','id'),
  ('order_items','order_id'),
  ('order_items','product_id'),
  ('order_items','price'),
  ('order_items','quantity'),
  ('order_items','is_custom'),
  ('order_items','personalization'),
  ('order_items','availability_mode'),
  ('order_items','variant_ids'),
  ('order_items','selected_options'),
  ('custom_requests','id'),
  ('custom_requests','status'),
  ('custom_requests','converted_order_id'),
  ('custom_requests','linked_product_id'),
  ('custom_requests','quoted_price'),
  ('custom_requests','quoted_days'),
  ('custom_requests','admin_note'),
  ('custom_requests','email'),
  ('custom_requests','reference_image_url'),
  ('artisans','id'),
  ('artisans','name'),
  ('artisans','speciality'),
  ('artisans','instagram'),
  ('artisans','active'),
  ('product_costs','id'),
  ('product_costs','product_id'),
  ('product_costs','notes'),
  ('collections','id'),
  ('collections','slug'),
  ('collections','active'),
  ('occasions','id'),
  ('occasions','slug'),
  ('occasions','active'),
  ('categories','id'),
  ('categories','slug'),
  ('categories','active'),
  ('gift_cards','id'),
  ('gift_cards','code'),
  ('gift_cards','balance'),
  ('settings','key'),
  ('settings','value'),
  ('raw_materials','id'),
  ('raw_materials','current_stock'),
  ('raw_materials','active'),
  ('components','id'),
  ('components','current_stock'),
  ('components','active')
),
expected_functions(signature) AS (VALUES
  ('public.place_commerce_order(jsonb,jsonb)'),
  ('public.consume_order_inventory(uuid)'),
  ('public.cancel_commerce_order(uuid)'),
  ('public.subscribe_newsletter(text)'),
  ('public.receive_material(jsonb)'),
  ('public.produce_component(bigint,numeric,numeric,text)'),
  ('public.convert_custom_request(uuid,numeric,text)'),
  ('public.update_commerce_order(uuid,jsonb)')
),
findings AS (
 SELECT 'TABLE'::text AS kind, table_name AS object, 
   CASE WHEN to_regclass('public.' || table_name) IS NULL THEN 'FAIL' ELSE 'PASS' END AS status,
   'Check 001–015 migrations'::text AS advice FROM expected_tables
 UNION ALL
 SELECT 'COLUMN', table_name||'.'||column_name,
   CASE WHEN NOT EXISTS (SELECT 1 FROM information_schema.columns c
     WHERE c.table_schema='public' AND c.table_name=e.table_name AND c.column_name=e.column_name)
   THEN 'FAIL' ELSE 'PASS' END,
   'Column required by the application; check the originating migration'
 FROM expected_columns e
 UNION ALL
 SELECT 'RPC', signature,
   CASE WHEN to_regprocedure(signature) IS NULL THEN 'FAIL' ELSE 'PASS' END,
   'Function missing or signature differs; review migrations 003/004/013/009'
 FROM expected_functions
 UNION ALL
 SELECT 'RPC PERMISSION', signature,
   CASE WHEN to_regprocedure(signature) IS NULL THEN 'FAIL'
        WHEN has_function_privilege('service_role', to_regprocedure(signature), 'EXECUTE') THEN 'PASS'
        ELSE 'FAIL' END,
   'Ensure EXECUTE is granted to service_role only'
 FROM expected_functions
 UNION ALL
 SELECT 'TABLE PERMISSION', table_name,
   CASE WHEN to_regclass('public.' || table_name) IS NULL THEN 'FAIL'
        WHEN has_table_privilege('service_role', to_regclass('public.'||table_name), 'SELECT')
         AND has_table_privilege('service_role', to_regclass('public.'||table_name), 'INSERT')
         AND has_table_privilege('service_role', to_regclass('public.'||table_name), 'UPDATE')
         AND has_table_privilege('service_role', to_regclass('public.'||table_name), 'DELETE') THEN 'PASS'
        ELSE 'FAIL' END,
   'Review migration 010; RLS is not tested by this privilege check'
 FROM expected_tables
 UNION ALL
 SELECT 'RLS', table_name,
   CASE WHEN c.oid IS NOT NULL AND c.relrowsecurity THEN 'PASS' ELSE 'FAIL' END,
   'RLS should be enabled for all business tables'
 FROM expected_tables e LEFT JOIN pg_class c ON c.oid=to_regclass('public.'||e.table_name)
 UNION ALL
 SELECT 'STORAGE', bucket_id,
   CASE WHEN EXISTS(SELECT 1 FROM storage.buckets b WHERE b.id=bucket_id AND b.public=expected_public)
        THEN 'PASS' ELSE 'FAIL' END,
   CASE WHEN expected_public THEN 'Bucket must be public'
        ELSE 'Bucket must be private' END
 FROM (VALUES ('everbloom',true),('payment-receipts',false)) AS b(bucket_id,expected_public)
)
SELECT kind, object, status, advice FROM findings ORDER BY CASE status WHEN 'FAIL' THEN 0 ELSE 1 END, kind, object;
