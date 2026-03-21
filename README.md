# 🌿 Everbloom

Handcrafted art & craft store. Flask + Supabase REST API + Vercel.

---

## Deploy in 3 steps

### Step 1 — Supabase (2 minutes)

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** → paste the entire contents of `schema.sql` → click **Run**
3. Go to **Storage** → create these 3 buckets:
   - `product-images` → toggle **Public** ON
   - `payment-proofs` → leave Private
   - `qr-codes` → toggle **Public** ON
4. Go to **Settings → API** → copy your **Project URL** and **anon public key**

### Step 2 — Vercel (2 minutes)

1. Push this folder to GitHub
2. Import at [vercel.com](https://vercel.com) → New Project
3. Add these environment variables:

```
SECRET_KEY          →  any long random string
SUPABASE_URL        →  https://xxxx.supabase.co
SUPABASE_KEY        →  your anon public key
MAIL_USERNAME       →  your@gmail.com
MAIL_PASSWORD       →  your Gmail App Password (see below)
SITE_URL            →  https://your-app.vercel.app
```

Optional:
```
STORE_NAME          →  Everbloom
UPI_ID              →  yourname@upi
SUPABASE_SERVICE_KEY→  service_role key (for Storage uploads)
```

4. Deploy!

### Step 3 — Create Admin User (1 minute)

1. Sign up on your live site at `/auth/signup`
2. In Supabase → **SQL Editor** run:
```sql
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
```
3. Log out, log back in → you'll see the **Admin** button in the nav

---

## Gmail App Password

1. Enable 2-Step Verification on your Google Account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create an App Password → use it as `MAIL_PASSWORD`

---

## How the order workflow works

```
Customer places order  →  no payment yet
         ↓
Admin reviews in dashboard → sets advance amount
         ↓
Customer gets email with UPI QR → pays → uploads screenshot
         ↓
Admin sees screenshot → confirms → crafting begins
         ↓
Status updates: Crafting → Quality Check → Shipped → Delivered
(email sent at every step)
```

---

## Upload your UPI QR

Go to **Admin → Settings** → upload your QR image (from GPay/PhonePe → Receive Money → Share QR).

---

## Architecture

```
Flask app (Vercel serverless)
    ↓  HTTP calls only
Supabase REST API
    ├── Database (Postgres) — all tables
    └── Storage — product images, payment proofs, QR code
```

No drivers. No connection strings. Just `SUPABASE_URL` + `SUPABASE_KEY`.
