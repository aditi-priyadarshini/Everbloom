# 🌸 Everbloom — Flask + Supabase + Vercel

Serverless Flask e-commerce store for handcrafted art.  
**Stack:** Flask · psycopg2 · Supabase (Postgres + Storage) · Flask-Mail · Vercel

---

## 🔄 Order Workflow

```
📋  Customer places order  →  Email: "We'll review it soon"
💌  Admin reviews + sets advance amount  →  Email with UPI QR sent to customer
💳  Customer pays + uploads screenshot
✅  Admin confirms screenshot  →  Email: "Advance confirmed, crafting begins!"
🎨  accepted → 🪵 material_sourced → ✂️ crafting → 🔍 quality_check
📦  packed → 🚚 shipped → 🌸 delivered
```

---

## 🚀 Deploy to Vercel in 5 Steps

### Step 1 — Create Supabase Project

1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Note down your project **ref** (e.g. `abcdefghij`)
3. Go to **Settings → Database → Connection String**
4. Select **"Transaction"** pooler mode (port **6543**) — required for serverless!
5. Copy the URI — it looks like:
   ```
   postgresql://postgres.abcdefghij:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
   ```

### Step 2 — Create Supabase Storage Buckets

In Supabase → **Storage** → New Bucket:

| Bucket name | Public? | Purpose |
|---|---|---|
| `product-images` | ✅ Yes | Product photos |
| `payment-proofs` | ❌ No | Customer payment screenshots |
| `qr-codes` | ✅ Yes | UPI QR code |

### Step 3 — Initialise the Database

After deploying (Step 5), visit:
```
https://your-app.vercel.app/_init?secret=YOUR_INIT_SECRET
```
This creates all tables and seeds the 6 default categories.  
Set `INIT_SECRET` as an env var in Vercel (any random string).

### Step 4 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourname/everbloom.git
git push -u origin main
```

### Step 5 — Deploy on Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project** → Import your GitHub repo
2. Go to **Settings → Environment Variables** and add all of these:

| Variable | Value | Where to find |
|---|---|---|
| `SECRET_KEY` | Any long random string | Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Supabase Transaction pooler URI | Supabase → Settings → Database |
| `SUPABASE_URL` | `https://xxxx.supabase.co` | Supabase → Settings → API |
| `SUPABASE_KEY` | anon public key | Supabase → Settings → API |
| `SUPABASE_SERVICE_KEY` | service_role key | Supabase → Settings → API |
| `MAIL_SERVER` | `smtp.gmail.com` | — |
| `MAIL_PORT` | `587` | — |
| `MAIL_USE_TLS` | `true` | — |
| `MAIL_USERNAME` | your Gmail address | — |
| `MAIL_PASSWORD` | Gmail App Password (16 chars) | Google Account → Security → App Passwords |
| `MAIL_DEFAULT_SENDER` | `Everbloom <you@gmail.com>` | — |
| `STORE_NAME` | `Everbloom` | — |
| `SITE_URL` | `https://your-app.vercel.app` | Your Vercel deployment URL |
| `UPI_ID` | `yourname@upi` | Your UPI app |
| `INIT_SECRET` | Any random string | Keep secret — for `/_ init` route |

3. Click **Deploy**
4. After deploy, visit `https://your-app.vercel.app/_init?secret=YOUR_INIT_SECRET` once

---

## 👤 Create First Admin User

1. Sign up at `/auth/signup`
2. In Supabase → **SQL Editor**, run:
```sql
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
```
3. Log out and back in → you'll land on `/admin/`

---

## 💳 Set Up UPI Payment

Go to **Admin → Settings** and:
1. Upload your UPI QR code image (from GPay / PhonePe / Paytm → Receive Money → Share QR)
2. Enter your UPI ID

The QR image is stored in Supabase Storage and shown on the advance payment page.

---

## 📁 Project Structure

```
everbloom-vercel/
├── app.py              ← Flask factory + Vercel entrypoint
├── db.py               ← psycopg2 connection pool (no SQLAlchemy)
├── models.py           ← SQL query helpers for all tables
├── emails.py           ← All transactional email functions
├── storage.py          ← Supabase Storage upload helpers
├── vercel.json         ← Vercel routing config
├── requirements.txt
├── .env.example        ← Copy to .env for local dev
├── .gitignore
│
├── routes/
│   ├── shop.py         ← Home, shop, product, cart, checkout, notifications
│   ├── auth.py         ← Login, signup, logout, profile
│   ├── orders.py       ← My orders, track, advance payment upload
│   └── admin.py        ← Dashboard, orders, products, customers, settings
│
├── templates/
│   ├── base.html                ← Nav, footer, flash, mobile nav
│   ├── admin/
│   │   ├── base.html            ← Admin sidebar layout
│   │   ├── dashboard.html       ← Stats cards + recent orders
│   │   ├── orders.html          ← Orders list + filter tabs
│   │   ├── order_detail.html    ← Manage order, confirm advance, update status
│   │   ├── products.html        ← Products table
│   │   ├── product_form.html    ← Add/edit product + image upload
│   │   ├── customers.html
│   │   └── settings.html        ← QR code + UPI ID
│   ├── shop/
│   │   ├── home.html
│   │   ├── shop.html
│   │   ├── product.html
│   │   ├── cart.html
│   │   ├── checkout.html
│   │   ├── orders.html
│   │   ├── track.html
│   │   ├── pay_advance.html     ← UPI QR + screenshot upload
│   │   └── _product_card.html
│   ├── auth/
│   │   ├── login.html
│   │   ├── signup.html
│   │   └── profile.html
│   └── errors/
│       ├── 404.html
│       └── 500.html
│
└── static/
    ├── css/style.css
    ├── css/admin.css
    └── js/main.js
```

---

## 💻 Local Development

```bash
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # Fill in your values
python app.py
```

Then visit `http://localhost:5000/_init` once to create tables.

---

## ⚠️ Why No SQLite / SQLAlchemy?

Vercel is **serverless** — each request runs in a fresh container with no persistent filesystem. SQLite files vanish between requests. This app uses:

- **psycopg2** → direct PostgreSQL connection (no ORM overhead)
- **Supabase Transaction Pooler** (port 6543) → handles connection pooling for serverless
- **Supabase Storage** → stores all uploaded images (no local disk writes)

---

## 📧 Gmail App Password Setup

1. Enable 2-Step Verification on your Google Account
2. Go to **Security → App passwords**
3. Create one for "Mail" → copy the 16-character password
4. Use it as `MAIL_PASSWORD` in Vercel env vars

For production volume, switch to [Resend](https://resend.com), [Mailgun](https://mailgun.com), or [SendGrid](https://sendgrid.com) SMTP.

---

## 📊 Order Status Reference

| Status | Triggered by | Email |
|---|---|---|
| `draft` | Customer places order | ✅ |
| `advance_requested` | Admin sets advance amount | ✅ with UPI QR |
| `advance_paid` | Customer uploads screenshot | — |
| `advance_confirmed` | Admin confirms payment | ✅ |
| `accepted` → `delivered` | Admin updates | ✅ each step |
| `cancelled` | Admin | ✅ |

---

*Built with 🌸 — Everbloom Vercel Edition*
