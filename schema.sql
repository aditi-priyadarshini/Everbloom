-- Everbloom Database Schema
-- Paste into Supabase SQL Editor

-- Users
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  password_hash text not null,
  name text,
  phone text,
  address text,
  is_admin boolean default false,
  created_at timestamptz default now()
);

-- Categories
create table if not exists categories (
  id serial primary key,
  name text not null,
  slug text unique not null,
  description text,
  image_url text
);

insert into categories (name, slug) values
  ('Paintings', 'paintings'),
  ('DIY Kits', 'diy-kits'),
  ('Sculptures', 'sculptures')
on conflict do nothing;

-- Products
create table if not exists products (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  price numeric(10,2) not null,
  discount_percent integer default 0,
  images text[] default '{}',
  stock integer default 0,
  category_id integer references categories(id),
  featured boolean default false,
  is_flash_sale boolean default false,
  flash_sale_ends_at timestamptz,
  crafting_days integer default 7,
  created_at timestamptz default now()
);

-- Coupons
create table if not exists coupons (
  id serial primary key,
  code text unique not null,
  discount_percent integer not null,
  max_uses integer default 100,
  used_count integer default 0,
  expires_at timestamptz,
  active boolean default true,
  created_at timestamptz default now()
);

-- Orders
create table if not exists orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  name text not null,
  phone text not null,
  address text not null,
  total numeric(10,2) not null,
  advance_amount numeric(10,2) default 0,
  coupon_code text,
  discount_amount numeric(10,2) default 0,
  status text default 'placed',
  payment_screenshot_url text,
  is_custom_order boolean default false,
  custom_notes text,
  created_at timestamptz default now()
);

-- Order Items
create table if not exists order_items (
  id serial primary key,
  order_id uuid references orders(id),
  product_id uuid references products(id),
  title text not null,
  price numeric(10,2) not null,
  quantity integer not null,
  image_url text
);

-- Tracking
create table if not exists tracking (
  id serial primary key,
  order_id uuid references orders(id),
  status text not null,
  note text,
  created_at timestamptz default now()
);

-- Notifications
create table if not exists notifications (
  id serial primary key,
  user_id uuid references users(id),
  message text not null,
  link text,
  read boolean default false,
  created_at timestamptz default now()
);

-- Reviews
create table if not exists reviews (
  id serial primary key,
  product_id uuid references products(id),
  user_id uuid references users(id),
  rating integer check (rating between 1 and 5),
  comment text,
  created_at timestamptz default now(),
  unique(product_id, user_id)
);

-- Custom Order Requests
create table if not exists custom_requests (
  id serial primary key,
  user_id uuid references users(id),
  name text not null,
  email text not null,
  phone text,
  description text not null,
  budget text,
  reference_image_url text,
  status text default 'pending',
  admin_note text,
  created_at timestamptz default now()
);

-- UPI Settings
create table if not exists settings (
  key text primary key,
  value text
);

insert into settings (key, value) values
  ('upi_id', 'yourname@upi'),
  ('upi_qr_url', '')
on conflict do nothing;
