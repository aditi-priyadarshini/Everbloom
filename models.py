"""
models.py — Simple Python classes that wrap SQL queries.
No ORM — just psycopg2 + RealDictCursor (returns dicts).
"""
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from db import query, get_db

# ── Order status config ───────────────────────────────────────────────────────
ORDER_STATUSES = [
    ("draft",             "Order Received",           "📋"),
    ("advance_requested", "Advance Payment Requested", "💌"),
    ("advance_paid",      "Advance Paid",              "💳"),
    ("advance_confirmed", "Advance Confirmed",         "✅"),
    ("accepted",          "Accepted by Artist",        "🎨"),
    ("material_sourced",  "Raw Material Sourced",      "🪵"),
    ("crafting",          "Crafting in Progress",      "✂️"),
    ("quality_check",     "Quality Check",             "🔍"),
    ("packed",            "Packed & Ready",            "📦"),
    ("shipped",           "Shipped",                   "🚚"),
    ("delivered",         "Delivered",                 "🌸"),
    ("cancelled",         "Cancelled",                 "❌"),
]
STATUS_KEYS   = [s[0] for s in ORDER_STATUSES]
STATUS_LABELS = {s[0]: s[1] for s in ORDER_STATUSES}
STATUS_ICONS  = {s[0]: s[2] for s in ORDER_STATUSES}


# ── User ──────────────────────────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, row):
        self.id            = row["id"]
        self.full_name     = row["full_name"]
        self.email         = row["email"]
        self.phone         = row.get("phone") or ""
        self.address       = row.get("address") or ""
        self.password_hash = row["password_hash"]
        self.role          = row.get("role", "customer")
        self.created_at    = row.get("created_at")

    @property
    def is_admin(self):
        return self.role == "admin"

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get(user_id):
        row = query("SELECT * FROM users WHERE id=%s", (user_id,), fetchone=True)
        return User(row) if row else None

    @staticmethod
    def get_by_email(email):
        row = query("SELECT * FROM users WHERE email=%s", (email,), fetchone=True)
        return User(row) if row else None

    @staticmethod
    def create(full_name, email, phone, password):
        ph = generate_password_hash(password)
        row = query(
            "INSERT INTO users (full_name,email,phone,password_hash) VALUES (%s,%s,%s,%s) RETURNING id",
            (full_name, email, phone, ph), fetchone=True
        )
        return row["id"] if row else None

    @staticmethod
    def update_profile(user_id, full_name, phone, address):
        query("UPDATE users SET full_name=%s, phone=%s, address=%s WHERE id=%s",
              (full_name, phone, address, user_id))

    @staticmethod
    def set_admin(email):
        query("UPDATE users SET role='admin' WHERE email=%s", (email,))


# ── Category ──────────────────────────────────────────────────────────────────
class Category:
    @staticmethod
    def all():
        return query("SELECT * FROM categories ORDER BY name", fetchall=True) or []

    @staticmethod
    def get_by_slug(slug):
        return query("SELECT * FROM categories WHERE slug=%s", (slug,), fetchone=True)

    @staticmethod
    def get(cat_id):
        return query("SELECT * FROM categories WHERE id=%s", (cat_id,), fetchone=True)


# ── Product ───────────────────────────────────────────────────────────────────
class Product:
    @staticmethod
    def final_price(row):
        return float(row["price"]) * (1 - (row["discount_percent"] or 0) / 100)

    @staticmethod
    def image_list(row):
        imgs = row.get("images") or ""
        return [i.strip() for i in imgs.split(",") if i.strip()]

    @staticmethod
    def first_image(row):
        imgs = Product.image_list(row)
        return imgs[0] if imgs else None

    @staticmethod
    def tag_list(row):
        tags = row.get("tags") or ""
        return [t.strip() for t in tags.split(",") if t.strip()]

    @staticmethod
    def get(product_id, active_only=True):
        sql = "SELECT p.*, c.name as cat_name, c.slug as cat_slug, c.icon as cat_icon FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=%s"
        if active_only:
            sql += " AND p.is_active=TRUE"
        return query(sql, (product_id,), fetchone=True)

    @staticmethod
    def list(category_id=None, search=None, sort="newest", min_price=None,
             max_price=None, in_stock=False, on_sale=False,
             active_only=True, page=1, per_page=12):
        conditions = []
        params = []
        if active_only:
            conditions.append("p.is_active=TRUE")
        if category_id:
            conditions.append("p.category_id=%s")
            params.append(category_id)
        if search:
            conditions.append("(p.title ILIKE %s OR p.description ILIKE %s)")
            params += [f"%{search}%", f"%{search}%"]
        if min_price is not None:
            conditions.append("p.price>=%s")
            params.append(min_price)
        if max_price is not None:
            conditions.append("p.price<=%s")
            params.append(max_price)
        if in_stock:
            conditions.append("p.stock_qty>0")
        if on_sale:
            conditions.append("p.discount_percent>0")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        order = {"price_asc": "p.price ASC", "price_desc": "p.price DESC",
                 "discount": "p.discount_percent DESC"}.get(sort, "p.created_at DESC")

        count_sql = f"SELECT COUNT(*) as cnt FROM products p LEFT JOIN categories c ON c.id=p.category_id {where}"
        total = query(count_sql, params, fetchone=True)["cnt"]

        offset = (page - 1) * per_page
        sql = f"""SELECT p.*, c.name as cat_name, c.slug as cat_slug, c.icon as cat_icon
                  FROM products p LEFT JOIN categories c ON c.id=p.category_id
                  {where} ORDER BY {order} LIMIT %s OFFSET %s"""
        rows = query(sql, params + [per_page, offset], fetchall=True) or []
        return rows, total

    @staticmethod
    def featured(limit=4):
        return query(
            "SELECT p.*, c.name as cat_name, c.slug as cat_slug, c.icon as cat_icon FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.is_active=TRUE AND p.is_featured=TRUE LIMIT %s",
            (limit,), fetchall=True) or []

    @staticmethod
    def newest(limit=4):
        return query(
            "SELECT p.*, c.name as cat_name, c.slug as cat_slug, c.icon as cat_icon FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.is_active=TRUE ORDER BY p.created_at DESC LIMIT %s",
            (limit,), fetchall=True) or []

    @staticmethod
    def related(category_id, exclude_id, limit=4):
        return query(
            "SELECT p.*, c.name as cat_name, c.slug as cat_slug, c.icon as cat_icon FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.category_id=%s AND p.id!=%s AND p.is_active=TRUE LIMIT %s",
            (category_id, exclude_id, limit), fetchall=True) or []

    @staticmethod
    def create(data):
        row = query("""
            INSERT INTO products (title,slug,description,category_id,price,discount_percent,
                                  stock_qty,tags,is_featured,is_active,images)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (data["title"], data["slug"], data["description"], data["category_id"],
             data["price"], data["discount_percent"], data["stock_qty"], data["tags"],
             data["is_featured"], data["is_active"], data.get("images", "")),
            fetchone=True)
        return row["id"] if row else None

    @staticmethod
    def update(product_id, data):
        query("""UPDATE products SET title=%s,slug=%s,description=%s,category_id=%s,
                 price=%s,discount_percent=%s,stock_qty=%s,tags=%s,
                 is_featured=%s,is_active=%s,images=%s WHERE id=%s""",
              (data["title"], data["slug"], data["description"], data["category_id"],
               data["price"], data["discount_percent"], data["stock_qty"], data["tags"],
               data["is_featured"], data["is_active"], data.get("images", ""), product_id))

    @staticmethod
    def deduct_stock(product_id, qty):
        query("UPDATE products SET stock_qty=GREATEST(0,stock_qty-%s) WHERE id=%s", (qty, product_id))

    @staticmethod
    def hide(product_id):
        query("UPDATE products SET is_active=FALSE WHERE id=%s", (product_id,))

    @staticmethod
    def admin_list(search=None, category_id=None, page=1, per_page=20):
        conditions, params = [], []
        if search:
            conditions.append("p.title ILIKE %s")
            params.append(f"%{search}%")
        if category_id:
            conditions.append("p.category_id=%s")
            params.append(category_id)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        total = query(f"SELECT COUNT(*) as cnt FROM products p {where}", params, fetchone=True)["cnt"]
        offset = (page - 1) * per_page
        rows = query(
            f"SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON c.id=p.category_id {where} ORDER BY p.created_at DESC LIMIT %s OFFSET %s",
            params + [per_page, offset], fetchall=True) or []
        return rows, total


# ── Order ─────────────────────────────────────────────────────────────────────
class Order:
    @staticmethod
    def create(customer_id, total, addr, notes=""):
        row = query("""
            INSERT INTO orders (customer_id,total_amount,addr_name,addr_phone,
                addr_street,addr_city,addr_state,addr_pin,notes,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft') RETURNING id""",
            (customer_id, total, addr["name"], addr["phone"],
             addr["street"], addr["city"], addr["state"], addr["pin"], notes),
            fetchone=True)
        return row["id"] if row else None

    @staticmethod
    def get(order_id):
        return query("""
            SELECT o.*, u.full_name as cust_name, u.email as cust_email, u.phone as cust_phone
            FROM orders o JOIN users u ON u.id=o.customer_id
            WHERE o.id=%s""", (order_id,), fetchone=True)

    @staticmethod
    def get_for_customer(order_id, customer_id):
        return query("""
            SELECT o.*, u.full_name as cust_name, u.email as cust_email
            FROM orders o JOIN users u ON u.id=o.customer_id
            WHERE o.id=%s AND o.customer_id=%s""", (order_id, customer_id), fetchone=True)

    @staticmethod
    def list_for_customer(customer_id):
        return query("""
            SELECT o.* FROM orders o
            WHERE o.customer_id=%s ORDER BY o.created_at DESC""",
            (customer_id,), fetchall=True) or []

    @staticmethod
    def admin_list(status=None, search=None, page=1, per_page=20):
        conditions, params = [], []
        if status:
            conditions.append("o.status=%s")
            params.append(status)
        if search:
            conditions.append("(u.full_name ILIKE %s OR u.email ILIKE %s)")
            params += [f"%{search}%", f"%{search}%"]
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        total = query(f"SELECT COUNT(*) as cnt FROM orders o JOIN users u ON u.id=o.customer_id {where}", params, fetchone=True)["cnt"]
        offset = (page - 1) * per_page
        rows = query(
            f"SELECT o.*, u.full_name as cust_name, u.email as cust_email FROM orders o JOIN users u ON u.id=o.customer_id {where} ORDER BY o.created_at DESC LIMIT %s OFFSET %s",
            params + [per_page, offset], fetchall=True) or []
        return rows, total

    @staticmethod
    def update_status(order_id, status, admin_note=None, advance_amount=None):
        if advance_amount is not None:
            query("UPDATE orders SET status=%s, advance_amount=%s WHERE id=%s",
                  (status, advance_amount, order_id))
        elif admin_note:
            query("UPDATE orders SET status=%s, admin_note=%s WHERE id=%s",
                  (status, admin_note, order_id))
        else:
            query("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))
        if status == "delivered":
            query("UPDATE orders SET delivered_at=NOW() WHERE id=%s", (order_id,))

    @staticmethod
    def set_advance_proof(order_id, url):
        query("UPDATE orders SET advance_proof=%s, status='advance_paid' WHERE id=%s", (url, order_id))

    @staticmethod
    def dashboard_stats():
        return query("""
            SELECT
              COUNT(*) as total,
              COUNT(*) FILTER (WHERE status='draft') as pending_review,
              COUNT(*) FILTER (WHERE status='advance_paid') as advance_pending,
              COUNT(*) FILTER (WHERE status IN ('advance_confirmed','accepted','material_sourced','crafting','quality_check')) as in_progress,
              COUNT(*) FILTER (WHERE status='shipped') as shipped,
              COUNT(*) FILTER (WHERE status='delivered') as delivered,
              COALESCE(SUM(total_amount) FILTER (WHERE status IN ('delivered','shipped','packed')), 0) as revenue
            FROM orders""", fetchone=True)

    @staticmethod
    def items(order_id):
        return query("""
            SELECT oi.*, p.title as prod_title, p.images as prod_images
            FROM order_items oi LEFT JOIN products p ON p.id=oi.product_id
            WHERE oi.order_id=%s""", (order_id,), fetchall=True) or []

    @staticmethod
    def add_items(order_id, cart):
        with get_db() as conn:
            with conn.cursor() as cur:
                for key, item in cart.items():
                    cur.execute("""
                        INSERT INTO order_items (order_id,product_id,quantity,unit_price,title_snap,image_snap)
                        VALUES (%s,%s,%s,%s,%s,%s)""",
                        (order_id, item["id"], item["qty"], item["price"],
                         item["title"], item.get("image", "")))


# ── Tracking ──────────────────────────────────────────────────────────────────
class Tracking:
    @staticmethod
    def add(order_id, status, note=None, created_by=None):
        query("INSERT INTO tracking_events (order_id,status,note,created_by) VALUES (%s,%s,%s,%s)",
              (order_id, status, note, created_by))

    @staticmethod
    def list(order_id):
        return query("SELECT * FROM tracking_events WHERE order_id=%s ORDER BY created_at ASC",
                     (order_id,), fetchall=True) or []


# ── Notification ──────────────────────────────────────────────────────────────
class Notification:
    @staticmethod
    def add(user_id, order_id, title, message):
        query("INSERT INTO notifications (user_id,order_id,title,message) VALUES (%s,%s,%s,%s)",
              (user_id, order_id, title, message))

    @staticmethod
    def list(user_id, limit=10):
        return query("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
                     (user_id, limit), fetchall=True) or []

    @staticmethod
    def unread_count(user_id):
        row = query("SELECT COUNT(*) as cnt FROM notifications WHERE user_id=%s AND is_read=FALSE",
                    (user_id,), fetchone=True)
        return row["cnt"] if row else 0

    @staticmethod
    def mark_read(notif_id, user_id):
        query("UPDATE notifications SET is_read=TRUE WHERE id=%s AND user_id=%s", (notif_id, user_id))

    @staticmethod
    def mark_all_read(user_id):
        query("UPDATE notifications SET is_read=TRUE WHERE user_id=%s", (user_id,))

    @staticmethod
    def count_customers():
        row = query("SELECT COUNT(*) as cnt FROM users WHERE role='customer'", fetchone=True)
        return row["cnt"] if row else 0

    @staticmethod
    def list_customers(search=None, page=1, per_page=20):
        conditions, params = [], []
        if search:
            conditions.append("(full_name ILIKE %s OR email ILIKE %s)")
            params += [f"%{search}%", f"%{search}%"]
        where = ("WHERE role='customer' AND " + " AND ".join(conditions)) if conditions else "WHERE role='customer'"
        total = query(f"SELECT COUNT(*) as cnt FROM users {where}", params, fetchone=True)["cnt"]
        offset = (page - 1) * per_page
        rows = query(f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                     params + [per_page, offset], fetchall=True) or []
        return rows, total
