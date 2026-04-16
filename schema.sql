
-- Link custom request to a product listing
alter table custom_requests add column if not exists linked_product_id uuid references products(id);
alter table custom_requests add column if not exists listed_in_shop boolean default false;

-- Link custom requests to products
alter table custom_requests add column if not exists linked_product_id uuid references products(id);
alter table custom_requests add column if not exists listed_in_shop boolean default false;
