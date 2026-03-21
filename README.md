# 🌿 Everbloom — Full Flask E-Commerce App

A complete handcrafted goods store with admin panel, UPI payments, order tracking, coupons, flash sales, custom orders, and reviews.

---

## Features

### Customer
- Browse products by category, price, stock, sale
- Product detail with image gallery and reviews
- Cart with quantity controls
- Checkout with coupon code support
- Order history with 9-step progress bar
- Live order tracking timeline
- UPI advance payment with screenshot upload
- Custom order request form
- In-app notification bell (polls every 30s)
- Login / Signup / Profile

### Admin Panel
- Dashboard with 8 stat cards
- Orders list with status filter tabs
- Order detail with context-aware action panel:
  - `placed` → set advance amount → email customer UPI QR
  - `advance_paid` → view screenshot → confirm → start crafting
  - All other stages → dropdown to next status + note → email sent
- Product CRUD: title, price, discount %, stock, multiple images, featured toggle
- Flash sale with end date/time
- Coupon management (create, toggle active, delete)
- Custom order requests review panel
- Customer list
- Settings: UPI ID + QR code upload

---

## Setup

### 1. Clone & install

```bash
git clone <your-repo>
cd everbloom
pip install -r requirements.txt
```

### 2. Supabase

1. Go to [supabase.com](https://supabase.com) and create a new project
2. In the SQL Editor, paste and run the full contents of `schema.sql`
3. Go to Storage → create a bucket called `products` (set to **Public**)
4. Copy your Project URL and anon public key

### 3. Gmail App Password

1. Enable 2FA on your Gmail account
2. Go to Google Account → Security → App Passwords
3. Create an app password for "Mail"

### 4. Environment variables

Copy `.env.example` to `.env` and fill in all values:

```
SECRET_KEY=any-random-string
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your-anon-key
MAIL_USERNAME=you@gmail.com
MAIL_PASSWORD=your-app-password
SITE_URL=http://localhost:5000
```

### 5. Run locally

```bash
python app.py
```

### 6. Create your admin account

After signing up normally, go to Supabase → Table Editor → users → find your row → set `is_admin = true`.

### 7. Deploy to Vercel

```bash
npm i -g vercel
vercel
```

Add all 6 env variables in Vercel dashboard → Settings → Environment Variables.

---

## File Structure

```
app.py                          Flask factory + Vercel entrypoint
supa.py                         Supabase REST API wrapper
models.py                       Business logic
emails.py                       Transactional email functions
schema.sql                      Paste into Supabase SQL Editor
requirements.txt
vercel.json

routes/
  auth.py                       Login, signup, logout, profile
  shop.py                       Store, cart, checkout, notifications
  orders.py                     My orders, tracking, pay advance
  admin.py                      Full admin panel

templates/
  base.html                     Customer base layout
  admin/
    base_admin.html             Admin sidebar layout
    dashboard.html
    orders.html
    order_detail.html           Context-aware action panel
    products.html
    product_form.html           Add/edit with flash sale + images
    coupons.html
    customers.html
    custom_requests.html
    custom_request_detail.html
    settings.html
  shop/
    index.html                  Homepage
    shop.html                   Product listing + filters
    product.html                Product detail + reviews
    _product_card.html          Reusable product card partial
    cart.html
    checkout.html               With coupon code
    orders.html                 Order history
    track.html                  9-step tracking timeline
    pay_advance.html            UPI QR + screenshot upload
    custom_order.html
  auth/
    login.html
    signup.html
    profile.html

static/
  css/main.css                  Full Everbloom design system
  css/admin.css                 Admin panel styles
  js/main.js                    Nav, notifications, animations
```

---

## Order Workflow

```
placed → advance_requested → advance_paid → advance_confirmed
→ crafting → quality_check → shipped → delivered
                                              ↘ cancelled (any stage)
```

Every status change sends an email to the customer and creates an in-app notification.

---

## Tech Stack

- **Frontend**: Jinja2 + Vanilla JS + CSS (Cormorant Garamond + Jost)
- **Backend**: Flask (Python) on Vercel serverless
- **Database**: Supabase Postgres via REST API
- **Storage**: Supabase Storage (product images, payment screenshots, QR codes)
- **Email**: Gmail SMTP via Flask-Mail
- **Hosting**: Vercel free tier
