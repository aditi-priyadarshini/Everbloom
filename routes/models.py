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
                 on_sale=False, flash=False, order="created_at.desc", limit=None, search=None, listed_only=True):
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
    if listed_only:
        filters["is_listed"] = "eq.true"
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

def get_custom_requests(status=None, user_id=None):
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    if user_id:
        filters["user_id"] = f"eq.{user_id}"
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
    from datetime import datetime, timezone, timedelta
    all_orders = supa.select("orders") or []
    all_users = supa.select("users", {"is_admin": "eq.false"}) or []
    all_products = supa.select("products") or []
    pending = [o for o in all_orders if o["status"] not in ("delivered", "cancelled")]
    delivered = [o for o in all_orders if o["status"] == "delivered"]
    revenue = sum(float(o.get("total", 0)) for o in delivered)
    cancelled = [o for o in all_orders if o["status"] == "cancelled"]

    # Monthly revenue & order count (last 6 months)
    now = datetime.now(timezone.utc)
    monthly = {}
    monthly_orders = {}
    for i in range(5, -1, -1):
        d = now - timedelta(days=30 * i)
        key = d.strftime("%b")
        monthly[key] = 0
        monthly_orders[key] = 0
    for o in all_orders:
        if o.get("created_at"):
            try:
                dt = datetime.fromisoformat(o["created_at"].replace("Z", "+00:00"))
                key = dt.strftime("%b")
                if key in monthly_orders:
                    monthly_orders[key] += 1
                if o["status"] == "delivered" and key in monthly:
                    monthly[key] += float(o.get("total", 0))
            except Exception:
                pass

    avg_order_value = revenue / len(delivered) if delivered else 0
    cancel_rate = round(len(cancelled) / len(all_orders) * 100, 1) if all_orders else 0

    # Status breakdown for funnel
    status_counts = {}
    for o in all_orders:
        s = o.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    # New customers this month
    new_customers_month = 0
    cutoff = now - timedelta(days=30)
    for u in all_users:
        try:
            dt = datetime.fromisoformat((u.get("created_at") or "").replace("Z", "+00:00"))
            if dt > cutoff:
                new_customers_month += 1
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
        "delivered": len(delivered),
        "cancelled": len(cancelled),
        "monthly_revenue": monthly,
        "monthly_orders": monthly_orders,
        "avg_order_value": round(avg_order_value, 2),
        "cancel_rate": cancel_rate,
        "status_counts": status_counts,
        "new_customers_month": new_customers_month,
    }


# ── Email Templates ───────────────────────────────────────

def get_email_templates():
    return supa.select("email_templates", order="id.asc")


def get_email_template(tid):
    rows = supa.select("email_templates", {"id": f"eq.{tid}"})
    return rows[0] if rows else None


def update_email_template(tid, subject, body):
    return supa.update("email_templates",
                       {"id": f"eq.{tid}"},
                       {"subject": subject, "body": body,
                        "updated_at": "now()"})


def render_template_vars(text, order=None, user=None, extra=None):
    """Replace {{var}} placeholders with real values."""
    import re
    vals = {
        "name": (user or {}).get("name", "there") if user else (order or {}).get("name", "there"),
        "order_id": str((order or {}).get("id", ""))[:8].upper() if order else "",
        "total": f"{float((order or {}).get('total', 0)):.0f}" if order else "",
        "advance_amount": f"{float((order or {}).get('advance_amount', 0)):.0f}" if order else "",
        "balance": f"{float((order or {}).get('total', 0)) - float((order or {}).get('advance_amount', 0)):.0f}" if order else "",
        "upi_id": get_setting("upi_id") or "",
        "pay_link": "",
    }
    if extra:
        vals.update(extra)
    for k, v in vals.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text


# ── Email Templates ───────────────────────────────────────

def get_email_templates():
    return supa.select("email_templates", order="key.asc")


def get_email_template(key):
    rows = supa.select("email_templates", {"key": f"eq.{key}"})
    return rows[0] if rows else None


def save_email_template(key, subject, body_html):
    existing = get_email_template(key)
    if existing:
        return supa.update("email_templates",
                           {"key": f"eq.{key}"},
                           {"subject": subject, "body_html": body_html,
                            "updated_at": "now()"})
    return supa.insert("email_templates",
                       {"key": key, "subject": subject, "body_html": body_html})


# ── Auth Tokens (email verify + password reset) ───────────

import secrets
from datetime import datetime, timezone, timedelta


def create_auth_token(user_id, token_type, hours=24):
    token = secrets.token_hex(32)  # hex only - no special chars, fully URL safe
    expires = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    # Invalidate old tokens of same type for this user
    supa.update("auth_tokens",
                {"user_id": f"eq.{user_id}", "type": f"eq.{token_type}", "used": "eq.false"},
                {"used": True})
    supa.insert("auth_tokens", {
        "user_id": str(user_id),
        "token": token,
        "type": token_type,
        "expires_at": expires,
        "used": False,
    })
    return token


def get_auth_token(token, token_type):
    rows = supa.select("auth_tokens", {
        "token": f"eq.{token}",
        "type": f"eq.{token_type}",
        "used": "eq.false",
    })
    if not rows:
        return None
    t = rows[0]
    # Check expiry
    try:
        exp = datetime.fromisoformat(t["expires_at"].replace("Z", "+00:00"))
        if exp < datetime.now(timezone.utc):
            return None
    except Exception:
        return None
    return t


def use_auth_token(token_id):
    supa.update("auth_tokens", {"id": f"eq.{token_id}"}, {"used": True})


def verify_user_email(user_id):
    supa.update("users", {"id": f"eq.{user_id}"}, {"email_verified": True})


# ── Enhanced Custom Requests ──────────────────────────────

def get_custom_request_by_token(token):
    rows = supa.select("custom_requests", {"tracking_token": f"eq.{token}"})
    return rows[0] if rows else None


def get_custom_requests_all(status=None):
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    return supa.select("custom_requests", filters, order="created_at.desc")


# ── Email Log ─────────────────────────────────────────────

def log_email(to_email, subject, body, sent_by, related_type=None, related_id=None):
    return supa.insert("email_log", {
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "sent_by": str(sent_by) if sent_by else None,
        "related_type": related_type,
        "related_id": str(related_id) if related_id else None,
    })


def get_email_log(related_type, related_id):
    return supa.select("email_log", {
        "related_type": f"eq.{related_type}",
        "related_id": f"eq.{related_id}",
    }, order="sent_at.desc")


# ── Raw Materials ─────────────────────────────────────────

def get_raw_materials():
    return supa.select("raw_materials", order="name.asc")

def get_raw_material(mid):
    rows = supa.select("raw_materials", {"id": f"eq.{mid}"})
    return rows[0] if rows else None

def create_raw_material(data):
    return supa.insert("raw_materials", data)

def update_raw_material(mid, data):
    return supa.update("raw_materials", {"id": f"eq.{mid}"}, data)

def delete_raw_material(mid):
    return supa.delete("raw_materials", {"id": f"eq.{mid}"})

def get_low_stock_materials():
    """Materials where current_stock <= reorder_level."""
    materials = get_raw_materials()
    return [m for m in materials
            if float(m.get("current_stock", 0)) <= float(m.get("reorder_level", 0))
            and float(m.get("reorder_level", 0)) > 0]

# ── Expenditures ──────────────────────────────────────────

def get_expenditures(material_id=None):
    filters = {}
    if material_id:
        filters["material_id"] = f"eq.{material_id}"
    return supa.select("expenditures", filters, order="purchased_at.desc")

def add_expenditure(data):
    exp = supa.insert("expenditures", data)
    if exp:
        # Update material stock and cost_per_unit
        mat = get_raw_material(data["material_id"])
        if mat:
            new_stock = float(mat.get("current_stock", 0)) + float(data["quantity"])
            supa.update("raw_materials", {"id": f"eq.{data['material_id']}"}, {
                "current_stock": new_stock,
                "cost_per_unit": float(data["cost_per_unit"]),
            })
    return exp

def deduct_material_stock(material_id, quantity):
    mat = get_raw_material(material_id)
    if mat:
        new_stock = max(0, float(mat.get("current_stock", 0)) - float(quantity))
        supa.update("raw_materials", {"id": f"eq.{material_id}"}, {"current_stock": new_stock})

# ── Product Costs ─────────────────────────────────────────

def get_product_cost(product_id):
    rows = supa.select("product_costs", {"product_id": f"eq.{product_id}"})
    return rows[0] if rows else None

def save_product_cost(product_id, data):
    existing = get_product_cost(product_id)
    data["product_id"] = str(product_id)
    data["updated_at"] = "now()"
    if existing:
        return supa.update("product_costs", {"product_id": f"eq.{product_id}"}, data)
    return supa.insert("product_costs", data)

def get_product_materials(product_id):
    return supa.select("product_materials", {"product_id": f"eq.{product_id}"})

def save_product_materials(product_id, materials_data):
    # Delete existing and re-insert
    supa.delete("product_materials", {"product_id": f"eq.{product_id}"})
    for m in materials_data:
        if m.get("material_id") and float(m.get("quantity_used", 0)) > 0:
            supa.insert("product_materials", {
                "product_id": str(product_id),
                "material_id": int(m["material_id"]),
                "quantity_used": float(m["quantity_used"]),
            })

def calculate_product_cost(product_id):
    """Calculate total material cost + labour + overhead, return suggested price."""
    pm = get_product_materials(product_id)
    pc = get_product_cost(product_id) or {}
    material_cost = 0
    for item in pm:
        mat = get_raw_material(item["material_id"])
        if mat:
            material_cost += float(mat.get("cost_per_unit", 0)) * float(item.get("quantity_used", 0))
    labour    = float(pc.get("labour_cost", 0))
    overhead  = float(pc.get("overhead_cost", 0))
    total_cost = material_cost + labour + overhead
    margin    = float(pc.get("margin_percent", 30))
    suggested = round(total_cost * (1 + margin / 100), 2) if total_cost > 0 else 0
    return {
        "material_cost": round(material_cost, 2),
        "labour_cost":   round(labour, 2),
        "overhead_cost": round(overhead, 2),
        "total_cost":    round(total_cost, 2),
        "margin_percent": margin,
        "suggested_price": suggested,
    }


# ── Components ────────────────────────────────────────────

def get_components():
    return supa.select("components", order="name.asc")

def get_component(cid):
    rows = supa.select("components", {"id": f"eq.{cid}"})
    return rows[0] if rows else None

def create_component(data):
    return supa.insert("components", data)

def update_component(cid, data):
    return supa.update("components", {"id": f"eq.{cid}"}, data)

def delete_component(cid):
    return supa.delete("components", {"id": f"eq.{cid}"})

def get_low_stock_components():
    comps = get_components()
    return [c for c in comps
            if float(c.get("current_stock", 0)) <= float(c.get("reorder_level", 0))
            and float(c.get("reorder_level", 0)) > 0]

# ── Component BOM ─────────────────────────────────────────

def get_component_bom(component_id):
    return supa.select("component_bom", {"component_id": f"eq.{component_id}"})

def save_component_bom(component_id, items):
    supa.delete("component_bom", {"component_id": f"eq.{component_id}"})
    for item in items:
        if item.get("material_id") and float(item.get("quantity_used", 0)) > 0:
            supa.insert("component_bom", {
                "component_id": int(component_id),
                "material_id": int(item["material_id"]),
                "quantity_used": float(item["quantity_used"]),
            })

def calculate_component_cost(component_id):
    bom = get_component_bom(component_id)
    total = 0
    for item in bom:
        mat = get_raw_material(item["material_id"])
        if mat:
            total += float(mat.get("cost_per_unit", 0)) * float(item.get("quantity_used", 0))
    return round(total, 2)

def manufacture_component(component_id, quantity, notes="", wastage_percent=0):
    """Deduct raw materials and add to component stock, accounting for wastage."""
    bom = get_component_bom(component_id)
    errors = []
    wastage_factor = 1 + float(wastage_percent or 0) / 100.0
    for item in bom:
        mat = get_raw_material(item["material_id"])
        if not mat:
            continue
        needed = float(item["quantity_used"]) * float(quantity) * wastage_factor
        available = float(mat.get("current_stock", 0))
        if available < needed:
            errors.append(f"Not enough {mat['name']}: need {needed:.2f} {mat['unit']} (incl. {wastage_percent}% waste), have {available}")
    if errors:
        return False, errors
    # Deduct materials (including waste)
    total_waste_cost = 0.0
    for item in bom:
        mat = get_raw_material(item["material_id"])
        if mat:
            base_needed = float(item["quantity_used"]) * float(quantity)
            waste_qty = base_needed * float(wastage_percent or 0) / 100.0
            total_needed = base_needed + waste_qty
            new_stock = max(0, float(mat.get("current_stock", 0)) - total_needed)
            supa.update("raw_materials", {"id": f"eq.{item['material_id']}"}, {"current_stock": new_stock})
            total_waste_cost += waste_qty * float(mat.get("cost_per_unit", 0))
    # Add to component stock (only non-wasted quantity)
    comp = get_component(component_id)
    if comp:
        new_stock = float(comp.get("current_stock", 0)) + float(quantity)
        supa.update("components", {"id": f"eq.{component_id}"}, {"current_stock": new_stock})
    # Log it with waste info
    supa.insert("manufacture_log", {
        "component_id": int(component_id),
        "quantity_made": float(quantity),
        "wastage_percent": float(wastage_percent or 0),
        "waste_cost": round(total_waste_cost, 2),
        "notes": notes,
    })
    return True, []


def get_manufacturing_analytics():
    """Aggregate manufacture_log for analytics: total runs, total waste cost, waste rate."""
    from datetime import datetime, timezone, timedelta
    logs = supa.select("manufacture_log", order="manufactured_at.desc") or []
    now = datetime.now(timezone.utc)
    total_runs = len(logs)
    total_waste_cost = sum(float(l.get("waste_cost", 0)) for l in logs)
    total_qty = sum(float(l.get("quantity_made", 0)) for l in logs)
    avg_waste_pct = (
        sum(float(l.get("wastage_percent", 0)) for l in logs) / total_runs
        if total_runs > 0 else 0
    )
    # Monthly waste cost (last 6 months)
    monthly_waste = {}
    monthly_qty = {}
    for i in range(5, -1, -1):
        d = now - timedelta(days=30 * i)
        key = d.strftime("%b")
        monthly_waste[key] = 0
        monthly_qty[key] = 0
    for l in logs:
        ts = l.get("manufactured_at") or l.get("created_at", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                key = dt.strftime("%b")
                if key in monthly_waste:
                    monthly_waste[key] += float(l.get("waste_cost", 0))
                    monthly_qty[key] += float(l.get("quantity_made", 0))
            except Exception:
                pass
    return {
        "total_runs": total_runs,
        "total_waste_cost": round(total_waste_cost, 2),
        "total_qty_made": round(total_qty, 2),
        "avg_waste_pct": round(avg_waste_pct, 1),
        "monthly_waste": monthly_waste,
        "monthly_qty": monthly_qty,
        "recent_logs": logs[:20],
    }

# ── Product BOM ───────────────────────────────────────────

def get_product_bom(product_id):
    return supa.select("product_bom", {"product_id": f"eq.{product_id}"})

def save_product_bom(product_id, items):
    supa.delete("product_bom", {"product_id": f"eq.{product_id}"})
    for item in items:
        qty = float(item.get("quantity_used", 0))
        if qty <= 0:
            continue
        row = {"product_id": str(product_id), "item_type": item["item_type"], "quantity_used": qty}
        if item["item_type"] == "material" and item.get("material_id"):
            row["material_id"] = int(item["material_id"])
        elif item["item_type"] == "component" and item.get("component_id"):
            row["component_id"] = int(item["component_id"])
        else:
            continue
        supa.insert("product_bom", row)

def calculate_product_bom_cost(product_id):
    bom = get_product_bom(product_id)
    pc = get_product_cost(product_id) or {}
    material_cost = 0
    breakdown = []
    for item in bom:
        if item["item_type"] == "material" and item.get("material_id"):
            mat = get_raw_material(item["material_id"])
            if mat:
                cost = float(mat.get("cost_per_unit", 0)) * float(item["quantity_used"])
                material_cost += cost
                breakdown.append({
                    "name": mat["name"], "icon": mat.get("icon", "🧪"),
                    "type": "material", "qty": item["quantity_used"],
                    "unit": mat["unit"], "cost": round(cost, 2)
                })
        elif item["item_type"] == "component" and item.get("component_id"):
            comp = get_component(item["component_id"])
            if comp:
                comp_cost = calculate_component_cost(item["component_id"])
                cost = comp_cost * float(item["quantity_used"])
                material_cost += cost
                breakdown.append({
                    "name": comp["name"], "icon": comp.get("icon", "🔧"),
                    "type": "component", "qty": item["quantity_used"],
                    "unit": comp["unit"], "cost": round(cost, 2)
                })
    labour = float(pc.get("labour_cost", 0))
    overhead = float(pc.get("overhead_cost", 0))
    margin = float(pc.get("margin_percent", 30))
    total = material_cost + labour + overhead
    suggested = round(total * (1 + margin / 100), 2) if total > 0 else 0
    return {
        "breakdown": breakdown,
        "material_cost": round(material_cost, 2),
        "labour_cost": round(labour, 2),
        "overhead_cost": round(overhead, 2),
        "total_cost": round(total, 2),
        "margin_percent": margin,
        "suggested_price": suggested,
    }

# ── Order Requirements & Auto-deduction ──────────────────

def get_order_requirements(order_id):
    return supa.select("order_requirements", {"order_id": f"eq.{order_id}"})

def calculate_order_requirements(order_id):
    """Work out all materials + components needed for an order."""
    items = get_order_items(order_id)
    requirements = {}  # key: 'material_X' or 'component_X'
    for item in items:
        qty = int(item.get("quantity", 1))
        bom = get_product_bom(str(item["product_id"]))
        for b in bom:
            needed = float(b["quantity_used"]) * qty
            if b["item_type"] == "material" and b.get("material_id"):
                key = f"material_{b['material_id']}"
                requirements[key] = requirements.get(key, {
                    "item_type": "material", "material_id": b["material_id"],
                    "component_id": None, "quantity_needed": 0
                })
                requirements[key]["quantity_needed"] += needed
            elif b["item_type"] == "component" and b.get("component_id"):
                key = f"component_{b['component_id']}"
                requirements[key] = requirements.get(key, {
                    "item_type": "component", "material_id": None,
                    "component_id": b["component_id"], "quantity_needed": 0
                })
                requirements[key]["quantity_needed"] += needed
    return list(requirements.values())

def check_requirements_availability(requirements):
    """Check if we have enough stock for each requirement."""
    result = []
    for req in requirements:
        r = dict(req)
        if r["item_type"] == "material":
            mat = get_raw_material(r["material_id"])
            if mat:
                r["name"] = mat["name"]
                r["icon"] = mat.get("icon", "🧪")
                r["unit"] = mat["unit"]
                r["available"] = float(mat.get("current_stock", 0))
                r["is_available"] = r["available"] >= r["quantity_needed"]
            else:
                r["name"] = "Unknown"
                r["icon"] = "❓"
                r["unit"] = ""
                r["available"] = 0
                r["is_available"] = False
        elif r["item_type"] == "component":
            comp = get_component(r["component_id"])
            if comp:
                r["name"] = comp["name"]
                r["icon"] = comp.get("icon", "🔧")
                r["unit"] = comp["unit"]
                r["available"] = float(comp.get("current_stock", 0))
                r["is_available"] = r["available"] >= r["quantity_needed"]
            else:
                r["name"] = "Unknown"
                r["icon"] = "❓"
                r["unit"] = ""
                r["available"] = 0
                r["is_available"] = False
        result.append(r)
    return result

def deduct_order_materials(order_id):
    """Deduct all materials and components when order is confirmed."""
    reqs = calculate_order_requirements(order_id)
    for req in reqs:
        needed = float(req["quantity_needed"])
        if req["item_type"] == "material" and req.get("material_id"):
            mat = get_raw_material(req["material_id"])
            if mat:
                new_stock = max(0, float(mat.get("current_stock", 0)) - needed)
                supa.update("raw_materials", {"id": f"eq.{req['material_id']}"}, {"current_stock": new_stock})
        elif req["item_type"] == "component" and req.get("component_id"):
            comp = get_component(req["component_id"])
            if comp:
                new_stock = max(0, float(comp.get("current_stock", 0)) - needed)
                supa.update("components", {"id": f"eq.{req['component_id']}"}, {"current_stock": new_stock})


def delete_order(oid):
    """Hard delete an order and all its items/tracking."""
    supa.delete("order_items",  {"order_id": f"eq.{oid}"})
    supa.delete("tracking",     {"order_id": f"eq.{oid}"})
    supa.delete("notifications",{"order_id": f"eq.{oid}"})
    return supa.delete("orders", {"id": f"eq.{oid}"})
