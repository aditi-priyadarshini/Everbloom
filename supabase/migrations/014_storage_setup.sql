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
