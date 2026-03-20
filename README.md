# 🌸 Everbloom

> A complete handcrafted art & craft e-commerce store — live order tracking, email notifications at every step, and QR-based UPI payment. No payment gateway required.

---

## ✨ Features

- **Customer-facing store** — Home, Shop with filters, Product detail, Cart, Checkout
- **Live order tracking** — 9-step timeline with real-time Supabase updates
- **Email notifications** — Branded email sent at every status change via Resend
- **QR / UPI payment** — Customer scans QR, uploads screenshot, admin verifies
- **In-app notifications** — Bell icon with unread count
- **Admin panel** — Dashboard, product CRUD, order management with one-click status updates
- **Fully mobile responsive** — Hamburger nav, touch-friendly layouts
- **Secure config** — All credentials in `js/env.js`, never hardcoded

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML + CSS + Vanilla JS (no framework) |
| Database | Supabase PostgreSQL |
| Auth | Supabase Auth |
| File Storage | Supabase Storage |
| Realtime | Supabase Realtime |
| Email | Resend (via Supabase Edge Function) |
| Scheduled Jobs | pg_cron (auto-delete delivered orders after 30 days) |

Everything runs on **free tiers** — designed for ~50 orders/month.

---

## 🚀 Setup Guide

### Step 1 — Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Name it `everbloom`, set a strong DB password, choose your region
3. Wait ~2 minutes for provisioning

---

### Step 2 — Set Up the Database

In Supabase → **SQL Editor**, run these two files in order:

1. `supabase/schema.sql` — creates all tables, triggers, pg_cron cleanup job
2. `supabase/rls.sql` — sets up Row Level Security policies

---

### Step 3 — Create Storage Buckets

In Supabase → **Storage** → New Bucket:

| Bucket Name | Public? | Used for |
|---|---|---|
| `product-images` | ✅ Yes | Product photos (admin uploads) |
| `payment-proofs` | ❌ No | Customer payment screenshots |

---

### Step 4 — Configure Environment Variables

Copy the example config file:

```bash
cp js/env.js.example js/env.js
```

Open `js/env.js` and fill in your values:

```javascript
window.ENV = {
  SUPABASE_URL:      'https://xxxx.supabase.co',   // Settings → API → Project URL
  SUPABASE_ANON_KEY: 'eyJhbGci...',               // Settings → API → anon public key
  SITE_URL:          'https://yourstore.com',       // Your live domain (or localhost)
  UPI_ID:            'yourname@upi',               // Your UPI handle
  QR_CODE_IMAGE:     'assets/qr-code.png',         // Path to your UPI QR image
};
```

> ⚠️ **`js/env.js` is listed in `.gitignore` — never commit it with real credentials.**

---

### Step 5 — Set Up Email (Resend)

1. Sign up at [resend.com](https://resend.com) — free tier gives 3,000 emails/month
2. Create an API key in the dashboard
3. Verify your sending domain (or use `@resend.dev` for testing)

Install the Supabase CLI and deploy the Edge Function:

```bash
npm install -g supabase

# Log in and link to your project
supabase login
supabase link --project-ref YOUR_PROJECT_REF   # found in Project Settings → General

# Set secrets (these stay server-side, never in frontend code)
supabase secrets set RESEND_API_KEY=re_xxxxxxxxxxxx
supabase secrets set SITE_URL=https://yourstore.com

# Deploy the function
supabase functions deploy order-notifications
```

---

### Step 6 — Add Your UPI QR Code

1. Open your UPI app (GPay, PhonePe, Paytm) → **Receive Money** → **Share QR**
2. Save the QR image as `assets/qr-code.png` in the project folder
3. Make sure `QR_CODE_IMAGE` in `js/env.js` points to this path

---

### Step 7 — Create the First Admin User

1. Sign up on the website normally (this creates a customer account)
2. In Supabase → **SQL Editor**, promote yourself to admin:

```sql
UPDATE profiles
SET role = 'admin'
WHERE email = 'your-email@example.com';
```

3. Log out and log back in — you'll be redirected to the Admin Panel at `/admin/`

---

## 📁 Project Structure

```
everbloom/
│
├── index.html            ← Home page
├── shop.html             ← Product listing with sidebar filters
├── product.html          ← Product detail + image gallery + add to cart
├── cart.html             ← Shopping cart
├── checkout.html         ← Delivery address + QR payment + screenshot upload
├── orders.html           ← Customer order history
├── track.html            ← Live 9-step order tracking timeline
├── login.html            ← Login
├── signup.html           ← Sign up
│
├── admin/
│   ├── index.html        ← Dashboard (stats, recent orders)
│   ├── products.html     ← Product CRUD + drag-and-drop image upload
│   └── orders.html       ← Order management — update status, send emails
│
├── css/
│   ├── style.css         ← Global styles, Everbloom design system, mobile
│   └── admin.css         ← Admin panel layout + components
│
├── js/
│   ├── env.js            ← ⚠️ Your credentials (DO NOT COMMIT)
│   ├── env.js.example    ← Safe template — commit this instead
│   ├── supabase.js       ← Supabase client, cart, helpers, formatters
│   └── auth.js           ← Nav auth state, notification bell
│
├── assets/
│   └── qr-code.png       ← Your UPI QR code image (add this yourself)
│
├── supabase/
│   ├── schema.sql        ← Full DB schema: tables, triggers, pg_cron
│   ├── rls.sql           ← Row Level Security policies
│   └── functions/
│       └── order-notifications/
│           └── index.ts  ← Deno Edge Function → Resend email
│
├── .gitignore            ← Excludes js/env.js
└── README.md             ← This file
```

---

## 🔄 Order Lifecycle

```
🛒  placed
 ↓  Customer places order, sees QR code for payment
✅  payment_confirmed       → Email: "Payment received"
 ↓  Admin verifies payment screenshot
🎨  accepted                → Email: "Artist accepted your order"
 ↓
🪵  material_sourced        → Email: "Materials being gathered"
 ↓
✂️  crafting                → Email: "Your piece is being handcrafted"
 ↓
🔍  quality_check           → Email: "Almost ready!"
 ↓
📦  packed                  → Email: "Packed and ready to ship"
 ↓
🚚  shipped                 → Email: "Your order is on the way"
 ↓
🌸  delivered               → Email: "Enjoy your Everbloom piece!"
 ↓
🗑️  auto-deleted 30 days after delivery (pg_cron)
```

Every transition also creates an **in-app notification** visible in the customer's bell icon.

---

## 🔒 Security

### Environment Variables

All sensitive config lives in `js/env.js` which is loaded as the very first script on every page. It is excluded from Git via `.gitignore`.

| Variable | Where to find it | Sensitivity |
|---|---|---|
| `SUPABASE_URL` | Supabase → Settings → API → Project URL | Low (public) |
| `SUPABASE_ANON_KEY` | Supabase → Settings → API → anon key | Medium — protected by RLS |
| `SITE_URL` | Your domain | Low |
| `UPI_ID` | Your UPI app | Low |

The `SUPABASE_ANON_KEY` is safe to expose in frontend code **as long as Row Level Security is enabled** on all tables (which `rls.sql` does). It cannot bypass RLS policies.

The `RESEND_API_KEY` is **never in frontend code** — it lives only as a Supabase Edge Function secret (server-side).

### Deploying to Netlify or Vercel

Set environment variables in your hosting dashboard, then use a build script to inject them into `js/env.js` before deployment.

Create `inject-env.js` in the project root (safe to commit — contains no secrets):

```javascript
const fs = require('fs');
fs.writeFileSync('js/env.js', `window.ENV = {
  SUPABASE_URL: '${process.env.SUPABASE_URL}',
  SUPABASE_ANON_KEY: '${process.env.SUPABASE_ANON_KEY}',
  SITE_URL: '${process.env.SITE_URL}',
  UPI_ID: '${process.env.UPI_ID}',
  QR_CODE_IMAGE: 'assets/qr-code.png',
};`);
console.log('✓ env.js generated');
```

Then set your build command to `node inject-env.js` in the Netlify/Vercel dashboard, and add all four variables (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SITE_URL`, `UPI_ID`) as environment variables there.

### Row Level Security Summary

| Table | Customer | Admin |
|---|---|---|
| `products` | Read active only | Full CRUD |
| `orders` | Own orders only | All orders |
| `order_tracking` | Own orders only | All + update |
| `notifications` | Own only | All |
| `profiles` | Own profile | All |

---

## 🌐 Deployment

This is a **static site** — no server needed. Deploy anywhere for free:

| Platform | How |
|---|---|
| [Netlify](https://netlify.com) | Drag & drop the `everbloom/` folder, or connect GitHub |
| [Vercel](https://vercel.com) | `vercel --prod` from the project folder |
| [GitHub Pages](https://pages.github.com) | Push to repo → Settings → Pages → Deploy from branch |
| [Cloudflare Pages](https://pages.cloudflare.com) | Connect GitHub repo, build output set to `/` |

For all platforms: use the `inject-env.js` build script and set the four env vars in the dashboard.

---

## 📊 Free Tier Capacity

| Service | Free Limit | At 50 orders/month |
|---|---|---|
| Supabase DB | 500 MB | Handles thousands of orders |
| Supabase Storage | 1 GB | ~5,000 product images |
| Supabase Edge Functions | 500,000 calls/mo | Handles all email triggers easily |
| Supabase Realtime | 200 concurrent connections | Fine for a small store |
| Resend | 3,000 emails/mo | Covers ~333 orders × 9 emails each |

---

## 🎨 Design System

**Fonts** — Cormorant Garamond (display) + Jost (body) via Google Fonts

**Color tokens** (defined as CSS variables in `css/style.css`)

| Token | Hex | Used for |
|---|---|---|
| `--cream` | `#FAF6F1` | Page background |
| `--brown-dark` | `#2C1810` | Headers, hero, footer |
| `--brown-mid` | `#5C4033` | Body text |
| `--brown-accent` | `#8B5E3C` | Buttons, links, highlights |
| `--brown-light` | `#C4A882` | Muted text on dark backgrounds |
| `--sage` | `#8A9E7B` | Success states, sale badges |
| `--sand` | `#E8DDD4` | Borders, subtle backgrounds |

---

*Built with 🌸 for handcrafted art lovers.*
