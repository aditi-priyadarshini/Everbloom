import math
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from flask_login import current_user
from models import Product, Category, Order, Tracking, Notification, final_price, first_image, image_list
from emails import mail_order_placed

bp = Blueprint("shop", __name__)


# ── Cart helpers ──────────────────────────────────────────────
def get_cart():
    return session.get("cart", {})

def save_cart(c):
    session["cart"] = c
    session.modified = True

def cart_total(c):
    return sum(i["price"] * i["qty"] for i in c.values())


# ── Pages ─────────────────────────────────────────────────────
@bp.route("/")
def home():
    cats     = Category.all()
    featured = Product.featured(4)
    newest   = Product.newest(8)
    return render_template("shop/home.html", cats=cats, featured=featured, newest=newest)


@bp.route("/shop")
def shop():
    q        = request.args.get("q", "").strip()
    cat_slug = request.args.get("cat", "")
    sort     = request.args.get("sort", "newest")
    min_p    = request.args.get("min_p", type=float)
    max_p    = request.args.get("max_p", type=float)
    in_stock = bool(request.args.get("in_stock"))
    on_sale  = bool(request.args.get("on_sale"))
    page     = request.args.get("page", 1, type=int)

    sel_cat = Category.by_slug(cat_slug) if cat_slug else None
    cat_id  = sel_cat["id"] if sel_cat else None

    products, total = Product.list(cat_id=cat_id, q=q, sort=sort, min_p=min_p, max_p=max_p,
                                   in_stock=in_stock, on_sale=on_sale, page=page)
    cats       = Category.all()
    total_pages = math.ceil(total / 12) if total else 1

    return render_template("shop/shop.html",
                           products=products, total=total, page=page, total_pages=total_pages,
                           cats=cats, sel_cat=sel_cat,
                           q=q, sort=sort, min_p=min_p, max_p=max_p,
                           in_stock=in_stock, on_sale=on_sale)


@bp.route("/product/<int:pid>")
def product(pid):
    p = Product.get(pid)
    if not p:
        flash("Product not found.", "error")
        return redirect(url_for("shop.shop"))
    related = Product.related(p["category_id"], p["id"]) if p.get("category_id") else []
    return render_template("shop/product.html", p=p, related=related)


# ── Cart ──────────────────────────────────────────────────────
@bp.route("/cart")
def cart():
    c = get_cart()
    return render_template("shop/cart.html", cart=c, total=cart_total(c))


@bp.route("/cart/add", methods=["POST"])
def cart_add():
    pid = request.form.get("pid", type=int)
    qty = request.form.get("qty", 1, type=int)
    p   = Product.get(pid)
    if not p:
        flash("Product not found.", "error")
        return redirect(url_for("shop.shop"))
    c   = get_cart()
    key = str(pid)
    fp  = final_price(p)
    fi  = first_image(p)
    if key in c:
        c[key]["qty"] = min(c[key]["qty"] + qty, p["stock_qty"])
    else:
        c[key] = {"id": p["id"], "title": p["title"], "price": fp,
                  "image": fi, "stock_qty": p["stock_qty"], "qty": min(qty, p["stock_qty"])}
    save_cart(c)
    flash(f'Added "{p["title"]}" to cart!', "success")
    return redirect(request.referrer or url_for("shop.cart"))


@bp.route("/cart/update", methods=["POST"])
def cart_update():
    key = request.form.get("pid")
    qty = request.form.get("qty", type=int)
    c   = get_cart()
    if key in c:
        if qty and qty > 0:
            c[key]["qty"] = min(qty, c[key]["stock_qty"])
        else:
            del c[key]
    save_cart(c)
    return redirect(url_for("shop.cart"))


@bp.route("/cart/remove/<pid>", methods=["POST"])
def cart_remove(pid):
    c = get_cart()
    c.pop(str(pid), None)
    save_cart(c)
    return redirect(url_for("shop.cart"))


@bp.route("/cart/clear", methods=["POST"])
def cart_clear():
    session.pop("cart", None)
    return redirect(url_for("shop.cart"))


# ── Checkout ──────────────────────────────────────────────────
@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not current_user.is_authenticated:
        flash("Please log in to checkout.", "info")
        return redirect(url_for("auth.login", next=url_for("shop.checkout")))
    c = get_cart()
    if not c:
        return redirect(url_for("shop.shop"))
    total = cart_total(c)

    if request.method == "POST":
        addr = {k: request.form.get(k, "").strip() for k in ("name","phone","street","city","state","pin")}
        if not all(addr.values()):
            flash("Please fill in all address fields.", "error")
            return render_template("shop/checkout.html", cart=c, total=total, pre=addr)

        notes = request.form.get("notes", "").strip()
        oid   = Order.create(current_user.id, total, addr, notes)
        Order.add_items(oid, c)
        Tracking.add(oid, "placed", "Order placed. We'll review it shortly.")
        Notification.add(current_user.id, oid, "Order Placed 📋", f"Order #{oid:04d} placed successfully!")

        order = Order.get(oid)
        try: mail_order_placed(order)
        except: pass

        for item in c.values():
            Product.deduct(item["id"], item["qty"])

        session.pop("cart", None)
        flash("Order placed! We'll review it and be in touch. 🌿", "success")
        return redirect(url_for("orders.track", oid=oid))

    pre = {"name": current_user.full_name, "phone": current_user.phone or "",
           "street": "", "city": "", "state": "", "pin": ""}
    return render_template("shop/checkout.html", cart=c, total=total, pre=pre)


# ── Notifications API ─────────────────────────────────────────
@bp.route("/api/notifications")
def notifs():
    if not current_user.is_authenticated:
        return jsonify([])
    rows = Notification.for_user(current_user.id)
    return jsonify([{"id":n["id"],"title":n["title"],"message":n["message"],
                     "is_read":n["is_read"],"order_id":n["order_id"],
                     "time":n["created_at"].strftime("%d %b, %I:%M %p")} for n in rows])


@bp.route("/api/notifications/count")
def notif_count():
    if not current_user.is_authenticated:
        return jsonify({"n": 0})
    return jsonify({"n": Notification.unread(current_user.id)})


@bp.route("/api/notifications/read/<int:nid>", methods=["POST"])
def notif_read(nid):
    if current_user.is_authenticated:
        Notification.mark_read(nid, current_user.id)
    return jsonify({"ok": True})


@bp.route("/api/notifications/read-all", methods=["POST"])
def notif_read_all():
    if current_user.is_authenticated:
        Notification.mark_all(current_user.id)
    return jsonify({"ok": True})
