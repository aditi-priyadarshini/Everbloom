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
