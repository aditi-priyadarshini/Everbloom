from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
import models
from routes.auth import login_required

shop_bp = Blueprint("shop", __name__)


def _cart():
    return session.setdefault("cart", {})


def _cart_count():
    return sum(_cart().values())


def _cart_total(cart):
    total = 0
    for pid, qty in cart.items():
        p = models.get_product(pid)
        if p:
            total += models.discounted_price(p) * qty
    return round(total, 2)


@shop_bp.context_processor
def inject_cart():
    return {"cart_count": _cart_count()}


@shop_bp.route("/")
def index():
    featured = models.get_products(featured=True, limit=6)
    categories = models.get_categories()
    flash_products = [p for p in models.get_products(flash=True) if models.is_flash_active(p)][:3]
    cat_images = {}
    for cat in categories:
        prods = models.get_products(category_id=cat["id"], limit=4)
        for p in prods:
            imgs = p.get("images") or []
            if imgs:
                cat_images[cat["id"]] = imgs[0]
                break
    return render_template("shop/index.html",
                           featured=featured,
                           categories=categories,
                           flash_products=flash_products,
                           cat_images=cat_images)


@shop_bp.route("/shop")
def shop():
    category_id = request.args.get("category")
    price_max = request.args.get("price_max")
    in_stock = request.args.get("in_stock") == "1"
    on_sale = request.args.get("on_sale") == "1"
    sort = request.args.get("sort", "newest")
    search = request.args.get("q", "").strip()

    order_map = {
        "newest": "created_at.desc",
        "price_asc": "price.asc",
        "price_desc": "price.desc",
    }
    order = order_map.get(sort, "created_at.desc")

    products = models.get_products(
        category_id=category_id,
        in_stock=in_stock,
        on_sale=on_sale,
        order=order,
        search=search or None,
    )

    # Price filter client-side (Supabase free tier doesn't support lte easily without RLS)
    if price_max:
        try:
            pm = float(price_max)
            products = [p for p in products if models.discounted_price(p) <= pm]
        except Exception:
            pass

    categories = models.get_categories()
    return render_template("shop/shop.html",
                           products=products,
                           categories=categories,
                           selected_category=category_id,
                           sort=sort,
                           in_stock=in_stock,
                           on_sale=on_sale,
                           search=search)


@shop_bp.route("/product/<pid>")
def product(pid):
    p = models.get_product(pid)
    if not p:
        flash("Product not found.", "error")
        return redirect(url_for("shop.shop"))
    reviews = models.get_reviews(pid)
    avg = models.avg_rating(reviews)
    variants = models.get_variants(pid)
    user_review = None
    if session.get("user_id"):
        user_review = models.get_review_by_user(pid, session["user_id"])
    related = models.get_products(category_id=p.get("category_id"), limit=4)
    related = [r for r in related if str(r["id"]) != str(pid)][:3]
    wishlisted = models.is_wishlisted(session["user_id"], pid) if session.get("user_id") else False
    return render_template("shop/product.html",
                           product=p,
                           reviews=reviews,
                           avg_rating=avg,
                           variants=variants,
                           wishlisted=wishlisted,
                           user_review=user_review,
                           related=related)


@shop_bp.route("/product/<pid>/review", methods=["POST"])
@login_required
def submit_review(pid):
    rating = int(request.form.get("rating", 5))
    comment = request.form.get("comment", "").strip()
    existing = models.get_review_by_user(pid, session["user_id"])
    if existing:
        models.update_review(existing["id"], {"rating": rating, "comment": comment})
    else:
        models.create_review({"product_id": pid, "user_id": session["user_id"],
                               "rating": rating, "comment": comment})
    return redirect(url_for("shop.product", pid=pid))


@shop_bp.route("/cart")
def cart():
    cart = _cart()
    items = []
    for pid, qty in cart.items():
        p = models.get_product(pid)
        if p:
            items.append({"product": p, "qty": qty,
                          "subtotal": round(models.discounted_price(p) * qty, 2)})
    total = sum(i["subtotal"] for i in items)
    return render_template("shop/cart.html", items=items, total=total)


@shop_bp.route("/cart/add/<pid>", methods=["POST"])
def cart_add(pid):
    qty = int(request.form.get("qty", 1))
    is_preorder = request.form.get("preorder") == "1"
    p = models.get_product(pid)
    if not p:
        flash("Product not found.", "error")
        return redirect(request.referrer or url_for("shop.shop"))

    stock = int(p.get("stock", 0))
    cart = _cart()
    already_in_cart = cart.get(pid, 0)

    if stock <= 0 and not p.get("allow_preorder"):
        flash("This product is out of stock.", "error")
        return redirect(request.referrer or url_for("shop.shop"))

    # Prevent adding more than available stock
    if stock > 0 and (already_in_cart + qty) > stock:
        allowed = max(0, stock - already_in_cart)
        if allowed <= 0:
            flash(f"You already have the maximum available quantity ({stock}) in your cart.", "error")
        else:
            cart[pid] = already_in_cart + allowed
            session.modified = True
            flash(f"Only {stock} available — added {allowed} to your cart.", "info")
        return redirect(request.referrer or url_for("shop.cart"))

    cart[pid] = already_in_cart + qty
    preorders = session.setdefault("preorder_items", [])
    if is_preorder and pid not in preorders:
        preorders.append(pid)
    session.modified = True
    if is_preorder:
        flash("Pre-order added! We'll craft this especially for you.", "success")
    else:
        flash("Added to cart!", "success")
    return redirect(request.referrer or url_for("shop.cart"))


@shop_bp.route("/cart/update/<pid>", methods=["POST"])
def cart_update(pid):
    qty = int(request.form.get("qty", 1))
    cart = _cart()
    if qty <= 0:
        cart.pop(pid, None)
    else:
        p = models.get_product(pid)
        stock = int(p.get("stock", 0)) if p else 0
        preorders = session.get("preorder_items", [])
        is_pre = pid in preorders
        # Cap at stock unless preorder
        if stock > 0 and not is_pre and qty > stock:
            qty = stock
            flash(f"Quantity capped at {stock} (available stock).", "info")
        cart[pid] = qty
    session.modified = True
    return redirect(url_for("shop.cart"))


@shop_bp.route("/cart/remove/<pid>", methods=["POST"])
def cart_remove(pid):
    _cart().pop(pid, None)
    session.modified = True
    return redirect(url_for("shop.cart"))


@shop_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = _cart()
    if not cart:
        return redirect(url_for("shop.cart"))

    items = []
    for pid, qty in cart.items():
        p = models.get_product(pid)
        if p:
            items.append({"product": p, "qty": qty,
                          "subtotal": round(models.discounted_price(p) * qty, 2)})
    subtotal = sum(i["subtotal"] for i in items)

    coupon_error = None
    discount = 0
    coupon_obj = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        coupon_code = request.form.get("coupon_code", "").strip().upper()
        gift_card_code = request.form.get("gift_card_code", "").strip().upper()
        gift_card_discount = 0
        gift_card_obj = None

        if coupon_code:
            coupon_obj = models.get_coupon(coupon_code)
            if coupon_obj:
                discount = round(subtotal * coupon_obj["discount_percent"] / 100, 2)
            else:
                coupon_error = "Invalid or expired coupon."

        if gift_card_code and not coupon_error:
            try:
                gift_card_obj = models.get_gift_card(gift_card_code)
                if gift_card_obj:
                    gift_card_discount = min(float(gift_card_obj["balance"]), subtotal - discount)
                else:
                    coupon_error = "Invalid or expired gift card."
            except Exception:
                coupon_error = "Gift card feature coming soon."

        if not coupon_error:
            delivery_type = request.form.get("delivery_type", "delivery")
            if delivery_type == "pickup":
                address = "SELF PICKUP"

            # ── Stock validation ── check live stock right now before placing
            stock_errors = []
            for i in items:
                p = i["product"]
                live = models.get_product(str(p["id"]))  # fresh from DB
                if not live:
                    stock_errors.append(f"'{p['title']}' is no longer available.")
                    continue
                available = int(live.get("stock", 0))
                can_preorder = live.get("allow_preorder", False)
                if available <= 0 and not can_preorder:
                    stock_errors.append(f"'{p['title']}' is out of stock.")
                elif available > 0 and i["qty"] > available and not can_preorder:
                    stock_errors.append(
                        f"Only {available} unit(s) of '{p['title']}' available. You have {i['qty']} in cart."
                    )

            if stock_errors:
                for err in stock_errors:
                    flash(err, "error")
                return render_template("shop/checkout.html",
                                       items=items, subtotal=subtotal,
                                       discount=discount, user=user,
                                       coupon_error=None)

            is_preorder_order = any(str(i["product"]["id"]) in preorder_pids for i in items)
            total = round(subtotal - discount - gift_card_discount, 2)
            total = max(0, total)
            order = models.create_order({
                "user_id": session["user_id"],
                "name": name, "phone": phone, "address": address,
                "total": total,
                "coupon_code": coupon_code or None,
                "discount_amount": discount,
                "delivery_type": delivery_type,
                "shipping_charge": 0,
                "is_preorder": is_preorder_order,
                "status": "placed",
            })
            if order:
                for i in items:
                    p = i["product"]
                    live = models.get_product(str(p["id"]))
                    models.create_order_item({
                        "order_id": order["id"],
                        "product_id": str(p["id"]),
                        "title": p["title"],
                        "price": models.discounted_price(p),
                        "quantity": i["qty"],
                        "image_url": (p.get("images") or [""])[0],
                    })
                    # Only reduce stock for non-preorder items with stock
                    if live and int(live.get("stock", 0)) > 0:
                        new_stock = max(0, int(live.get("stock", 0)) - i["qty"])
                        models.update_product(str(p["id"]), {"stock": new_stock})

                models.add_tracking(order["id"], "placed", "Order placed by customer.")
                models.create_notification(session["user_id"],
                                           f"Order #{str(order['id'])[:8].upper()} placed!",
                                           url_for("orders.order_detail", oid=order["id"]))
                if coupon_code and coupon_obj:
                    models.use_coupon(coupon_code)
                if gift_card_code and gift_card_obj and gift_card_discount > 0:
                    try:
                        models.use_gift_card(gift_card_code, gift_card_discount)
                    except Exception:
                        pass

                import emails, os
                user = models.get_user_by_id(session["user_id"])
                emails.send_order_placed(user["email"], order)
                # Alert admin
                admin_email = os.environ.get("MAIL_USERNAME", "")
                if admin_email:
                    site_url = os.environ.get("SITE_URL", "http://localhost:5000")
                    emails.send_admin_new_order(admin_email, order, site_url)

                session.pop("cart", None)
                flash("Order placed successfully!", "success")
                return redirect(url_for("orders.orders_list"))

    user = models.get_user_by_id(session["user_id"])
    return render_template("shop/checkout.html",
                           items=items, subtotal=subtotal,
                           discount=discount, user=user,
                           coupon_error=coupon_error)


@shop_bp.route("/custom-order", methods=["GET", "POST"])
def custom_order():
    success = False
    if request.method == "POST":
        import supa
        ref_url = None
        ref_file = request.files.get("reference_image")
        if ref_file and ref_file.filename:
            import uuid
            path = f"custom/{uuid.uuid4()}-{ref_file.filename}"
            ref_url = supa.upload_file("everbloom", path, ref_file.read(), ref_file.content_type)
        data = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "description": request.form.get("description", "").strip(),
            "budget": request.form.get("budget", "").strip(),
            "reference_image_url": ref_url,
            "user_id": session.get("user_id"),
        }
        if models.create_custom_request(data):
            import emails
            emails.send_custom_request_received(data["email"], data["name"])
            success = True
    return render_template("shop/custom_order.html", success=success)


@shop_bp.route("/wishlist")
@login_required
def wishlist():
    try:
        items = models.get_wishlist(session["user_id"])
    except Exception:
        items = []
    return render_template("shop/wishlist.html", items=items)


@shop_bp.route("/wishlist/toggle/<pid>", methods=["POST"])
@login_required
def wishlist_toggle(pid):
    try:
        added = models.toggle_wishlist(session["user_id"], pid)
        flash("Added to wishlist!" if added else "Removed from wishlist.", "success")
    except Exception:
        flash("Wishlist feature coming soon.", "info")
    return redirect(request.referrer or url_for("shop.shop"))


@shop_bp.route("/back-in-stock/<pid>", methods=["POST"])
def back_in_stock(pid):
    try:
        email = request.form.get("email", "").strip()
        if email:
            models.add_back_in_stock_alert(pid, email, session.get("user_id"))
            flash("We'll notify you when it's back!", "success")
    except Exception:
        flash("Notification feature coming soon.", "info")
    return redirect(request.referrer or url_for("shop.shop"))


@shop_bp.route("/faq")
def faq():
    try:
        faqs = models.get_faqs()
    except Exception:
        faqs = []
    return render_template("shop/faq.html", faqs=faqs)


@shop_bp.route("/artisans")
def artisans():
    try:
        artisan_list = models.get_artisans()
    except Exception:
        artisan_list = []
    return render_template("shop/artisans.html", artisans=artisan_list)


@shop_bp.route("/artisans/<aid>")
def artisan_detail(aid):
    try:
        artisan = models.get_artisan(aid)
    except Exception:
        artisan = None
    if not artisan:
        return redirect(url_for("shop.artisans"))
    return render_template("shop/artisan_detail.html", artisan=artisan)


@shop_bp.route("/about")
def about():
    return render_template("shop/about.html")


@shop_bp.route("/api/notifications")
@login_required
def notifications_api():
    try:
        notifs = models.get_notifications(session["user_id"])
        unread = len([n for n in notifs if not n["read"]])
        return jsonify({"notifications": notifs, "unread": unread})
    except Exception as e:
        return jsonify({"notifications": [], "unread": 0})


@shop_bp.route("/api/notifications/read", methods=["POST"])
@login_required
def mark_read():
    models.mark_notifications_read(session["user_id"])
    return jsonify({"ok": True})
