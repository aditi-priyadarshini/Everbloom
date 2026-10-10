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
