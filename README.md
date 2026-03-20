# 🌸 Everbloom — Setup Guide

A complete handcrafted art & craft e-commerce store with live order tracking, email notifications, and QR-based UPI payment.

---

## 🚀 Quick Start (5 Steps)

### Step 1 — Create Supabase Project

1. Go to [supabase.com](https://supabase.com) → New Project
2. Choose a name (e.g. `everbloom`), set a strong database password, select your region
3. Wait ~2 minutes for the project to be ready

---

### Step 2 — Set Up the Database

In your Supabase project → **SQL Editor**:

1. Paste and run `supabase/schema.sql` (creates all tables + triggers)
2. Paste and run `supabase/rls.sql` (sets up Row Level Security)

---

### Step 3 — Create Storage Buckets

Go to **Storage** in your Supabase dashboard and create:

| Bucket Name | Public |
|---|---|
| `product-images` | ✅ Yes |
| `payment-proofs` | ❌ No (private) |
| `qr-code` | ✅ Yes |

---

### Step 4 — Connect the Frontend

Open `js/supabase.js` and replace these two values:

```javascript
const SUPABASE_URL = 'YOUR_SUPABASE_URL';        // Project Settings → API → Project URL
const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY'; // Project Settings → API → anon public key
```

---

### Step 5 — Set Up Email (Resend)

1. Sign up at [resend.com](https://resend.com) (free — 3,000 emails/month)
2. Get your API key from the dashboard
3. Verify your sending domain (or use `@resend.dev` for testing)

Deploy the Edge Function:
```bash
# Install Supabase CLI first
npm install -g supabase

# Login and link to your project
supabase login
supabase link --project-ref YOUR_PROJECT_REF

# Set secrets
supabase secrets set RESEND_API_KEY=re_xxxxxxxxxxxx
supabase secrets set SITE_URL=https://yourstore.com

# Deploy
supabase functions deploy order-notifications
```

---

## 👤 Creating the First Admin User

1. Sign up normally on the website (creates a customer account)
2. In Supabase **SQL Editor**, run:

```sql
UPDATE profiles 
SET role = 'admin' 
WHERE email = 'your-admin@email.com';
```

3. Log out and log back in — you'll be redirected to the Admin Panel

---

## 💳 Setting Up UPI Payment

In `checkout.html`, replace the QR code placeholder:

```html
<!-- Replace the emoji placeholder div with: -->
<img src="YOUR_UPI_QR_CODE.png" style="width:200px;height:200px;border-radius:12px">
```

Also update the UPI ID:
```html
<strong id="upi-id">yourname@upi</strong>
```

To generate a UPI QR code, use any UPI app (GPay, PhonePe, Paytm) → Receive Money → Share QR.

---

## 📁 Project Structure

```
everbloom/
├── index.html          ← Home page
├── shop.html           ← Product listing with filters
├── product.html        ← Product detail + add to cart
├── cart.html           ← Shopping cart
├── checkout.html       ← Address + QR payment
├── orders.html         ← Customer order history
├── track.html          ← Live order tracking (9 steps)
├── login.html          ← Login
├── signup.html         ← Sign up
│
├── admin/
│   ├── index.html      ← Dashboard with stats
│   ├── products.html   ← Product CRUD + image upload
│   └── orders.html     ← Order management + status updates
│
├── css/
│   ├── style.css       ← Global styles + Everbloom theme
│   └── admin.css       ← Admin panel styles
│
├── js/
│   ├── supabase.js     ← Client init + cart + helpers
│   └── auth.js         ← Nav auth + notifications
│
└── supabase/
    ├── schema.sql      ← Full database schema
    ├── rls.sql         ← Row Level Security policies
    └── functions/
        └── order-notifications/
            └── index.ts ← Email Edge Function (Resend)
```

---

## 🔄 Order Status Flow

```
🛒 placed → 💳 payment_confirmed → 🎨 accepted
→ 🪵 material_sourced → ✂️ crafting → 🔍 quality_check
→ 📦 packed → 🚚 shipped → 🌸 delivered
```

At **every step**, the customer receives:
- In-app notification (bell icon)
- Beautiful branded email via Resend

---

## 🌐 Deployment

This is a static site — deploy anywhere for free:

- **[Netlify](https://netlify.com)**: Drag & drop the `everbloom/` folder
- **[Vercel](https://vercel.com)**: `vercel --prod`
- **[GitHub Pages](https://pages.github.com)**: Push to a repo, enable Pages
- **[Cloudflare Pages](https://pages.cloudflare.com)**: Connect your repo

---

## 📊 Free Tier Limits

| Service | Limit | Covers |
|---|---|---|
| Supabase DB | 500 MB | Thousands of orders |
| Supabase Storage | 1 GB | ~10,000 product images |
| Supabase Edge Functions | 500K calls/mo | 55K order emails |
| Resend | 3,000 emails/mo | ~333 orders (9 emails each) |

**Perfectly sized for 50 orders/month with room to grow!**

---

## 🎨 Brand Colors

| Name | Hex |
|---|---|
| Cream (bg) | `#FAF6F1` |
| Brown Dark | `#2C1810` |
| Brown Accent | `#8B5E3C` |
| Brown Light | `#C4A882` |
| Sage Green | `#8A9E7B` |

---

*Built with love for handcrafted art. 🌸*
