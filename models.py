from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import supa

# ── Order statuses ────────────────────────────────────────────
STATUSES = [
    ("placed",            "Order Placed",             "📋"),
    ("advance_requested", "Advance Requested",         "💌"),
    ("advance_paid",      "Advance Paid",              "💳"),
    ("advance_confirmed", "Advance Confirmed",         "✅"),
    ("crafting",          "Being Crafted",             "🎨"),
    ("quality_check",     "Quality Check",             "🔍"),
    ("shipped",           "Shipped",                   "🚚"),
    ("delivered",         "Delivered",                 "🌿"),
    ("cancelled",         "Cancelled",                 "❌"),
]
STATUS_KEYS   = [s[0] for s in STATUSES]
STATUS_LABELS = {s[0]: s[1] for s in STATUSES}
STATUS_ICONS  = {s[0]: s[2] for s in STATUSES}


# ── Price helpers ─────────────────────────────────────────────
def final_price(p):
    return round(float(p["price"]) * (1 - (p.get("discount_percent") or 0) / 100), 2)

def img_list(p):
    return [i.strip() for i in (p.get("images") or "").split(",") if i.strip()]

def first_img(p):
    imgs = img_list(p)
    return imgs[0] if imgs else ""


# ── User ──────────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, row):
        for k, v in row.items():
            setattr(self, k, v)

    @property
    def is_admin(self):
        return self.role == "admin"

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @staticmethod
    def get(uid):
        row = supa.select_one("users", {"id": f"eq.{uid}"})
        return User(row) if row else None

    @staticmethod
    def by_email(email):
        row = supa.select_one("users", {"email": f"eq.{email}"})
        return User(row) if row else None

    @staticmethod
    def create(full_name, email, phone, password):
        ph = generate_password_hash(password)
        row = supa.insert("users", {
            "full_name": full_name, "email": email,
            "phone": phone, "password_hash": ph
        })
        return row["id"] if row else None

    @staticmethod
    def update(uid, full_name, phone, address):
        supa.update("users", {"id": f"eq.{uid}"},
                    {"full_name": full_name, "phone": phone, "address": address})

    @staticmethod
    def all_customers(q="", page=1, per=20):
        rows = supa.select("users",
                           filters={"role": "eq.customer", "order": "created_at.desc",
                                    "limit": per, "offset": (page-1)*per})
        total = supa.count("users", {"role": "eq.customer"})
        if q:
            rows = [r for r in rows if q.lower() in r["full_name"].lower() or q.lower() in r["email"].lower()]
        return rows or [], total


# ── Category ──────────────────────────────────────────────────
class Category:
    @staticmethod
    def all():
        return supa.select("categories", order="name") or []

    @staticmethod
    def by_slug(slug):
        return supa.select_one("categories", {"slug": f"eq.{slug}"})


# ── Product ───────────────────────────────────────────────────
class Product:
    @staticmethod
    def get(pid):
        rows = supa.select("products", filters={"id": f"eq.{pid}", "is_active": "eq.true"})
        if not rows:
            return None
        p = rows[0]
        # attach category
        if p.get("category_id"):
            cat = supa.select_one("categories", {"id": f"eq.{p['category_id']}"})
            if cat:
                p["cat_name"] = cat["name"]
                p["cat_slug"] = cat["slug"]
                p["cat_icon"] = cat["icon"]
        return p

    @staticmethod
    def get_any(pid):
        """Get even if inactive (for admin)."""
        rows = supa.select("products", filters={"id": f"eq.{pid}"})
        return rows[0] if rows else None

    @staticmethod
    def featured(n=4):
        rows = supa.select("products",
                           filters={"is_active": "eq.true", "is_featured": "eq.true"},
                           limit=n, order="created_at.desc") or []
        return Product._attach_cats(rows)

    @staticmethod
    def newest(n=8):
        rows = supa.select("products",
                           filters={"is_active": "eq.true"},
                           limit=n, order="created_at.desc") or []
        return Product._attach_cats(rows)

    @staticmethod
    def list(cat_id=None, q="", sort="newest", min_p=None, max_p=None,
             in_stock=False, on_sale=False, page=1, per=12):
        filters = {"is_active": "eq.true"}
        if cat_id:
            filters["category_id"] = f"eq.{cat_id}"
        if in_stock:
            filters["stock_qty"] = "gt.0"
        if on_sale:
            filters["discount_percent"] = "gt.0"
        if min_p is not None:
            filters["price"] = f"gte.{min_p}"
        if max_p is not None:
            filters["price"] = f"lte.{max_p}"

        order_map = {"price_asc": "price.asc", "price_desc": "price.desc",
                     "discount": "discount_percent.desc", "newest": "created_at.desc"}
        order = order_map.get(sort, "created_at.desc")

        filters["limit"]  = per
        filters["offset"] = (page - 1) * per

        rows = supa.select("products", filters=filters, order=order) or []
        if q:
            rows = [r for r in rows if q.lower() in r["title"].lower()]
        total = supa.count("products", {"is_active": "eq.true"})
        return Product._attach_cats(rows), total

    @staticmethod
    def related(cat_id, exclude_id, n=4):
        rows = supa.select("products",
                           filters={"category_id": f"eq.{cat_id}",
                                    "is_active": "eq.true",
                                    "id": f"neq.{exclude_id}"},
                           limit=n) or []
        return Product._attach_cats(rows)

    @staticmethod
    def admin_list(q="", cat_id=None, page=1, per=20):
        filters = {"limit": per, "offset": (page-1)*per}
        if cat_id:
            filters["category_id"] = f"eq.{cat_id}"
        rows = supa.select("products", filters=filters, order="created_at.desc") or []
        if q:
            rows = [r for r in rows if q.lower() in r["title"].lower()]
        total = supa.count("products")
        return Product._attach_cats(rows), total

    @staticmethod
    def _attach_cats(rows):
        cats = {c["id"]: c for c in Category.all()}
        for r in rows:
            cat = cats.get(r.get("category_id"))
            if cat:
                r["cat_name"] = cat["name"]
                r["cat_slug"] = cat["slug"]
                r["cat_icon"] = cat["icon"]
        return rows

    @staticmethod
    def create(data):
        row = supa.insert("products", data)
        return row["id"] if row else None

    @staticmethod
    def update(pid, data):
        supa.update("products", {"id": f"eq.{pid}"}, data)

    @staticmethod
    def deduct(pid, qty):
        p = Product.get_any(pid)
        if p:
            new_qty = max(0, (p.get("stock_qty") or 0) - qty)
            supa.update("products", {"id": f"eq.{pid}"}, {"stock_qty": new_qty})

    @staticmethod
    def hide(pid):
        supa.update("products", {"id": f"eq.{pid}"}, {"is_active": False})


# ── Order ─────────────────────────────────────────────────────
class Order:
    @staticmethod
    def create(customer_id, total, addr, notes):
        row = supa.insert("orders", {
            "customer_id": customer_id, "total_amount": total,
            "addr_name": addr["name"], "addr_phone": addr["phone"],
            "addr_street": addr["street"], "addr_city": addr["city"],
            "addr_state": addr["state"], "addr_pin": addr["pin"],
            "notes": notes, "status": "placed"
        })
        return row["id"] if row else None

    @staticmethod
    def add_items(order_id, cart):
        for item in cart.values():
            supa.insert("order_items", {
                "order_id": order_id, "product_id": item["id"],
                "quantity": item["qty"], "unit_price": item["price"],
                "title_snap": item["title"], "image_snap": item.get("image", "")
            })

    @staticmethod
    def get(oid):
        rows = supa.select("orders", filters={"id": f"eq.{oid}"})
        if not rows:
            return None
        o = rows[0]
        user = supa.select_one("users", {"id": f"eq.{o['customer_id']}"})
        if user:
            o["cust_name"]  = user["full_name"]
            o["cust_email"] = user["email"]
            o["cust_phone"] = user.get("phone", "")
        return o

    @staticmethod
    def get_for_customer(oid, cid):
        rows = supa.select("orders", filters={"id": f"eq.{oid}", "customer_id": f"eq.{cid}"})
        if not rows:
            return None
        o = rows[0]
        user = supa.select_one("users", {"id": f"eq.{o['customer_id']}"})
        if user:
            o["cust_name"] = user["full_name"]
            o["cust_email"] = user["email"]
        return o

    @staticmethod
    def for_customer(cid):
        return supa.select("orders", filters={"customer_id": f"eq.{cid}"}, order="created_at.desc") or []

    @staticmethod
    def items(oid):
        return supa.select("order_items", filters={"order_id": f"eq.{oid}"}) or []

    @staticmethod
    def set_status(oid, status, note="", advance=None):
        data = {"status": status}
        if note:
            data["admin_note"] = note
        if advance is not None:
            data["advance_amount"] = advance
        if status == "delivered":
            from datetime import datetime, timezone
            data["delivered_at"] = datetime.now(timezone.utc).isoformat()
        supa.update("orders", {"id": f"eq.{oid}"}, data)

    @staticmethod
    def set_advance_proof(oid, url):
        supa.update("orders", {"id": f"eq.{oid}"},
                    {"advance_proof": url, "status": "advance_paid"})

    @staticmethod
    def admin_list(status="", q="", page=1, per=20):
        filters = {"limit": per, "offset": (page-1)*per}
        if status:
            filters["status"] = f"eq.{status}"
        rows = supa.select("orders", filters=filters, order="created_at.desc") or []
        # attach customer names
        for o in rows:
            user = supa.select_one("users", {"id": f"eq.{o['customer_id']}"})
            if user:
                o["cust_name"]  = user["full_name"]
                o["cust_email"] = user["email"]
        if q:
            rows = [o for o in rows if q.lower() in o.get("cust_name","").lower()
                    or q.lower() in o.get("cust_email","").lower()]
        total = supa.count("orders", {"status": f"eq.{status}"} if status else {})
        return rows, total

    @staticmethod
    def stats():
        all_orders = supa.select("orders") or []
        revenue = sum(float(o["total_amount"]) for o in all_orders if o["status"] == "delivered")
        return {
            "total":           len(all_orders),
            "new_orders":      sum(1 for o in all_orders if o["status"] == "placed"),
            "advance_pending": sum(1 for o in all_orders if o["status"] == "advance_paid"),
            "in_progress":     sum(1 for o in all_orders if o["status"] in ("advance_confirmed","crafting","quality_check")),
            "shipped":         sum(1 for o in all_orders if o["status"] == "shipped"),
            "delivered":       sum(1 for o in all_orders if o["status"] == "delivered"),
            "revenue":         revenue,
        }


# ── Tracking ──────────────────────────────────────────────────
class Tracking:
    @staticmethod
    def add(oid, status, note=""):
        supa.insert("tracking", {"order_id": oid, "status": status, "note": note})

    @staticmethod
    def for_order(oid):
        return supa.select("tracking", filters={"order_id": f"eq.{oid}"}, order="created_at.asc") or []


# ── Notification ──────────────────────────────────────────────
class Notification:
    @staticmethod
    def add(uid, oid, title, msg):
        supa.insert("notifications", {"user_id": uid, "order_id": oid, "title": title, "message": msg})

    @staticmethod
    def for_user(uid, n=10):
        return supa.select("notifications",
                           filters={"user_id": f"eq.{uid}"},
                           order="created_at.desc", limit=n) or []

    @staticmethod
    def unread(uid):
        return supa.count("notifications", {"user_id": f"eq.{uid}", "is_read": "eq.false"})

    @staticmethod
    def mark_read(nid, uid):
        supa.update("notifications", {"id": f"eq.{nid}", "user_id": f"eq.{uid}"}, {"is_read": True})

    @staticmethod
    def mark_all(uid):
        supa.update("notifications", {"user_id": f"eq.{uid}"}, {"is_read": True})
