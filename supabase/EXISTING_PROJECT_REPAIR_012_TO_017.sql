-- EXISTING PROJECT ONLY, and ONLY after 001–011 have been applied (applies 012–017).
-- Review and run on a restored staging copy first. Back up production.
-- Do not apply blindly to an incompatible legacy schema.

-- ============== 012_product_insert_repair.sql ==============
-- Everbloom: non-destructive product editor schema repair.
-- Apply ONCE in Supabase SQL Editor after a backup/staging verification.
-- Re-runnable: ADD COLUMN IF NOT EXISTS / GRANT are idempotent.
-- Does not modify existing product values, delete records or disable RLS.
-- This migration is useful if schema.sql previously stopped at migration 010.
begin;

-- These columns are sent by routes/admin.py::_parse_product_form on EVERY save.
-- The first columns originate in 002_commerce.sql; image_alt_texts is from 011.
alter table public.products
    add column if not exists availability_mode text default 'READY_TO_SHIP',
    add column if not exists accepting_orders boolean not null default true,
    add column if not exists lead_time_min integer,
    add column if not exists lead_time_max integer,
    add column if not exists max_order_quantity integer default 99,
    add column if not exists sale_price numeric(12,2),
    add column if not exists slug text,
    add column if not exists personalization_fields jsonb not null default '[]'::jsonb,
    add column if not exists image_alt_texts jsonb not null default '[]'::jsonb;

-- The backend key must be a service-role key; RLS remains enabled.
grant usage on schema public to service_role;
grant select, insert, update, delete on table public.products to service_role;
commit;

-- PostgREST may otherwise keep an old cached schema for a short period.
notify pgrst, 'reload schema';

-- Verification (read-only):
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_schema='public' AND table_name='products'
-- AND column_name IN ('image_alt_texts','availability_mode','personalization_fields');


-- ============== 013_custom_conversion_repair.sql ==============
-- Everbloom: idempotent custom-order conversion RPC repair (migration 013).
-- Back up first. Run in Supabase SQL Editor as project owner/postgres.
-- Does not touch existing orders, change RLS, or create customer orders.
-- Requires migrations 001 (tables) and, for full commerce features, 002–012.
BEGIN;

-- Only the columns the conversion RPC actually needs. On partially migrated
-- projects, these may be absent even though the base tables exist.
ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS email text,
  ADD COLUMN IF NOT EXISTS tracking_token text,
  ADD COLUMN IF NOT EXISTS internal_notes text;
ALTER TABLE public.order_items
  ADD COLUMN IF NOT EXISTS personalization jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS availability_mode text;

-- Preserve the API signature expected by models.convert_custom_to_order.
-- Fully qualified tables and pg_catalog first prevent SECURITY DEFINER
-- name resolution surprises. Use core gen_random_uuid() rather than
-- pgcrypto gen_random_bytes(), which may live in Supabase's extensions schema.
CREATE OR REPLACE FUNCTION public.convert_custom_request(
  p_request_id uuid,
  p_price numeric,
  p_note text DEFAULT ''
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  r public.custom_requests%ROWTYPE;
  o public.orders%ROWTYPE;
  p public.products%ROWTYPE;
  new_tracking_token text;
BEGIN
  IF p_request_id IS NULL THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Request ID is required';
  END IF;
  IF p_price IS NULL OR p_price <= 0 OR p_price > 9999999999.99
     OR p_price <> round(p_price, 2) THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Enter a positive agreed price with at most two decimal places';
  END IF;

  -- Lock request row, making repeated clicks and concurrent retries idempotent.
  SELECT * INTO r FROM public.custom_requests WHERE id = p_request_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Custom request does not exist';
  END IF;

  IF r.converted_order_id IS NOT NULL THEN
    SELECT * INTO o FROM public.orders WHERE id = r.converted_order_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Request points to a missing converted order; contact an administrator';
    END IF;
    RETURN to_jsonb(o);
  END IF;

  IF r.status IN ('closed', 'rejected') THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Closed or rejected requests cannot be converted';
  END IF;

  IF r.linked_product_id IS NOT NULL THEN
    SELECT * INTO p FROM public.products WHERE id = r.linked_product_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION USING ERRCODE = '23503', MESSAGE = 'Linked product no longer exists';
    END IF;
  END IF;

  -- gen_random_uuid is built into supported PostgreSQL versions, so no
  -- dependency on pgcrypto extension location. Two UUIDv4s yield a 64-char token.
  new_tracking_token := replace(gen_random_uuid()::text, '-', '') ||
                        replace(gen_random_uuid()::text, '-', '');

  INSERT INTO public.orders (
    user_id, name, email, phone, address, total, status,
    is_custom_order, custom_request_id, custom_notes, tracking_token,
    preferred_delivery_date, internal_notes
  ) VALUES (
    r.user_id, r.name, r.email, r.phone, 'To be confirmed', p_price,
    'placed', true, r.id, r.description, new_tracking_token,
    r.preferred_delivery_date, left(coalesce(p_note, ''), 20000)
  ) RETURNING * INTO o;

  INSERT INTO public.order_items (
    order_id, product_id, title, price, quantity, image_url,
    is_custom, availability_mode, personalization
  ) VALUES (
    o.id, r.linked_product_id,
    coalesce(p.title, r.craft_type, 'Custom creation'),
    p_price, 1, coalesce(p.images->>0, r.reference_image_url, ''),
    true, 'MADE_TO_ORDER',
    jsonb_build_object('request', r.description, 'colours', r.colour_preference, 'occasion', r.occasion)
  );

  UPDATE public.custom_requests
  SET status = 'converted', converted_order_id = o.id, quoted_price = p_price
  WHERE id = r.id;

  INSERT INTO public.tracking (order_id, status, note)
  VALUES (o.id, 'placed', 'Your custom creation has been confirmed. We will share the next steps.');

  RETURN to_jsonb(o);
END;
$$;

-- Keep execution restricted to the backend role; no public or browser RPC use.
REVOKE ALL ON FUNCTION public.convert_custom_request(uuid, numeric, text)
FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT EXECUTE ON FUNCTION public.convert_custom_request(uuid, numeric, text) TO service_role;
-- These grants also cover direct backend reads/edits. RLS is unchanged.
GRANT SELECT, UPDATE ON public.custom_requests TO service_role;
GRANT SELECT, INSERT ON public.orders, public.order_items, public.tracking TO service_role;
GRANT SELECT ON public.products TO service_role;
COMMIT;

-- Refresh the PostgREST function-signature/schema cache.
NOTIFY pgrst, 'reload schema';

-- Safe, read-only verification:
-- SELECT to_regprocedure('public.convert_custom_request(uuid,numeric,text)') AS rpc_signature;
-- SELECT column_name FROM information_schema.columns WHERE table_schema='public'
--   AND table_name='orders' AND column_name IN ('email','tracking_token','internal_notes');
-- SELECT has_function_privilege('service_role',
--   'public.convert_custom_request(uuid,numeric,text)', 'EXECUTE') AS service_role_can_execute;


-- ============== 014_storage_setup.sql ==============
-- Everbloom: Supabase Storage prerequisites. Safe for existing data.
-- Run as the Supabase project owner in SQL Editor, after a backup.
-- Supabase's managed `storage` schema must already exist.
BEGIN;
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('everbloom', 'everbloom', true, 8388608, ARRAY['image/webp'])
ON CONFLICT (id) DO UPDATE SET public = EXCLUDED.public;
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('payment-receipts', 'payment-receipts', false, 8388608, ARRAY['image/webp'])
ON CONFLICT (id) DO UPDATE SET public = EXCLUDED.public;
COMMIT;
-- All uploads/signing are made from the Flask backend with service_role.
-- Do not add public INSERT/UPDATE policies to payment-receipts.
-- Existing payment proof URLs require separate migration; this does not make old public objects private.


-- ============== 015_coupon_rls_permissions.sql ==============
-- Critical security hardening: baseline coupons was omitted from grants/RLS lists.
-- Safe on existing Supabase projects. No coupon rows are deleted or rewritten.
BEGIN;
ALTER TABLE public.coupons ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.coupons FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.coupons TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
COMMIT;
-- Browser clients must never access coupon inventory directly. The Flask
-- backend validates and consumes coupons within place_commerce_order RPC.


-- ============== 016_custom_request_id_type_agnostic.sql ==============
-- Everbloom: fix HTTP 400 / SQLSTATE 22P02 on RPC convert_custom_request
--   ERROR: invalid input syntax for type uuid: "9"
--
-- Cause: public.custom_requests.id is an INTEGER/BIGINT in databases created
-- before migration 001 (CREATE TABLE IF NOT EXISTS kept the old table), but the
-- RPC declared p_request_id as UUID. The admin URL carries the real id ("9"),
-- so PostgREST fails casting it before the function body even runs.
--
-- Fix: accept the id as TEXT and compare against the column as text. Works for
-- uuid, bigint and integer ids. Back up first; safe to re-run.
-- Replaces migration 013's function; run AFTER 013. Does not touch existing
-- orders, change RLS, or alter any table.
BEGIN;

-- The uuid-only overload MUST go. If both overloads exist PostgREST cannot pick
-- one for a JSON string and returns PGRST203 (ambiguous function).
DROP FUNCTION IF EXISTS public.convert_custom_request(uuid, numeric, text);

CREATE OR REPLACE FUNCTION public.convert_custom_request(
  p_request_id text,
  p_price numeric,
  p_note text DEFAULT ''
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  r public.custom_requests%ROWTYPE;
  o public.orders%ROWTYPE;
  p public.products%ROWTYPE;
  v_key text;
  v_fk_type text;
  new_tracking_token text;
BEGIN
  v_key := lower(btrim(coalesce(p_request_id, '')));
  IF v_key = '' THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Request ID is required';
  END IF;
  IF p_price IS NULL OR p_price <= 0 OR p_price > 9999999999.99
     OR p_price <> round(p_price, 2) THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Enter a positive agreed price with at most two decimal places';
  END IF;

  -- Lock the request row (id compared as text, so any id type works). This makes
  -- repeated clicks and concurrent retries idempotent.
  SELECT c.* INTO r FROM public.custom_requests c WHERE c.id::text = v_key FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Custom request does not exist';
  END IF;

  IF r.converted_order_id IS NOT NULL THEN
    SELECT * INTO o FROM public.orders WHERE id = r.converted_order_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Request points to a missing converted order; contact an administrator';
    END IF;
    RETURN to_jsonb(o);
  END IF;

  IF r.status IN ('closed', 'rejected') THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Closed or rejected requests cannot be converted';
  END IF;

  IF r.linked_product_id IS NOT NULL THEN
    SELECT * INTO p FROM public.products WHERE id = r.linked_product_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION USING ERRCODE = '23503', MESSAGE = 'Linked product no longer exists';
    END IF;
  END IF;

  new_tracking_token := replace(gen_random_uuid()::text, '-', '') ||
                        replace(gen_random_uuid()::text, '-', '');

  -- custom_request_id is set separately below because its column type must
  -- match the request id type, which differs between databases.
  INSERT INTO public.orders (
    user_id, name, email, phone, address, total, status,
    is_custom_order, custom_notes, tracking_token,
    preferred_delivery_date, internal_notes
  ) VALUES (
    r.user_id, r.name, r.email, r.phone, 'To be confirmed', p_price,
    'placed', true, r.description, new_tracking_token,
    r.preferred_delivery_date, left(coalesce(p_note, ''), 20000)
  ) RETURNING * INTO o;

  SELECT format_type(a.atttypid, a.atttypmod) INTO v_fk_type
  FROM pg_catalog.pg_attribute a
  WHERE a.attrelid = 'public.orders'::regclass
    AND a.attname = 'custom_request_id' AND NOT a.attisdropped;
  IF v_fk_type IS NOT NULL THEN
    BEGIN
      EXECUTE format('UPDATE public.orders SET custom_request_id = %L::%s WHERE id = $1',
                     r.id::text, v_fk_type) USING o.id;
    EXCEPTION WHEN invalid_text_representation OR datatype_mismatch
              OR cannot_coerce OR numeric_value_out_of_range THEN
      -- Informational back-link only; the authoritative link is
      -- custom_requests.converted_order_id, written below.
      NULL;
    END;
    SELECT * INTO o FROM public.orders WHERE id = o.id;
  END IF;

  INSERT INTO public.order_items (
    order_id, product_id, title, price, quantity, image_url,
    is_custom, availability_mode, personalization
  ) VALUES (
    o.id, r.linked_product_id,
    coalesce(p.title, r.craft_type, 'Custom creation'),
    p_price, 1, coalesce(p.images->>0, r.reference_image_url, ''),
    true, 'MADE_TO_ORDER',
    jsonb_build_object('request', r.description, 'colours', r.colour_preference, 'occasion', r.occasion)
  );

  UPDATE public.custom_requests
  SET status = 'converted', converted_order_id = o.id, quoted_price = p_price
  WHERE id::text = v_key;

  INSERT INTO public.tracking (order_id, status, note)
  VALUES (o.id, 'placed', 'Your custom creation has been confirmed. We will share the next steps.');

  RETURN to_jsonb(o);
END;
$$;

REVOKE ALL ON FUNCTION public.convert_custom_request(text, numeric, text)
FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT EXECUTE ON FUNCTION public.convert_custom_request(text, numeric, text) TO service_role;
COMMIT;

-- Refresh the PostgREST function-signature/schema cache.
NOTIFY pgrst, 'reload schema';

-- Safe, read-only verification:
-- SELECT data_type FROM information_schema.columns
--   WHERE table_schema='public' AND table_name='custom_requests' AND column_name='id';
-- SELECT to_regprocedure('public.convert_custom_request(text,numeric,text)') AS new_signature,
--        to_regprocedure('public.convert_custom_request(uuid,numeric,text)') AS old_signature_must_be_null;


-- ============== 017_receive_material_validation.sql ==============
-- Everbloom: harden receive_material (stock purchases).
--
-- Bug: when "cost_per_unit" (or "quantity") was missing, the old checks
-- (qty<=0 or cpu<0) evaluated to NULL instead of true, so validation was skipped.
-- A missing cost silently overwrote the material's cost_per_unit with NULL (which
-- also zeroed later wastage/costing), and a missing quantity failed with a cryptic
-- NOT NULL violation. Now all inputs are validated up front with a clear message.
-- Same signature (jsonb) and grants, so no app change is needed. Safe to re-run.
BEGIN;

CREATE OR REPLACE FUNCTION public.receive_material(p_data jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  result expenditures%ROWTYPE;
  qty numeric;
  cpu numeric;
  mid bigint;
BEGIN
  IF p_data IS NULL OR jsonb_typeof(p_data) <> 'object' THEN
    RAISE EXCEPTION 'Invalid purchase';
  END IF;
  BEGIN
    qty := nullif(btrim(p_data->>'quantity'), '')::numeric;
    cpu := nullif(btrim(p_data->>'cost_per_unit'), '')::numeric;
    mid := nullif(btrim(p_data->>'material_id'), '')::bigint;
  EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN
    RAISE EXCEPTION 'Invalid purchase';
  END;
  IF mid IS NULL THEN
    RAISE EXCEPTION 'Material not found';
  END IF;
  -- NULL-safe: a missing value must be rejected, not slip past a NULL comparison.
  IF qty IS NULL OR cpu IS NULL OR qty <= 0 OR cpu < 0 THEN
    RAISE EXCEPTION 'Invalid purchase';
  END IF;

  UPDATE raw_materials SET current_stock = current_stock + qty, cost_per_unit = cpu WHERE id = mid;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Material not found';
  END IF;
  INSERT INTO expenditures(material_id, quantity, cost_per_unit, total_cost, supplier, note, reference)
  VALUES (mid, qty, cpu, qty * cpu, p_data->>'supplier', p_data->>'note', p_data->>'reference')
  RETURNING * INTO result;
  RETURN to_jsonb(result);
END $$;

REVOKE ALL ON FUNCTION public.receive_material(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.receive_material(jsonb) TO service_role;
COMMIT;

NOTIFY pgrst, 'reload schema';
