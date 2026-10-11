-- Canonical setup is the ordered, additive migrations in supabase/migrations/.
-- With psql, from this directory:
\ir supabase/migrations/001_legacy_baseline.sql
\ir supabase/migrations/002_commerce.sql
\ir supabase/migrations/003_transactions.sql
\ir supabase/migrations/004_inventory_operations.sql
\ir supabase/migrations/005_merchandising.sql
\ir supabase/migrations/006_custom_conversion.sql
\ir supabase/migrations/007_order_states.sql
\ir supabase/migrations/008_order_validation.sql
\ir supabase/migrations/009_order_updates.sql
\ir supabase/migrations/010_backend_permissions.sql
\ir supabase/migrations/011_ui_metadata.sql
\ir supabase/migrations/012_product_insert_repair.sql
\ir supabase/migrations/013_custom_conversion_repair.sql
\ir supabase/migrations/014_storage_setup.sql
\ir supabase/migrations/015_coupon_rls_permissions.sql
