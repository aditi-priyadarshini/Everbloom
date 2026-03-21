import supa
from datetime import datetime, timezone


# ── Users ─────────────────────────────────────────────────

def get_user_by_email(email):
    rows = supa.select("users", {"email": f"eq.{email}"})
    return rows[0] if rows else None


def get_user_by_id(uid):
    rows = supa.select("users", {"id": f"eq.{uid}"})
    return rows[0] if rows else None


def create_user(email, password_hash, name):
    return supa.insert("users", {"email": email, "password_hash": password_hash, "name": name})


def update_user(uid, data):
    return supa.update("users", {"id": f"eq.{uid}"}, data)


def get_all_users():
    return supa.select("users", order="created_at.desc")


# ── Categories ────────────────────────────────────────────

def get_categories():
    return supa.select("categories", order="name.asc")


def get_category(cid):
    rows = supa.select("categories", {"id": f"eq.{cid}"})
    return rows[0] if rows else None


# ── Products ──────────────────────────────────────────────

def get_products(category_id=None, featured=False, in_stock=False,
                 on_sale=False, flash=False, order="created_at.desc", limit=None, search=None):
    filters = {}
    if category_id:
        filters["category_id"] = f"eq.{category_id}"
    if featured:
        filters["featured"] = "eq.true"
    if in_stock:
        filters["stock"] = "gt.0"
    if on_sale:
        filters["discount_percent"] = "gt.0"
    if flash:
        filters["is_flash_sale"] = "eq.true"
    if search:
        filters["title"] = f"ilike.*{search}*"
    return supa.select("products", filters, order=order, limit=limit)


def get_product(pid):
    rows = supa.select("products", {"id": f"eq.{pid}"})
    return rows[0] if rows else None


def create_product(data):
    return supa.insert("products", data)


def update_product(pid, data):
    return supa.update("products", {"id": f"eq.{pid}"}, data)


def delete_product(pid):
    return supa.delete("products", {"id": f"eq.{pid}"})


def discounted_price(product):
    price = float(product["price"])
    disc = int(product.get("discount_percent") or 0)
    if disc > 0:
        return round(price * (1 - disc / 100), 2)
    return price


def is_flash_active(product):
    ends = product.get("flash_sale_ends_at")
    if not ends:
        return False
    try:
        dt = datetime.fromisoformat(ends.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False


# ── Coupons ───────────────────────────────────────────────

def get_coupon(code):
    rows = supa.select("coupons", {"code": f"eq.{code.upper()}", "active": "eq.true"})
    return rows[0] if rows else None


def use_coupon(code):
    c = get_coupon(code)
    if c:
        supa.update("coupons", {"code": f"eq.{code.upper()}"}, {"used_count": c["used_count"] + 1})


def get_all_coupons():
    return supa.select("coupons", order="created_at.desc")


def create_coupon(data):
    data["code"] = data["code"].upper()
    return supa.insert("coupons", data)


def update_coupon(cid, data):
    return supa.update("coupons", {"id": f"eq.{cid}"}, data)


def delete_coupon(cid):
    return supa.delete("coupons", {"id": f"eq.{cid}"})


# ── Orders ────────────────────────────────────────────────

ORDER_STATUSES = [
    "placed", "advance_requested", "advance_paid",
    "advance_confirmed", "crafting", "quality_check",
    "shipped", "delivered", "cancelled"
]

STATUS_LABELS = {
    "placed": "Order Placed",
    "advance_requested": "Advance Requested",
    "advance_paid": "Advance Paid",
    "advance_confirmed": "Advance Confirmed",
    "crafting": "Crafting",
    "quality_check": "Quality Check",
    "shipped": "Shipped",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}

NEXT_STATUS = {
    "placed": "advance_requested",
    "advance_requested": "advance_paid",
    "advance_paid": "advance_confirmed",
    "advance_confirmed": "crafting",
    "crafting": "quality_check",
    "quality_check": "shipped",
    "shipped": "delivered",
}


def get_orders(user_id=None, status=None, order="created_at.desc", limit=None):
    filters = {}
    if user_id:
        filters["user_id"] = f"eq.{user_id}"
    if status:
        filters["status"] = f"eq.{status}"
    return supa.select("orders", filters, order=order, limit=limit)


def get_order(oid):
    rows = supa.select("orders", {"id": f"eq.{oid}"})
    return rows[0] if rows else None


def create_order(data):
    return supa.insert("orders", data)


def update_order(oid, data):
    return supa.update("orders", {"id": f"eq.{oid}"}, data)


def get_order_items(oid):
    return supa.select("order_items", {"order_id": f"eq.{oid}"})


def create_order_item(data):
    return supa.insert("order_items", data)


def get_tracking(oid):
    return supa.select("tracking", {"order_id": f"eq.{oid}"}, order="created_at.asc")


def add_tracking(oid, status, note=None):
    return supa.insert("tracking", {"order_id": oid, "status": status, "note": note})


def status_index(status):
    try:
        return ORDER_STATUSES.index(status)
    except ValueError:
        return 0


# ── Notifications ─────────────────────────────────────────

def get_notifications(user_id, unread_only=False):
    filters = {"user_id": f"eq.{user_id}"}
    if unread_only:
        filters["read"] = "eq.false"
    return supa.select("notifications", filters, order="created_at.desc", limit=20)


def create_notification(user_id, message, link=None):
    return supa.insert("notifications", {"user_id": user_id, "message": message, "link": link})


def mark_notifications_read(user_id):
    return supa.update("notifications", {"user_id": f"eq.{user_id}", "read": "eq.false"}, {"read": True})


# ── Reviews ───────────────────────────────────────────────

def get_reviews(product_id):
    return supa.select("reviews", {"product_id": f"eq.{product_id}"}, order="created_at.desc")


def get_review_by_user(product_id, user_id):
    rows = supa.select("reviews", {"product_id": f"eq.{product_id}", "user_id": f"eq.{user_id}"})
    return rows[0] if rows else None


def create_review(data):
    return supa.insert("reviews", data)


def update_review(rid, data):
    return supa.update("reviews", {"id": f"eq.{rid}"}, data)


def avg_rating(reviews):
    if not reviews:
        return 0
    return round(sum(r["rating"] for r in reviews) / len(reviews), 1)


# ── Custom Requests ───────────────────────────────────────

def get_custom_requests(status=None):
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    return supa.select("custom_requests", filters, order="created_at.desc")


def get_custom_request(rid):
    rows = supa.select("custom_requests", {"id": f"eq.{rid}"})
    return rows[0] if rows else None


def create_custom_request(data):
    return supa.insert("custom_requests", data)


def update_custom_request(rid, data):
    return supa.update("custom_requests", {"id": f"eq.{rid}"}, data)


# ── Settings ─────────────────────────────────────────────

def get_setting(key):
    rows = supa.select("settings", {"key": f"eq.{key}"})
    return rows[0]["value"] if rows else None


def set_setting(key, value):
    return supa.update("settings", {"key": f"eq.{key}"}, {"value": value})


def get_all_settings():
    rows = supa.select("settings") or []
    return {r["key"]: r["value"] for r in rows}


# ── Variants ──────────────────────────────────────────────

def get_variants(product_id):
    return supa.select("variants", {"product_id": f"eq.{product_id}"}, order="name.asc")


def create_variant(data):
    return supa.insert("variants", data)


def update_variant(vid, data):
    return supa.update("variants", {"id": f"eq.{vid}"}, data)


def delete_variant(vid):
    return supa.delete("variants", {"id": f"eq.{vid}"})


def delete_variants_for_product(product_id):
    return supa.delete("variants", {"product_id": f"eq.{product_id}"})


# ── Wishlist ──────────────────────────────────────────────

def get_wishlist(user_id):
    rows = supa.select("wishlists", {"user_id": f"eq.{user_id}"}, order="created_at.desc")
    pids = [r["product_id"] for r in rows]
    products = []
    for pid in pids:
        p = get_product(pid)
        if p:
            products.append(p)
    return products


def is_wishlisted(user_id, product_id):
    rows = supa.select("wishlists", {"user_id": f"eq.{user_id}", "product_id": f"eq.{product_id}"})
    return bool(rows)


def toggle_wishlist(user_id, product_id):
    if is_wishlisted(user_id, product_id):
        supa.delete("wishlists", {"user_id": f"eq.{user_id}", "product_id": f"eq.{product_id}"})
        return False
    else:
        supa.insert("wishlists", {"user_id": user_id, "product_id": product_id})
        return True


# ── Back in Stock Alerts ──────────────────────────────────

def add_back_in_stock_alert(product_id, email, user_id=None):
    try:
        return supa.insert("back_in_stock_alerts", {
            "product_id": product_id, "email": email, "user_id": user_id
        })
    except Exception:
        return None


def get_alerts_for_product(product_id):
    return supa.select("back_in_stock_alerts", {
        "product_id": f"eq.{product_id}", "notified": "eq.false"
    })


def mark_alerts_notified(product_id):
    return supa.update("back_in_stock_alerts",
                       {"product_id": f"eq.{product_id}", "notified": "eq.false"},
                       {"notified": True})


def get_low_stock_products(threshold=5):
    all_products = supa.select("products", {"stock": f"lte.{threshold}"}, order="stock.asc") or []
    return [p for p in all_products if p.get("stock", 0) >= 0]


# ── Gift Cards ────────────────────────────────────────────

def get_gift_card(code):
    rows = supa.select("gift_cards", {"code": f"eq.{code.upper()}", "active": "eq.true"})
    return rows[0] if rows else None


def get_all_gift_cards():
    return supa.select("gift_cards", order="created_at.desc")


def create_gift_card(data):
    data["code"] = data["code"].upper()
    data["balance"] = data["amount"]
    return supa.insert("gift_cards", data)


def use_gift_card(code, amount):
    gc = get_gift_card(code)
    if not gc:
        return False
    new_bal = float(gc["balance"]) - float(amount)
    if new_bal < 0:
        return False
    supa.update("gift_cards", {"code": f"eq.{code.upper()}"},
                {"balance": new_bal, "active": new_bal > 0})
    return True


def delete_gift_card(gid):
    return supa.delete("gift_cards", {"id": f"eq.{gid}"})


# ── Returns ───────────────────────────────────────────────

def get_returns(status=None):
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    return supa.select("returns", filters, order="created_at.desc")


def get_return(rid):
    rows = supa.select("returns", {"id": f"eq.{rid}"})
    return rows[0] if rows else None


def get_returns_for_user(user_id):
    return supa.select("returns", {"user_id": f"eq.{user_id}"}, order="created_at.desc")


def create_return(data):
    return supa.insert("returns", data)


def update_return(rid, data):
    return supa.update("returns", {"id": f"eq.{rid}"}, data)


# ── Artisans ──────────────────────────────────────────────

def get_artisans(active_only=True):
    filters = {"active": "eq.true"} if active_only else {}
    return supa.select("artisans", filters, order="name.asc")


def get_artisan(aid):
    rows = supa.select("artisans", {"id": f"eq.{aid}"})
    return rows[0] if rows else None


def create_artisan(data):
    return supa.insert("artisans", data)


def update_artisan(aid, data):
    return supa.update("artisans", {"id": f"eq.{aid}"}, data)


def delete_artisan(aid):
    return supa.delete("artisans", {"id": f"eq.{aid}"})


# ── FAQs ──────────────────────────────────────────────────

def get_faqs(active_only=True):
    filters = {"active": "eq.true"} if active_only else {}
    return supa.select("faqs", filters, order="sort_order.asc")


def get_all_faqs():
    return supa.select("faqs", order="sort_order.asc")


def create_faq(data):
    return supa.insert("faqs", data)


def update_faq(fid, data):
    return supa.update("faqs", {"id": f"eq.{fid}"}, data)


def delete_faq(fid):
    return supa.delete("faqs", {"id": f"eq.{fid}"})


# ── Broadcasts ────────────────────────────────────────────

def log_broadcast(subject, body, sent_to):
    return supa.insert("broadcasts", {"subject": subject, "body": body, "sent_to": sent_to})


def get_broadcasts():
    return supa.select("broadcasts", order="created_at.desc")


# ── Dashboard Stats ───────────────────────────────────────

def get_stats():
    all_orders = supa.select("orders") or []
    all_users = supa.select("users", {"is_admin": "eq.false"}) or []
    all_products = supa.select("products") or []
    pending = [o for o in all_orders if o["status"] not in ("delivered", "cancelled")]
    revenue = sum(float(o.get("total", 0)) for o in all_orders if o["status"] == "delivered")
    # Monthly revenue (last 6 months)
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    monthly = {}
    for i in range(5, -1, -1):
        d = now - timedelta(days=30 * i)
        key = d.strftime("%b")
        monthly[key] = 0
    for o in all_orders:
        if o["status"] == "delivered" and o.get("created_at"):
            try:
                dt = datetime.fromisoformat(o["created_at"].replace("Z", "+00:00"))
                key = dt.strftime("%b")
                if key in monthly:
                    monthly[key] += float(o.get("total", 0))
            except Exception:
                pass
    return {
        "total_orders": len(all_orders),
        "pending_orders": len(pending),
        "total_customers": len(all_users),
        "total_products": len(all_products),
        "total_revenue": revenue,
        "placed": len([o for o in all_orders if o["status"] == "placed"]),
        "advance_paid": len([o for o in all_orders if o["status"] == "advance_paid"]),
        "shipped": len([o for o in all_orders if o["status"] == "shipped"]),
        "monthly_revenue": monthly,
    }
