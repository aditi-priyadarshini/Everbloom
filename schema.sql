-- ============================================================
-- EVERBLOOM — Paste this into Supabase SQL Editor and run it.
-- Takes about 5 seconds. Run it only once.
-- ============================================================

create table if not exists users (
  id            bigserial primary key,
  full_name     text not null,
  email         text unique not null,
  phone         text default '',
  address       text default '',
  password_hash text not null,
  role          text default 'customer',
  created_at    timestamptz default now()
);

create table if not exists categories (
  id          bigserial primary key,
  name        text not null,
  slug        text unique not null,
  icon        text default '🎨',
  description text default ''
);

create table if not exists products (
  id               bigserial primary key,
  title            text not null,
  description      text default '',
  price            numeric(10,2) not null,
  discount_percent integer default 0,
  images           text default '',
  category_id      bigint references categories(id),
  stock_qty        integer default 0,
  is_featured      boolean default false,
  is_active        boolean default true,
  tags             text default '',
  created_at       timestamptz default now()
);

create table if not exists orders (
  id             bigserial primary key,
  customer_id    bigint references users(id) not null,
  total_amount   numeric(10,2) not null,
  advance_amount numeric(10,2) default 0,
  advance_proof  text default '',
  addr_name      text default '',
  addr_phone     text default '',
  addr_street    text default '',
  addr_city      text default '',
  addr_state     text default '',
  addr_pin       text default '',
  notes          text default '',
  admin_note     text default '',
  status         text default 'placed',
  delivered_at   timestamptz,
  created_at     timestamptz default now()
);

create table if not exists order_items (
  id         bigserial primary key,
  order_id   bigint references orders(id) on delete cascade,
  product_id bigint references products(id),
  quantity   integer not null,
  unit_price numeric(10,2) not null,
  title_snap text default '',
  image_snap text default ''
);

create table if not exists tracking (
  id         bigserial primary key,
  order_id   bigint references orders(id) on delete cascade,
  status     text not null,
  note       text default '',
  created_at timestamptz default now()
);

create table if not exists notifications (
  id         bigserial primary key,
  user_id    bigint references users(id) on delete cascade,
  order_id   bigint references orders(id) on delete set null,
  title      text not null,
  message    text not null,
  is_read    boolean default false,
  created_at timestamptz default now()
);

-- Seed categories
insert into categories (name, slug, icon, description) values
  ('Paintings',  'paintings',  '🎨', 'Original hand-painted artworks'),
  ('Pottery',    'pottery',    '🏺', 'Handcrafted clay and ceramic pieces'),
  ('Jewellery',  'jewellery',  '💍', 'Artisan-made jewellery'),
  ('DIY Kits',   'diy-kits',   '🧰', 'Complete craft kits for home'),
  ('Textiles',   'textiles',   '🧵', 'Handwoven and embroidered fabrics'),
  ('Sculptures', 'sculptures', '🗿', 'Three-dimensional art pieces')
on conflict (slug) do nothing;

-- Disable RLS (we handle auth in Flask, not Supabase Auth)
alter table users          disable row level security;
alter table categories     disable row level security;
alter table products       disable row level security;
alter table orders         disable row level security;
alter table order_items    disable row level security;
alter table tracking       disable row level security;
alter table notifications  disable row level security;
