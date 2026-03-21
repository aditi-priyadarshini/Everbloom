import math
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from models import Product, Category, Order, OrderItem, Tracking, Notification
from emails import send_order_received

shop_bp = Blueprint("shop", __name__)

ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}


def get_cart():
    return session.get("cart", {})

def save_cart(cart):
    session["cart"] = cart
    session.modified = True

def cart_total(cart):
    return sum(i["price"] * i["qty"] for i in cart.values())


@shop_bp.route("/")
def home():
    categories = Category.all()
    featured   = Product.featured(4)
    new_items  = Product.newest(4)
    return render_template("shop/home.html", categories=categories,
                           featured=featured, new_items=new_items)


@shop_bp.route("/shop")
def shop():
    q          = request.args.get("q", "").strip()
    cat_slug   = request.args.get("category", "")
    sort       = request.args.get("sort", "newest")
    min_price  = request.args.get("min_price", type=float)
    max_price  = request.args.get("max_price", type=float)
    in_stock   = bool(request.args.get("in_stock"))
    on_sale    = bool(request.args.get("on_sale"))
    page       = request.args.get("page", 1, type=int)

    selected_cat = Category.get_by_slug(cat_slug) if cat_slug else None
    cat_id = selected_cat["id"] if selected_cat else None

    products, total = Product.list(
        category_id=cat_id, search=q, sort=sort,
        min_price=min_price, max_price=max_price,
        in_stock=in_stock, on_sale=on_sale, page=page
    )
    categories  = Category.all()
    total_pages = math.ceil(total / 12) if total else 1

    return render_template("shop/shop.html",
                           products=products, total=total,
                           page=page, total_pages=total_pages,
                           categories=categories, selected_cat=selected_cat,
                           q=q, sort=sort, min_price=min_price, max_price=max_price,
                           in_stock=in_stock, on_sale=on_sale)


@shop_bp.route("/product/<int:product_id>")
def product(product_id):
    p = Product.get(product_id)
    if not p:
        flash("Product not found.", "error")
        return redirect(url_for("shop.shop"))
    related = Product.related(p["category_id"], p["id"]) if p.get("category_id") else []
    return render_template("shop/product.html", product=p, related=related)


@shop_bp.route("/cart")
def cart():
    c = get_cart()
    return render_template("shop/cart.html", cart=c, total=cart_total(c))


@shop_bp.route("/cart/add", methods=["POST"])
def cart_add():
    pid = request.form.get("product_id", type=int)
    qty = request.form.get("qty", 1, type=int)
    p = Product.get(pid)
    if not p:
        flash("Product not found.", "error")
        return redirect(url_for("shop.shop"))
    cart = get_cart()
    key  = str(pid)
    if key in cart:
        cart[key]["qty"] = min(cart[key]["qty"] + qty, p["stock_qty"])
    else:
        cart[key] = {
            "id": p["id"], "title": p["title"],
            "price": float(Product.final_price(p)),
            "image": Product.first_image(p) or "",
            "stock_qty": p["stock_qty"], "qty": min(qty, p["stock_qty"])
        }
    save_cart(cart)
    flash(f'"{p["title"]}" added to cart!', "success")
    return redirect(request.referrer or url_for("shop.cart"))


@shop_bp.route("/cart/update", methods=["POST"])
def cart_update():
    key = request.form.get("product_id")
    qty = request.form.get("qty", type=int)
    cart = get_cart()
    if key in cart:
        if qty and qty > 0:
            cart[key]["qty"] = min(qty, cart[key]["stock_qty"])
        else:
            del cart[key]
    save_cart(cart)
    return redirect(url_for("shop.cart"))


@shop_bp.route("/cart/remove/<int:product_id>", methods=["POST"])
def cart_remove(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    return redirect(url_for("shop.cart"))


@shop_bp.route("/cart/clear", methods=["POST"])
def cart_clear():
    session.pop("cart", None)
    return redirect(url_for("shop.cart"))


@shop_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not current_user.is_authenticated:
        flash("Please log in to checkout.", "info")
        return redirect(url_for("auth.login", next=url_for("shop.checkout")))
    cart = get_cart()
    if not cart:
        return redirect(url_for("shop.shop"))
    total = cart_total(cart)

    if request.method == "POST":
        addr = {
            "name":   request.form.get("addr_name", "").strip(),
            "phone":  request.form.get("addr_phone", "").strip(),
            "street": request.form.get("addr_street", "").strip(),
            "city":   request.form.get("addr_city", "").strip(),
            "state":  request.form.get("addr_state", "").strip(),
            "pin":    request.form.get("addr_pin", "").strip(),
        }
        notes = request.form.get("notes", "").strip()
        if not all(addr.values()):
            flash("Please fill in all address fields.", "error")
            return render_template("shop/checkout.html", cart=cart, total=total,
                                   pre={f"addr_{k}": v for k, v in addr.items()})

        order_id = Order.create(current_user.id, total, addr, notes)
        Order.add_items(order_id, cart)
        Tracking.add(order_id, "draft",
                     "Order placed. Our team will review it shortly.",
                     current_user.id)
        Notification.add(current_user.id, order_id,
                         "Order Received 📋",
                         f"Order #{order_id:04d} placed. We'll review and confirm soon.")

        order_row = Order.get(order_id)
        try:
            send_order_received(order_row)
        except Exception as e:
            pass

        # Deduct stock
        for key, item in cart.items():
            Product.deduct_stock(item["id"], item["qty"])

        session.pop("cart", None)
        flash("Order placed! We'll review it and be in touch soon. 🌸", "success")
        return redirect(url_for("orders.track", order_id=order_id))

    pre = {"addr_name": current_user.full_name, "addr_phone": current_user.phone or "",
           "addr_street": "", "addr_city": "", "addr_state": "", "addr_pin": ""}
    return render_template("shop/checkout.html", cart=cart, total=total, pre=pre)


# ── Notifications API ─────────────────────────────────────────
@shop_bp.route("/notifications")
def notifications():
    if not current_user.is_authenticated:
        return jsonify([])
    notifs = Notification.list(current_user.id)
    return jsonify([{
        "id": n["id"], "title": n["title"], "message": n["message"],
        "is_read": n["is_read"], "order_id": n["order_id"],
        "created_at": n["created_at"].strftime("%d %b %Y, %I:%M %p")
    } for n in notifs])


@shop_bp.route("/notifications/read/<int:nid>", methods=["POST"])
def notification_read(nid):
    if current_user.is_authenticated:
        Notification.mark_read(nid, current_user.id)
    return jsonify({"ok": True})


@shop_bp.route("/notifications/read-all", methods=["POST"])
def notifications_read_all():
    if current_user.is_authenticated:
        Notification.mark_all_read(current_user.id)
    return jsonify({"ok": True})


@shop_bp.route("/notifications/count")
def notification_count():
    if not current_user.is_authenticated:
        return jsonify({"count": 0})
    return jsonify({"count": Notification.unread_count(current_user.id)})
