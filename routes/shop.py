from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
import models
import supa
from services.commerce import availability, quantity, line_key, earliest_date, coupon_discount, money
from services.cart import normalize, resolve, selection
from routes.auth import login_required

shop_bp = Blueprint("shop", __name__)


def _cart():
    session["cart"] = normalize(session.get("cart", {}))
    return session["cart"]


def _cart_count():
    return sum(line["qty"] for line in _cart().values())


def _cart_total(cart):
    return sum(i['subtotal'] for i in resolve(cart))


def inject_cart():
    from flask import g, request
    from datetime import date
    # Admin templates don't render storefront navigation/cart/settings.
    if request.blueprint == 'admin' or request.path == '/healthz':
        return {'current_year': date.today().year}
    try:
        g.store_settings = models.get_all_settings()
        g.nav_categories = models.get_public_merchandising()['categories']
    except Exception:
        # Preserve useful error pages, but do not silently change admin data.
        import logging
        logging.getLogger(__name__).exception('Storefront navigation unavailable')
        g.store_settings = {}
        g.nav_categories = []
    return {'cart_count': _cart_count(), 'store': g.store_settings,
            'nav_categories': g.nav_categories,
            'nav_occasions': getattr(g, 'public_merchandising', {}).get('occasions', []),
            'current_year': date.today().year}


@shop_bp.route("/")
def index():
    from flask import g
    merchandising = models.get_public_merchandising()
    products = g.public_products
    featured = [p for p in products if p.get('featured')][:6]
    cat_images = {}
    for product in products:
        if product.get('images'):
            cat_images.setdefault(product.get('category_id'), product['images'][0])
    try:
        testimonials = supa.select('testimonials', {'active': 'eq.true'})
    except supa.SupabaseError:
        testimonials = []
    return render_template("shop/index.html", featured=featured,
                           hero_products=[p for p in products if p.get('images')][:2],
                           categories=merchandising['categories'], cat_images=cat_images,
                           flash_products=[p for p in products if models.is_flash_active(p) and p.get('is_flash_sale')][:3],
                           occasions=merchandising['occasions'],
                           collections=[c for c in merchandising['collections'] if c.get('featured')],
                           testimonials=testimonials)


@shop_bp.route("/shop")
def shop():
    category_id=request.args.get('category')
    search=request.args.get('q','').strip()[:150]
    sort=request.args.get('sort','featured')
    from flask import g
    merchandising=models.get_public_merchandising()
    products=list(g.public_products)
    if category_id: products=[p for p in products if str(p.get('category_id'))==category_id]
    categories=merchandising['categories']
    category_names={str(c['id']):c['name'] for c in categories}
    if search:
        query=search.casefold()
        products=[p for p in products if query in (' '.join([p.get('title',''),p.get('description') or '',category_names.get(str(p.get('category_id')),'')])).casefold()]
    products=[p for p in products if availability(p)['published']]
    mode=request.args.get('availability','')
    if mode: products=[p for p in products if availability(p)['mode']==mode]
    if request.args.get('in_stock')=='1': products=[p for p in products if availability(p)['mode'] in ('READY_TO_SHIP','ONE_OF_ONE') and availability(p)['purchasable']]
    on_sale=request.args.get('on_sale')=='1'
    if on_sale: products=[p for p in products if models.discounted_price(p)<float(p['price'])]
    for param,comparison in [('price_min',lambda x,y:x>=y),('price_max',lambda x,y:x<=y)]:
        try:
            if request.args.get(param): products=[p for p in products if comparison(models.discounted_price(p),float(request.args[param]))]
        except ValueError: flash('Enter a valid price range.','error')
    for kind,table,column in [('collection','collection_products','collection_id'),('occasion','product_occasions','occasion_id')]:
        if request.args.get(kind):
            ids={str(r['product_id']) for r in supa.select(table,{column:'eq.'+request.args[kind]})}
            products=[p for p in products if str(p['id']) in ids]
    if sort in ('price_asc','price_desc'): products.sort(key=models.discounted_price,reverse=sort=='price_desc')
    elif sort=='newest': products.sort(key=lambda p:p.get('created_at') or '',reverse=True)
    elif sort=='featured': products.sort(key=lambda p:bool(p.get('featured')),reverse=True)
    return render_template('shop/shop.html',products=products,categories=categories,selected_category=category_id,sort=sort,in_stock=request.args.get('in_stock')=='1',on_sale=on_sale,search=search,collections=merchandising['collections'],occasions=merchandising['occasions'])


@shop_bp.route("/product/<pid>")
def product(pid):
    p = models.get_product(pid)
    if not p or not availability(p)["published"]:
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
                           related=related, can_review=bool(session.get("user_id") and models.review_eligible(pid,session["user_id"])))


@shop_bp.route("/product/<pid>/review", methods=["POST"])
@login_required
def submit_review(pid):
    if not models.review_eligible(pid, session['user_id']):
        flash('Reviews are available after your purchase is delivered.', 'error')
        return redirect(url_for('shop.product', pid=pid))
    try:
        rating = int(request.form.get('rating', 0))
    except ValueError:
        rating = 0
    if rating not in range(1, 6):
        flash('Choose a rating from 1 to 5.', 'error')
        return redirect(url_for('shop.product', pid=pid))
    comment = request.form.get("comment", "").strip()
    existing = models.get_review_by_user(pid, session["user_id"])
    if existing:
        models.update_review(existing["id"], {"rating": rating, "comment": comment, "verified_purchase":True})
    else:
        models.create_review({"product_id": pid, "user_id": session["user_id"],
                               "rating": rating, "comment": comment, "verified_purchase":True})
    return redirect(url_for("shop.product", pid=pid))


@shop_bp.route('/cart')
def cart():
    try:
        items = resolve(_cart(), strict=False)
    except ValueError as error:
        flash(str(error), 'error')
        items = []
    return render_template('shop/cart.html', items=items, total=sum(i['subtotal'] for i in items))


@shop_bp.route('/cart/add/<pid>', methods=['POST'])
def cart_add(pid):
    try:
        p = models.get_product(pid)
        if not p or not availability(p)['purchasable']:
            raise ValueError('This creation is not currently accepting orders.')
        qty = quantity(request.form.get('qty', 1))
        ids, personal = selection(p, request.form)
        key = line_key(pid, ids, personal)
        bag = _cart()
        total = qty + bag.get(key, {}).get('qty', 0)
        quantity(total)
        if total > int(p.get('max_order_quantity') or 99):
            raise ValueError('This exceeds the maximum order quantity.')
        if availability(p)['mode'] in ('READY_TO_SHIP','ONE_OF_ONE'):
            combined = qty + sum(l['qty'] for l in bag.values() if str(l['product_id']) == str(pid))
            if combined > int(p.get('stock') or 0): raise ValueError('The requested quantity is unavailable.')
        import json
        candidate = dict(bag)
        candidate[key] = {'product_id':str(pid), 'qty':total, 'variant_ids':ids, 'personalization':personal}
        if len(json.dumps(candidate)) > 2800: raise ValueError('Your bag has reached its size limit. Please complete this order before adding more personalisations.')
        bag[key] = candidate[key]
        session.modified = True
        flash('Added to your bag.', 'success')
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('shop.product', pid=pid))
    return redirect(url_for('shop.cart'))


@shop_bp.route('/cart/update/<pid>', methods=['POST'])
def cart_update(pid):
    bag = _cart()
    try:
        if pid in bag: bag[pid]['qty'] = quantity(request.form.get('qty', 1))
        session.modified = True
    except ValueError as error: flash(str(error), 'error')
    return redirect(url_for('shop.cart'))


@shop_bp.route('/cart/remove/<pid>', methods=['POST'])
def cart_remove(pid):
    _cart().pop(pid, None)
    session.modified = True
    return redirect(url_for('shop.cart'))


@shop_bp.route('/checkout', methods=['GET','POST'])
def checkout():
    import secrets, emails
    if not _cart(): return redirect(url_for('shop.cart'))
    user = models.get_user_by_id(session['user_id']) if session.get('user_id') else {}
    try:
        items = resolve(_cart())
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('shop.cart'))
    subtotal = sum(i['subtotal'] for i in items)
    min_date = earliest_date(items, models.get_setting('processing_buffer') or 0).isoformat()
    session.setdefault('checkout_key', secrets.token_urlsafe(24))
    error = None
    discount = money(0)
    if request.method == 'POST':
        try:
            import re
            name = request.form.get('name','').strip()[:150]
            email = request.form.get('email','').strip().lower()[:254]
            phone = request.form.get('phone','').strip()[:30]
            delivery = request.form.get('delivery_type','delivery')
            address = request.form.get('address','').strip()[:2000]
            if not name or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(re.sub(r'\D','',phone)) < 7:
                raise ValueError('Enter your name, valid email and phone number.')
            if delivery not in ('delivery','pickup') or (delivery == 'delivery' and len(address)<10):
                raise ValueError('Enter a complete delivery address.')
            pref = request.form.get('preferred_delivery_date') or None
            if pref:
                from datetime import date
                if date.fromisoformat(pref) < date.fromisoformat(min_date): raise ValueError('Choose a date on or after '+min_date+'.')
            code = request.form.get('coupon_code','').strip().upper()
            if code: discount = coupon_discount(models.get_coupon(code), subtotal)
            payload = {'user_id':session.get('user_id'), 'name':name,'email':email,'phone':phone,
                       'address':address if delivery=='delivery' else 'SELF PICKUP', 'delivery_type':delivery,
                       'preferred_delivery_date':pref, 'coupon_code':code or None,
                       'tracking_token':secrets.token_urlsafe(32), 'idempotency_key':session['checkout_key'],
                       'gift_card_code':request.form.get('gift_card_code','').strip().upper() or None, 'gift_message':request.form.get('gift_message','')[:1000], 'order_notes':request.form.get('order_notes','')[:2000]}
            lines = [{'product_id':str(i['product']['id']),'quantity':i['qty'],'variant_ids':i['variant_ids'], 'personalization':i['personalization']} for i in items]
            order = supa.rpc('place_commerce_order', {'p_order':payload,'p_lines':lines})
            if not order: raise ValueError('We could not place your order. Availability may have changed. Please try again.')
            session.pop('cart',None); session.pop('checkout_key',None)
            emails.send_order_placed(email, order)
            return redirect(url_for('shop.guest_order', token=order['tracking_token']))
        except (ValueError, TypeError) as exc: error = str(exc)
    return render_template('shop/checkout.html',items=items,subtotal=subtotal,discount=discount,user=user or {},coupon_error=error,min_date=min_date)


@shop_bp.route('/order/<token>')
def guest_order(token):
    from flask import abort
    rows = supa.select('orders', {'tracking_token':'eq.'+token})
    if not rows: abort(404)
    order = rows[0]
    return render_template('shop/confirmation.html', order=order, items=models.get_order_items(order['id']), tracking=models.get_tracking(order['id']))


@shop_bp.route('/newsletter', methods=['POST'])
def newsletter():
    import re
    email = request.form.get('email','').strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
        flash('Enter a valid email address.', 'error')
    elif supa.rpc('subscribe_newsletter', {'p_email':email}):
        flash('You’re on the list. Thank you for joining us.', 'success')
    else: flash('Subscription could not be saved. Please try again.', 'error')
    return redirect(url_for('shop.index'))


@shop_bp.route("/custom-order", methods=["GET", "POST"])
def custom_order():
    success = False
    tracking_token = None
    if request.method == "POST":
        import re
        if not request.form.get('name','').strip() or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',request.form.get('email','').strip()) or len(request.form.get('description','').strip())<10:
            flash('Please enter your name, a valid email and a description of at least 10 characters.','error')
            return redirect(url_for('shop.custom_order'))
        import supa, uuid, secrets
        ref_url = None
        ref_file = request.files.get("reference_image")
        if ref_file and ref_file.filename:
            path = f"custom/{uuid.uuid4()}-{ref_file.filename}"
            try:
                ref_url = supa.upload_file('everbloom', path, ref_file.read(), ref_file.content_type)
                if not ref_url:
                    raise ValueError('Reference image could not be uploaded.')
            except (ValueError, supa.SupabaseError) as error:
                flash(f'Image upload failed: {error}', 'error')
                return redirect(url_for('shop.custom_order'))
        tracking_token = secrets.token_urlsafe(24)
        data = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "description": request.form.get("description", "").strip(),
            "budget": request.form.get("budget", "").strip(),
            "craft_type": request.form.get("craft_type", "").strip(),
            "occasion": request.form.get("occasion", "").strip(),
            "size_preference": request.form.get("size_preference", "").strip(),
            "colour_preference": request.form.get("colour_preference", "").strip(),
            "reference_image_url": ref_url,
            "user_id": session.get("user_id"),
            "tracking_token": tracking_token,
            "preferred_delivery_date": request.form.get("preferred_delivery_date", "").strip() or None,
            "status": "pending",
        }
        if models.create_custom_request(data):
            import emails
            emails.send_custom_request_received(data["email"], data["name"])
            # Alert admin
            import os
            admin_email = os.environ.get("MAIL_USERNAME", "")
            if admin_email:
                site_url = os.environ.get("SITE_URL", "http://localhost:5000")
                emails.send_manual_email(
                    admin_email,
                    f"New Custom Order Request — {data['name']}",
                    f"New custom order request from {data['name']} ({data['email']}).\n\nCraft Type: {data.get('craft_type','')}\nBudget: {data.get('budget','')}\n\nDescription:\n{data['description']}\n\nView: {site_url}/admin/custom-requests"
                )
            success = True
    from datetime import date, timedelta
    min_date = (date.today() + timedelta(days=14)).isoformat()
    return render_template("shop/custom_order.html", success=success,
                           tracking_token=tracking_token, min_date=min_date)


@shop_bp.route("/custom-order/track/<token>")
def custom_order_track(token):
    req = models.get_custom_request_by_token(token)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("shop.custom_order"))
    return render_template("shop/custom_order_track.html", req=req)


@shop_bp.route("/custom-order/respond/<token>/<response>", methods=["GET","POST"])
def custom_order_respond(token, response):
    if request.method == "GET": return redirect(url_for("shop.custom_order_track",token=token))
    req = models.get_custom_request_by_token(token)
    if not req or req.get("status") != "quoted":
        flash("This link is no longer valid.", "error")
        return redirect(url_for("shop.index"))
    if response == 'accepted':
        order,error=models.convert_custom_to_order(req['id'],req['quoted_price'])
        if error: flash(error,'error')
        else:
            flash('Your custom order is confirmed.','success')
            return redirect(url_for('shop.guest_order',token=order['tracking_token']))
    elif response=='declined':
        models.update_custom_request(req['id'],{'status':'rejected','customer_response':'declined'})
        flash('Quote declined. You can start another creation whenever you’re ready.','info')
    return redirect(url_for('shop.custom_order_track',token=token))


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


@shop_bp.route("/custom-order/cancel/<token>", methods=["POST"])
def custom_order_cancel(token):
    req = models.get_custom_request_by_token(token)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("shop.custom_order"))
    if req.get("status") not in ["pending", "reviewing"]:
        flash("This request can no longer be cancelled.", "error")
        return redirect(url_for("shop.custom_order_track", token=token))
    models.update_custom_request(req["id"], {"status": "rejected", "admin_note": "Cancelled by customer."})
    flash("Your request has been cancelled.", "success")
    return redirect(url_for("shop.custom_order_track", token=token))


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


@shop_bp.route('/policies/<slug>')
def policy(slug):
    from flask import abort
    titles={'shipping':'Shipping & delivery','returns':'Returns & care','privacy':'Privacy policy','terms':'Terms of service'}
    if slug not in titles: abort(404)
    return render_template('shop/policy.html',title=titles[slug],body=models.get_setting('policy_'+slug))


@shop_bp.route('/order/<token>/payment', methods=['GET','POST'])
def guest_payment(token):
    from flask import abort
    rows=supa.select('orders',{'tracking_token':'eq.'+token})
    if not rows: abort(404)
    order=rows[0]
    if order.get('payment_status')!='advance_requested':
        return redirect(url_for('shop.guest_order',token=token))
    if request.method=='POST':
        file=request.files.get('screenshot')
        if file and file.filename:
            try:
                import uuid
                receipt=supa.upload_file('everbloom','payments/'+str(uuid.uuid4())+'.webp',file.read())
                if receipt:
                    models.update_order(order['id'],{'payment_screenshot_url':receipt,'payment_status':'advance_submitted','status':'advance_paid'})
                    models.add_tracking(order['id'],'advance_paid','Payment proof received. Awaiting verification.')
                    flash('Payment proof received. We will verify it shortly.','success')
                    return redirect(url_for('shop.guest_order',token=token))
            except (ValueError, supa.SupabaseError) as error: flash(str(error),'error')
        else: flash('Choose a payment screenshot.','error')
    return render_template('shop/pay_advance.html',order=order,upi_id=models.get_setting('upi_id'),upi_qr_url=models.get_setting('upi_qr_url'))


@shop_bp.route('/robots.txt')
def robots():
    from flask import Response
    return Response('User-agent: *\nDisallow: /admin/\nDisallow: /auth/\nDisallow: /orders/\nDisallow: /order/\nDisallow: /checkout\nDisallow: /custom-order/track/\nSitemap: '+url_for('shop.sitemap',_external=True)+'\n',mimetype='text/plain')

@shop_bp.route('/sitemap.xml')
def sitemap():
    from flask import Response
    from xml.sax.saxutils import escape
    urls=[url_for('shop.index',_external=True),url_for('shop.shop',_external=True),url_for('shop.about',_external=True)]
    urls += [url_for('shop.product',pid=p['id'],_external=True) for p in models.get_products() if availability(p)['published']]
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+escape(u)+'</loc></url>' for u in urls)+'</urlset>',mimetype='application/xml')


@shop_bp.route('/account/notifications')
@login_required
def account_notifications():
    return render_template('account/notifications.html',notifications=models.get_notifications(session['user_id']))
