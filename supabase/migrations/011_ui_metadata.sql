-- Category archive/restore support. Existing categories remain active.
-- Public visibility additionally requires at least one published product.
begin;
alter table categories add column if not exists active boolean not null default true;
-- Optional per-image alternative text, aligned with the existing images array.
alter table products add column if not exists image_alt_texts jsonb not null default '[]';
commit;
