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
