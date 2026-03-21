# 🌿 Everbloom — Flask + Supabase + Vercel

Handcrafted art & craft e-commerce store. Serverless-ready, fully tested.

---

## ✨ Order Workflow

```
📋 Customer places order  →  No payment yet
💌 Admin reviews & sets advance amount  →  Email with UPI QR sent to customer
💳 Customer pays & uploads screenshot
✅ Admin confirms screenshot  →  Email: crafting begins!
🎨 Crafting  →  🔍 Quality Check  →  🚚 Shipped  →  🌿 Delivered
```

---

## 🚀 Deploy in 5 Steps

### 1. Supabase Setup
- Create project at [supabase.com](https://supabase.com)
- **Settings → Database → Connection String → Transaction pooler (port 6543)** — copy this URI
- Create 3 Storage buckets:
  - `product-images` → Public
  - `payment-proofs` → Private
  - `qr-codes` → Public

### 2. Push to GitHub
```bash
git init && git add . && git commit -m "init"
git remote add origin https://github.com/yourname/everbloom.git
git push -u origin main
```

### 3. Deploy on Vercel
- Import repo at [vercel.com](https://vercel.com)
- Add these environment variables:

| Variable | Where to find |
|---|---|
| `SECRET_KEY` | Any long random string |
| `DATABASE_URL` | Supabase → Settings → Database → Transaction pooler URI (port 6543) |
| `SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase → Settings → API → service_role key |
| `MAIL_SERVER` | `smtp.gmail.com` |
| `MAIL_PORT` | `587` |
| `MAIL_USE_TLS` | `true` |
| `MAIL_USERNAME` | your Gmail address |
| `MAIL_PASSWORD` | Gmail App Password (16 chars — see below) |
| `MAIL_SENDER` | `Everbloom <you@gmail.com>` |
| `STORE_NAME` | `Everbloom` |
| `SITE_URL` | `https://your-app.vercel.app` |
| `UPI_ID` | `yourname@upi` |
| `INIT_SECRET` | Any random string (keep it secret) |

### 4. Initialise Database
After deploying, visit once:
```
https://your-app.vercel.app/_init?secret=YOUR_INIT_SECRET
```
This creates all tables and seeds the 6 categories.

### 5. Create Admin User
1. Sign up at `/auth/signup`
2. In Supabase → SQL Editor, run:
```sql
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
```
3. Log out and back in — you'll see the **Admin** button in the nav

---

## 💳 Gmail App Password Setup

1. Enable 2-Step Verification on your Google Account
2. Go to **myaccount.google.com → Security → App passwords**
3. Generate one for "Mail"
4. Use the 16-character password as `MAIL_PASSWORD`

---

## 🗂️ Project Structure

```
everbloom/
├── app.py              ← Flask factory + Vercel entrypoint
├── db.py               ← psycopg2 connection pool
├── models.py           ← All DB query helpers
├── emails.py           ← Transactional email functions
├── storage.py          ← Supabase Storage uploads
├── vercel.json         ← Vercel routing config
├── requirements.txt
├── .env.example
│
├── routes/
│   ├── auth.py         ← Login, signup, logout, profile
│   ├── shop.py         ← Home, shop, product, cart, checkout
│   ├── orders.py       ← My orders, tracking, advance payment
│   └── admin.py        ← Dashboard, order mgmt, products, settings
│
├── templates/
│   ├── base.html
│   ├── admin/          ← dashboard, orders, order_detail, products, settings
│   ├── shop/           ← home, shop, product, cart, checkout, track, orders
│   ├── auth/           ← login, signup, profile
│   └── errors/         ← 404, 500
│
└── static/
    ├── css/main.css    ← Full design system (Playfair + DM Sans, earthy tones)
    └── js/main.js      ← Mobile nav, notifications, helpers
```

---

## 🎨 Design

- **Fonts** — Playfair Display (headings) + DM Sans (body)
- **Palette** — Ink `#1C0A00` · Clay `#8B4513` · Terracotta `#C1440E` · Gold `#D4A96A` · Cream `#FDF8F3`
- **Style** — Earthy, artisan, warm — designed specifically for a handcraft store

---

## 🔒 Security

| What | How |
|---|---|
| Passwords | `werkzeug.security` PBKDF2-SHA256 |
| Forms | CSRF on every POST via Flask-WTF |
| Auth | Flask-Login `@login_required` |
| Admin | `@admin_only` decorator on all admin routes |
| Files | `secure_filename` + type whitelist |
| Secrets | Environment variables only |
| Login | Always redirects to homepage (never auto-opens admin) |

---

## ⚠️ Why psycopg2, not SQLAlchemy?

Vercel is serverless — no persistent disk, no SQLite. This app uses:
- **psycopg2** — direct Postgres, no ORM
- **Supabase Transaction Pooler (port 6543)** — handles connection pooling for serverless
- **Supabase Storage** — all uploaded images stored in cloud, not local disk

---

*Built with 🌿 for handcrafted art lovers*
