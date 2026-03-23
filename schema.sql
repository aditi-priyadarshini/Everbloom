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
  ('upi_qr_url', ''),
  ('whatsapp_number', ''),
  ('instagram_handle', ''),
  ('store_name', 'Everbloom'),
  ('store_tagline', 'Handcrafted with Love')
on conflict do nothing;

-- Product Variants
create table if not exists variants (
  id serial primary key,
  product_id uuid references products(id) on delete cascade,
  name text not null,
  value text not null,
  price_modifier numeric(10,2) default 0,
  stock integer default 0
);

-- Wishlist
create table if not exists wishlists (
  id serial primary key,
  user_id uuid references users(id) on delete cascade,
  product_id uuid references products(id) on delete cascade,
  created_at timestamptz default now(),
  unique(user_id, product_id)
);

-- Back in Stock Alerts
create table if not exists back_in_stock_alerts (
  id serial primary key,
  product_id uuid references products(id) on delete cascade,
  email text not null,
  user_id uuid references users(id),
  notified boolean default false,
  created_at timestamptz default now(),
  unique(product_id, email)
);

-- Gift Cards
create table if not exists gift_cards (
  id serial primary key,
  code text unique not null,
  amount numeric(10,2) not null,
  balance numeric(10,2) not null,
  issued_to text,
  active boolean default true,
  expires_at timestamptz,
  created_at timestamptz default now()
);

-- Returns
create table if not exists returns (
  id serial primary key,
  order_id uuid references orders(id),
  user_id uuid references users(id),
  reason text not null,
  description text,
  image_url text,
  status text default 'pending',
  admin_note text,
  created_at timestamptz default now()
);

-- Artisans
create table if not exists artisans (
  id serial primary key,
  name text not null,
  bio text,
  location text,
  speciality text,
  image_url text,
  instagram text,
  active boolean default true,
  created_at timestamptz default now()
);

-- FAQs
create table if not exists faqs (
  id serial primary key,
  question text not null,
  answer text not null,
  category text default 'general',
  sort_order integer default 0,
  active boolean default true
);

insert into faqs (question, answer, category, sort_order) values
  ('How do I place an order?', 'Browse our collection, add items to cart and checkout. No payment is needed upfront — we review your order first.', 'ordering', 1),
  ('When do I pay?', 'We collect a small advance via UPI after reviewing your order, and the balance on delivery.', 'payments', 2),
  ('How long does crafting take?', 'Each product page shows an estimated crafting time. Typically 5–14 days depending on complexity.', 'shipping', 3),
  ('Can I request a custom piece?', 'Yes! Visit our Custom Order page and describe what you have in mind. We will get back within 2–3 days.', 'ordering', 4),
  ('What is your return policy?', 'We accept returns within 7 days of delivery for damaged or defective items. Submit a return request from your orders page.', 'returns', 5)
on conflict do nothing;

-- Broadcast Emails Log
create table if not exists broadcasts (
  id serial primary key,
  subject text not null,
  body text not null,
  sent_to integer default 0,
  created_at timestamptz default now()
);

-- ── DISABLE ROW LEVEL SECURITY ON ALL TABLES ──
-- Run this after creating tables to allow API access
alter table if exists users disable row level security;
alter table if exists categories disable row level security;
alter table if exists products disable row level security;
alter table if exists orders disable row level security;
alter table if exists order_items disable row level security;
alter table if exists tracking disable row level security;
alter table if exists notifications disable row level security;
alter table if exists reviews disable row level security;
alter table if exists custom_requests disable row level security;
alter table if exists coupons disable row level security;
alter table if exists settings disable row level security;
alter table if exists variants disable row level security;
alter table if exists wishlists disable row level security;
alter table if exists back_in_stock_alerts disable row level security;
alter table if exists gift_cards disable row level security;
alter table if exists returns disable row level security;
alter table if exists artisans disable row level security;
alter table if exists faqs disable row level security;
alter table if exists broadcasts disable row level security;

-- Email Templates
create table if not exists email_templates (
  id text primary key,
  name text not null,
  subject text not null,
  body text not null,
  updated_at timestamptz default now()
);

insert into email_templates (id, name, subject, body) values
('order_placed', 'Order Placed', 'Order Placed — Everbloom',
'<h2 style="color:#5c3d3d;">Order Placed!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>
Your order <strong>#{{order_id}}</strong> has been placed successfully.
Our team will review it and send you payment details shortly.</p>
<p style="color:#3a2a2a;"><strong>Total:</strong> ₹{{total}}</p>
<p style="color:#7a5c5c;font-size:14px;">No payment needed right now.</p>'),

('advance_requested', 'Advance Payment Request', 'Advance Payment Required — Everbloom',
'<h2 style="color:#5c3d3d;">Advance Payment Required</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>
Please pay an advance of <strong>₹{{advance_amount}}</strong> to confirm your order.</p>
<p style="color:#3a2a2a;"><strong>UPI ID:</strong> {{upi_id}}</p>
<p><a href="{{pay_link}}" style="display:inline-block;background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;">Upload Payment Screenshot</a></p>'),

('advance_confirmed', 'Advance Confirmed', 'Your Order is Being Crafted — Everbloom',
'<h2 style="color:#5c3d3d;">Payment Confirmed!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>
We''ve confirmed your payment and our artisans have begun crafting your order <strong>#{{order_id}}</strong>.</p>
<p style="color:#7a5c5c;">We''ll keep you updated every step of the way.</p>'),

('shipped', 'Order Shipped', 'Your Order is Shipped — Everbloom',
'<h2 style="color:#5c3d3d;">Your Order is on its Way!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>
Your handcrafted order <strong>#{{order_id}}</strong> has been shipped and is on its way to you.</p>'),

('delivered', 'Order Delivered', 'Order Delivered — Everbloom',
'<h2 style="color:#5c3d3d;">Order Delivered!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>
Your order <strong>#{{order_id}}</strong> has been delivered. We hope you love it!</p>
<p style="color:#3a2a2a;">Balance due: <strong>₹{{balance}}</strong></p>'),

('cancelled', 'Order Cancelled', 'Order Cancelled — Everbloom',
'<h2 style="color:#5c3d3d;">Order Cancelled</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>
Your order <strong>#{{order_id}}</strong> has been cancelled.</p>'),

('welcome', 'Welcome Email', 'Welcome to Everbloom!',
'<h2 style="color:#5c3d3d;">Welcome to Everbloom!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>
Your account has been created. Browse our handcrafted collection and find something you''ll treasure.</p>')
on conflict (id) do nothing;

-- Email Templates
create table if not exists email_templates (
  id serial primary key,
  key text unique not null,
  subject text not null,
  body_html text not null,
  updated_at timestamptz default now()
);

insert into email_templates (key, subject, body_html) values
('order_placed', 'Order Placed — Everbloom', '<h2 style="color:#5c3d3d;">Order Placed!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Your order <strong>#{{order_id}}</strong> has been placed successfully. Our team will review it and send you payment details shortly.</p>
<p style="color:#3a2a2a;"><strong>Total:</strong> ₹{{total}}</p>
<p style="color:#7a5c5c;font-size:14px;">No payment needed right now.</p>'),
('advance_requested', 'Advance Payment Required — Everbloom', '<h2 style="color:#5c3d3d;">Advance Payment Required</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Please pay an advance of <strong>₹{{advance_amount}}</strong> to confirm your order.</p>
<p style="color:#3a2a2a;"><strong>UPI ID:</strong> {{upi_id}}</p>
<p><a href="{{pay_link}}" style="background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;">Upload Payment Screenshot</a></p>'),
('advance_confirmed', 'Your Order is Being Crafted — Everbloom', '<h2 style="color:#5c3d3d;">Payment Confirmed!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Your payment has been confirmed and crafting has begun! Order <strong>#{{order_id}}</strong>.</p>'),
('crafting', 'Crafting in Progress — Everbloom', '<h2 style="color:#5c3d3d;">Crafting in Progress</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Our artisans are working on your order <strong>#{{order_id}}</strong>. We''ll keep you updated!</p>'),
('quality_check', 'Quality Check — Everbloom', '<h2 style="color:#5c3d3d;">Quality Check</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Your order <strong>#{{order_id}}</strong> is undergoing quality inspection. Almost ready!</p>'),
('shipped', 'Your Order is Shipped — Everbloom', '<h2 style="color:#5c3d3d;">Your Order is Shipped!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Your handcrafted piece is on its way! Order <strong>#{{order_id}}</strong>.</p>'),
('delivered', 'Order Delivered — Everbloom', '<h2 style="color:#5c3d3d;">Order Delivered!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Thank you for shopping with Everbloom! Balance due: <strong>₹{{balance}}</strong>.</p>'),
('cancelled', 'Order Cancelled — Everbloom', '<h2 style="color:#5c3d3d;">Order Cancelled</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Your order <strong>#{{order_id}}</strong> has been cancelled. Contact us if you have questions.</p>'),
('welcome', 'Welcome to Everbloom!', '<h2 style="color:#5c3d3d;">Welcome to Everbloom!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>Your account has been created. Browse our handcrafted collection and find something you''ll treasure.</p>'),
('custom_request', 'Custom Request Received — Everbloom', '<h2 style="color:#5c3d3d;">Custom Order Request Received!</h2>
<p style="color:#3a2a2a;">Hi {{name}},<br>We''ve received your custom order request and will get back to you within 2–3 business days.</p>')
on conflict (key) do nothing;
