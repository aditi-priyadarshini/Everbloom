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
