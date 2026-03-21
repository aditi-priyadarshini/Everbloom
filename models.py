from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from db import run, db as db_ctx

# ── Status config ─────────────────────────────────────────────────────────────
STATUSES = [
    ("placed",            "Order Placed",              "📋"),
    ("advance_requested", "Advance Requested",          "💌"),
    ("advance_paid",      "Advance Paid",               "💳"),
    ("advance_confirmed", "Advance Confirmed",          "✅"),
    ("crafting",          "Being Crafted",              "🎨"),
    ("quality_check",     "Quality Check",              "🔍"),
    ("shipped",           "Shipped",                    "🚚"),
    ("delivered",         "Delivered",                  "🌸"),
    ("cancelled",         "Cancelled",                  "❌"),
]
STATUS_KEYS   = [s[0] for s in STATUSES]
STATUS_LABELS = {s[0]: s[1] for s in STATUSES}
STATUS_ICONS  = {s[0]: s[2] for s in STATUSES}


# ── Helpers ───────────────────────────────────────────────────────────────────
def final_price(p):
    return round(float(p["price"]) * (1 - (p["discount_percent"] or 0) / 100), 2)

def image_list(p):
    raw = p.get("images") or ""
    return [i.strip() for i in raw.split(",") if i.strip()]

def first_image(p):
    imgs = image_list(p)
    return imgs[0] if imgs else ""


# ── User ──────────────────────────────────────────────────────────────────────
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
        row = run("SELECT * FROM users WHERE id=%s", (uid,), one=True)
        return User(row) if row else None

    @staticmethod
    def by_email(email):
        row = run("SELECT * FROM users WHERE email=%s", (email,), one=True)
        return User(row) if row else None

    @staticmethod
    def create(full_name, email, phone, password):
        ph = generate_password_hash(password)
        row = run(
            "INSERT INTO users (full_name,email,phone,password_hash) VALUES (%s,%s,%s,%s) RETURNING id",
            (full_name, email, phone, ph), one=True
        )
        return row["id"] if row else None

    @staticmethod
    def update(uid, full_name, phone, address):
        run("UPDATE users SET full_name=%s, phone=%s, address=%s WHERE id=%s",
            (full_name, phone, address, uid))

    @staticmethod
    def all_customers(search="", page=1, per=20):
        q = f"%{search}%"
        total = run("SELECT COUNT(*) as n FROM users WHERE role='customer' AND (full_name ILIKE %s OR email ILIKE %s)", (q,q), one=True)["n"]
        rows  = run("SELECT * FROM users WHERE role='customer' AND (full_name ILIKE %s OR email ILIKE %s) ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (q, q, per, (page-1)*per), many=True)
        return rows, total


# ── Category ──────────────────────────────────────────────────────────────────
class Category:
    @staticmethod
    def all():
        return run("SELECT * FROM categories ORDER BY name", many=True)

    @staticmethod
    def by_slug(slug):
        return run("SELECT * FROM categories WHERE slug=%s", (slug,), one=True)


# ── Product ───────────────────────────────────────────────────────────────────
class Product:
    @staticmethod
    def get(pid, active_only=True):
        sql = "SELECT p.*, c.name cat_name, c.slug cat_slug, c.icon cat_icon FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=%s"
        if active_only:
            sql += " AND p.is_active=TRUE"
        return run(sql, (pid,), one=True)

    @staticmethod
    def list(cat_id=None, q="", sort="newest", min_p=None, max_p=None,
             in_stock=False, on_sale=False, page=1, per=12):
        where, params = ["p.is_active=TRUE"], []
        if cat_id:
            where.append("p.category_id=%s"); params.append(cat_id)
        if q:
            where.append("(p.title ILIKE %s OR p.description ILIKE %s)"); params += [f"%{q}%", f"%{q}%"]
        if min_p is not None:
            where.append("p.price>=%s"); params.append(min_p)
        if max_p is not None:
            where.append("p.price<=%s"); params.append(max_p)
        if in_stock:
            where.append("p.stock_qty>0")
        if on_sale:
            where.append("p.discount_percent>0")
        w = "WHERE " + " AND ".join(where)
        order = {"price_asc":"p.price ASC","price_desc":"p.price DESC","discount":"p.discount_percent DESC"}.get(sort,"p.created_at DESC")
        total = run(f"SELECT COUNT(*) n FROM products p LEFT JOIN categories c ON c.id=p.category_id {w}", params, one=True)["n"]
        rows  = run(f"SELECT p.*, c.name cat_name, c.slug cat_slug, c.icon cat_icon FROM products p LEFT JOIN categories c ON c.id=p.category_id {w} ORDER BY {order} LIMIT %s OFFSET %s",
                    params+[per,(page-1)*per], many=True)
        return rows, total

    @staticmethod
    def featured(n=4):
        return run("SELECT p.*, c.name cat_name, c.slug cat_slug FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.is_active=TRUE AND p.is_featured=TRUE LIMIT %s", (n,), many=True)

    @staticmethod
    def newest(n=8):
        return run("SELECT p.*, c.name cat_name, c.slug cat_slug FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.is_active=TRUE ORDER BY p.created_at DESC LIMIT %s", (n,), many=True)

    @staticmethod
    def related(cat_id, exclude_id, n=4):
        return run("SELECT p.*, c.name cat_name FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.category_id=%s AND p.id!=%s AND p.is_active=TRUE LIMIT %s",
                   (cat_id, exclude_id, n), many=True)

    @staticmethod
    def create(d):
        row = run("INSERT INTO products (title,description,price,discount_percent,images,category_id,stock_qty,is_featured,is_active,tags) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                  (d["title"],d["description"],d["price"],d["discount_percent"],d["images"],d["category_id"],d["stock_qty"],d["is_featured"],d["is_active"],d["tags"]), one=True)
        return row["id"] if row else None

    @staticmethod
    def update(pid, d):
        run("UPDATE products SET title=%s,description=%s,price=%s,discount_percent=%s,images=%s,category_id=%s,stock_qty=%s,is_featured=%s,is_active=%s,tags=%s WHERE id=%s",
            (d["title"],d["description"],d["price"],d["discount_percent"],d["images"],d["category_id"],d["stock_qty"],d["is_featured"],d["is_active"],d["tags"],pid))

    @staticmethod
    def deduct(pid, qty):
        run("UPDATE products SET stock_qty=GREATEST(0,stock_qty-%s) WHERE id=%s", (qty, pid))

    @staticmethod
    def hide(pid):
        run("UPDATE products SET is_active=FALSE WHERE id=%s", (pid,))

    @staticmethod
    def admin_list(q="", cat_id=None, page=1, per=20):
        where, params = [], []
        if q:
            where.append("p.title ILIKE %s"); params.append(f"%{q}%")
        if cat_id:
            where.append("p.category_id=%s"); params.append(cat_id)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        total = run(f"SELECT COUNT(*) n FROM products p {w}", params, one=True)["n"]
        rows  = run(f"SELECT p.*, c.name cat_name FROM products p LEFT JOIN categories c ON c.id=p.category_id {w} ORDER BY p.created_at DESC LIMIT %s OFFSET %s",
                    params+[per,(page-1)*per], many=True)
        return rows, total


# ── Order ─────────────────────────────────────────────────────────────────────
class Order:
    @staticmethod
    def create(customer_id, total, addr, notes):
        row = run("""INSERT INTO orders (customer_id,total_amount,addr_name,addr_phone,addr_street,addr_city,addr_state,addr_pin,notes,status)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'placed') RETURNING id""",
                  (customer_id,total,addr["name"],addr["phone"],addr["street"],addr["city"],addr["state"],addr["pin"],notes), one=True)
        return row["id"] if row else None

    @staticmethod
    def add_items(order_id, cart):
        with db_ctx() as conn:
            with conn.cursor() as cur:
                for item in cart.values():
                    cur.execute("INSERT INTO order_items (order_id,product_id,quantity,unit_price,title_snap,image_snap) VALUES (%s,%s,%s,%s,%s,%s)",
                                (order_id,item["id"],item["qty"],item["price"],item["title"],item.get("image","")))

    @staticmethod
    def get(oid):
        return run("SELECT o.*, u.full_name cust_name, u.email cust_email, u.phone cust_phone FROM orders o JOIN users u ON u.id=o.customer_id WHERE o.id=%s", (oid,), one=True)

    @staticmethod
    def get_for_customer(oid, cid):
        return run("SELECT o.*, u.full_name cust_name, u.email cust_email FROM orders o JOIN users u ON u.id=o.customer_id WHERE o.id=%s AND o.customer_id=%s", (oid,cid), one=True)

    @staticmethod
    def for_customer(cid):
        return run("SELECT * FROM orders WHERE customer_id=%s ORDER BY created_at DESC", (cid,), many=True)

    @staticmethod
    def items(oid):
        return run("SELECT oi.*, p.title prod_title, p.images prod_images FROM order_items oi LEFT JOIN products p ON p.id=oi.product_id WHERE oi.order_id=%s", (oid,), many=True)

    @staticmethod
    def set_status(oid, status, note="", advance=None):
        if advance is not None:
            run("UPDATE orders SET status=%s, advance_amount=%s WHERE id=%s", (status, advance, oid))
        else:
            run("UPDATE orders SET status=%s WHERE id=%s", (status, oid))
        if note:
            run("UPDATE orders SET admin_note=%s WHERE id=%s", (note, oid))
        if status == "delivered":
            run("UPDATE orders SET delivered_at=NOW() WHERE id=%s", (oid,))

    @staticmethod
    def set_advance_proof(oid, url):
        run("UPDATE orders SET advance_proof=%s, status='advance_paid' WHERE id=%s", (url, oid))

    @staticmethod
    def admin_list(status="", q="", page=1, per=20):
        where, params = [], []
        if status:
            where.append("o.status=%s"); params.append(status)
        if q:
            where.append("(u.full_name ILIKE %s OR u.email ILIKE %s)"); params+=[f"%{q}%",f"%{q}%"]
        w = ("WHERE "+" AND ".join(where)) if where else ""
        total = run(f"SELECT COUNT(*) n FROM orders o JOIN users u ON u.id=o.customer_id {w}", params, one=True)["n"]
        rows  = run(f"SELECT o.*, u.full_name cust_name, u.email cust_email FROM orders o JOIN users u ON u.id=o.customer_id {w} ORDER BY o.created_at DESC LIMIT %s OFFSET %s",
                    params+[per,(page-1)*per], many=True)
        return rows, total

    @staticmethod
    def stats():
        return run("""SELECT
            COUNT(*) total,
            COUNT(*) FILTER (WHERE status='placed') new_orders,
            COUNT(*) FILTER (WHERE status='advance_paid') advance_pending,
            COUNT(*) FILTER (WHERE status IN ('advance_confirmed','crafting','quality_check')) in_progress,
            COUNT(*) FILTER (WHERE status='shipped') shipped,
            COUNT(*) FILTER (WHERE status='delivered') delivered,
            COALESCE(SUM(total_amount) FILTER (WHERE status='delivered'),0) revenue
            FROM orders""", one=True)


# ── Tracking ──────────────────────────────────────────────────────────────────
class Tracking:
    @staticmethod
    def add(oid, status, note=""):
        run("INSERT INTO tracking (order_id,status,note) VALUES (%s,%s,%s)", (oid, status, note))

    @staticmethod
    def for_order(oid):
        return run("SELECT * FROM tracking WHERE order_id=%s ORDER BY created_at ASC", (oid,), many=True)


# ── Notification ──────────────────────────────────────────────────────────────
class Notification:
    @staticmethod
    def add(uid, oid, title, msg):
        run("INSERT INTO notifications (user_id,order_id,title,message) VALUES (%s,%s,%s,%s)", (uid,oid,title,msg))

    @staticmethod
    def for_user(uid, n=10):
        return run("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT %s", (uid,n), many=True)

    @staticmethod
    def unread(uid):
        r = run("SELECT COUNT(*) n FROM notifications WHERE user_id=%s AND is_read=FALSE", (uid,), one=True)
        return r["n"] if r else 0

    @staticmethod
    def mark_read(nid, uid):
        run("UPDATE notifications SET is_read=TRUE WHERE id=%s AND user_id=%s", (nid,uid))

    @staticmethod
    def mark_all(uid):
        run("UPDATE notifications SET is_read=TRUE WHERE user_id=%s", (uid,))
