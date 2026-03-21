# 🌸 Everbloom — Flask Edition

A complete handcrafted art & craft e-commerce store built with **Flask + SQLAlchemy + Flask-Mail**.  
Live order tracking, SMTP email notifications, and UPI/QR advance payment workflow.

---

## ✨ New Order Workflow

```
📋  Order Received          → Customer places order (no payment yet)
 ↓  Admin reviews it
💌  Advance Requested       → Admin sets advance amount → Email with UPI QR sent to customer
 ↓  Customer pays via UPI
💳  Advance Paid            → Customer uploads payment screenshot
 ↓  Admin verifies screenshot
✅  Advance Confirmed       → Admin confirms → Email: crafting begins!
🎨  Accepted by Artist      → Email update
🪵  Raw Material Sourced    → Email update
✂️  Crafting in Progress    → Email update
🔍  Quality Check           → Email update
📦  Packed & Ready          → Email update
🚚  Shipped                 → Email update
🌸  Delivered               → Email update
```

At **every step**: customer gets an email + in-app notification.

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
cd everbloom-flask

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
SECRET_KEY=your-long-random-secret-key

# Database (SQLite for dev, PostgreSQL for prod)
DATABASE_URL=sqlite:///everbloom.db

# Email — Gmail example (use App Password, not your real password)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password
MAIL_DEFAULT_SENDER=Everbloom <your-email@gmail.com>

# Store
STORE_NAME=Everbloom
SITE_URL=http://localhost:5000
UPI_ID=yourname@upi
```

### 3. Run the app

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

### 4. Create the first admin user

1. Sign up at `/auth/signup`
2. Open a Python shell:

```bash
python3 -c "
from app import create_app, db
from models import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(email='your@email.com').first()
    u.role = 'admin'
    db.session.commit()
    print('Admin created!')
"
```

3. Log back in — you'll be redirected to `/admin/`

### 5. Upload your UPI QR code

Go to **Admin → Settings** and upload your UPI QR image.  
Or place it at `static/uploads/qr/upi_qr.png`.

---

## 📁 Project Structure

```
everbloom-flask/
│
├── app.py                    ← Flask app factory + config
├── models.py                 ← SQLAlchemy models (User, Product, Order, etc.)
├── emails.py                 ← All transactional email functions
├── requirements.txt
├── .env.example              ← Copy to .env and fill in
├── .gitignore                ← Excludes .env, uploads, __pycache__
│
├── routes/
│   ├── shop.py               ← Home, shop, product, cart, checkout, notifications
│   ├── auth.py               ← Login, signup, logout, profile
│   ├── orders.py             ← My orders, tracking page, advance payment upload
│   └── admin.py              ← Dashboard, order management, products, settings
│
├── templates/
│   ├── base.html             ← Nav, footer, flash messages, mobile nav
│   ├── admin/
│   │   ├── base.html         ← Admin layout with sidebar
│   │   ├── dashboard.html    ← Stats + recent orders
│   │   ├── orders.html       ← Orders list with filter tabs
│   │   ├── order_detail.html ← THE KEY PAGE — manage status, confirm advance
│   │   ├── products.html     ← Products list
│   │   ├── product_form.html ← Add/edit product with image upload
│   │   ├── customers.html    ← Customer list
│   │   └── settings.html     ← QR code + UPI ID
│   ├── shop/
│   │   ├── home.html         ← Landing page
│   │   ├── shop.html         ← Product listing + filters
│   │   ├── product.html      ← Product detail + add to cart
│   │   ├── cart.html         ← Shopping cart
│   │   ├── checkout.html     ← Delivery address form
│   │   ├── orders.html       ← Customer order history
│   │   ├── track.html        ← Live order tracking timeline
│   │   ├── pay_advance.html  ← UPI QR + screenshot upload
│   │   └── _product_card.html ← Reusable product card partial
│   ├── auth/
│   │   ├── login.html
│   │   ├── signup.html
│   │   └── profile.html
│   └── errors/
│       ├── 404.html
│       └── 500.html
│
└── static/
    ├── css/
    │   ├── style.css         ← Global styles + Everbloom theme + mobile
    │   └── admin.css         ← Admin panel styles
    ├── js/
    │   └── main.js           ← Mobile nav, notifications, helpers
    └── uploads/
        ├── products/         ← Product images (auto-created)
        ├── payments/         ← Payment screenshots (private)
        └── qr/               ← UPI QR code (upi_qr.png)
```

---

## 🔒 Security

| What | How |
|---|---|
| Passwords | Hashed with Werkzeug `generate_password_hash` (PBKDF2-SHA256) |
| Forms | CSRF protection on every POST via Flask-WTF |
| Auth | Flask-Login session management with `@login_required` |
| Admin | `@admin_required` decorator on all admin routes |
| Uploads | `secure_filename()` on all uploads, type whitelisting |
| Secrets | All in `.env` file — never in source code |
| Payment proofs | Served only through authenticated admin route |

---

## 📧 Email Setup (Gmail)

1. Go to your Google Account → **Security → 2-Step Verification** (enable it)
2. Then **Security → App passwords** → Generate one for "Mail"
3. Use that 16-character password as `MAIL_PASSWORD` in `.env`

For production, use **Mailgun**, **SendGrid**, or **Resend** SMTP — all have free tiers.

---

## 🌐 Production Deployment

### Gunicorn + Nginx (VPS)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
```

### Railway / Render (free hosting)

1. Push to GitHub
2. Connect repo to Railway or Render
3. Set all `.env` variables in the dashboard
4. Set start command: `gunicorn "app:create_app()"`

### PostgreSQL for production

```env
DATABASE_URL=postgresql://user:password@host:5432/everbloom
```

---

## 📊 Order Status Reference

| Status | Triggered by | Email sent |
|---|---|---|
| `draft` | Customer places order | ✅ "Order received" |
| `advance_requested` | Admin reviews + sets amount | ✅ "Pay advance" with UPI QR |
| `advance_paid` | Customer uploads screenshot | ❌ (admin notified via dashboard) |
| `advance_confirmed` | Admin confirms screenshot | ✅ "Advance confirmed, crafting begins" |
| `accepted` | Admin updates | ✅ |
| `material_sourced` | Admin updates | ✅ |
| `crafting` | Admin updates | ✅ |
| `quality_check` | Admin updates | ✅ |
| `packed` | Admin updates | ✅ |
| `shipped` | Admin updates | ✅ |
| `delivered` | Admin updates | ✅ |
| `cancelled` | Admin updates | ✅ |

---

## 🎨 Design System

**Fonts** — Cormorant Garamond (display) + Jost (body)

| Token | Hex | Used for |
|---|---|---|
| `--cream` | `#FAF6F1` | Page background |
| `--brown-dark` | `#2C1810` | Hero, footer, headers |
| `--brown-accent` | `#8B5E3C` | Buttons, links |
| `--brown-light` | `#C4A882` | Muted on dark bg |
| `--sage` | `#8A9E7B` | Success, sale badges |
| `--sand` | `#E8DDD4` | Borders, subtle bg |

---

*Built with 🌸 — Everbloom Flask Edition*
