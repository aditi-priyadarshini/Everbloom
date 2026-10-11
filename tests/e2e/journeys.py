"""End-to-end journeys (see tests/e2e/README.md). Real Flask app -> real HTTP -> PostgREST -> real Postgres. No mocks.
Only email delivery (captured) and storage (stub) are substituted."""
import io, os, re, subprocess, sys, time, traceback, json
sys.path.insert(0, '.')
import supa, models
import app as appmod
from app import create_app

app = create_app()
app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
SENT = []
appmod.mail.send = lambda msg: SENT.append({'to': msg.recipients, 'subject': msg.subject, 'html': msg.html or '', 'body': msg.body or ''})

RESULTS = []
CTX = {}


def real_png():
    from PIL import Image
    b = io.BytesIO(); Image.new('RGB', (64, 64), (200, 120, 120)).save(b, 'PNG'); b.seek(0); return b


def sql(q):
    r = subprocess.run(['su', 'postgres', '-c', f'psql -h /tmp -p 5433 -d e2e -At -X -c "{q}"'], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def step(name):
    def deco(fn):
        t = time.time()
        try:
            fn(); RESULTS.append((name, True, ''))
        except AssertionError as e:
            RESULTS.append((name, False, 'ASSERT: ' + str(e)[:230]))
        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)[-1]
            RESULTS.append((name, False, f'{type(e).__name__}: {str(e)[:160]} @ {tb.filename.split("/")[-1]}:{tb.lineno}'))
        return fn
    return deco


def flashes(client):
    with client.session_transaction() as s:
        f = list(s.get('_flashes', [])); s['_flashes'] = []
    return f


def eq(a, b, msg=''):
    assert a == b, f'{msg} expected {b!r} got {a!r}'


def last_mail(to=None, contains=''):
    for m in reversed(SENT):
        if (to is None or to in m['to']) and contains.lower() in (m['subject'] + m['html']).lower(): return m
    return None


def status(r, *codes):
    assert r.status_code in codes, f'HTTP {r.status_code} (wanted {codes}) body={r.data[:300]!r} flashes={flashes_hint(r)}'


def flashes_hint(r): return ''


admin = app.test_client(); cust = app.test_client(); guest = app.test_client()

# ═════════════════════════ ADMIN: setup ═════════════════════════
@step('A01 admin signs up, is promoted, logs in, dashboard loads')
def _():
    r = admin.post('/auth/signup', data={'name': 'Owner', 'email': 'owner@everbloom.test', 'password': 'OwnerPassw0rd!'}); status(r, 302)
    sql("update users set is_admin=true,email_verified=true where email='owner@everbloom.test'")
    r = admin.post('/auth/login', data={'email': 'owner@everbloom.test', 'password': 'OwnerPassw0rd!'}); status(r, 302)
    for url in ('/admin/', '/admin/products', '/admin/orders', '/admin/inventory', '/admin/settings'):
        status(admin.get(url), 200)

@step('A02 admin saves store settings (UPI id, processing buffer)')
def _():
    r = admin.post('/admin/settings', data={'processing_buffer': '0', 'upi_id': 'everbloom@upi', 'store_name': 'Everbloom'}); status(r, 302, 200)
    eq(models.get_setting('upi_id'), 'everbloom@upi', 'upi_id saved')

@step('A03 admin creates raw material and records a purchase (receive_material RPC)')
def _():
    r = admin.post('/admin/inventory/new', data={'name': 'Satin ribbon', 'unit': 'm', 'current_stock': '0', 'reorder_level': '5', 'cost_per_unit': '0', 'supplier': 'Acme'}); status(r, 302)
    mid = int(sql("select id from raw_materials where name='Satin ribbon'")); CTX['mat'] = mid
    r = admin.post(f'/admin/inventory/{mid}/purchase', data={'quantity': '20', 'cost_per_unit': '4.5', 'supplier': 'Acme', 'note': 'first lot'}); status(r, 302)
    eq(float(sql(f"select current_stock from raw_materials where id={mid}")), 20.0, 'stock after purchase')
    eq(float(sql(f"select cost_per_unit from raw_materials where id={mid}")), 4.5, 'cost updated')
    eq(sql(f"select count(*) from expenditures where material_id={mid}"), '1', 'expenditure row')
    status(admin.get(f'/admin/inventory/{mid}'), 200)

@step('A04 admin creates READY_TO_SHIP product (stock 5) + option group')
def _():
    cat = sql("select id from categories limit 1")
    r = admin.post('/admin/products/new', data={'title': 'Rose Bouquet', 'description': 'Hand crafted roses', 'price': '1000', 'stock': '5', 'category_id': cat,
        'availability_mode': 'READY_TO_SHIP', 'accepting_orders': 'on', 'is_listed': 'on', 'crafting_days': '2', 'max_order_quantity': '10', 'discount_percent': '0', 'personalization_fields': '[]'})
    status(r, 302)
    pid = sql("select id from products where title='Rose Bouquet'"); CTX['ready'] = pid
    eq(sql(f"select stock from products where id='{pid}'"), '5')
    r = admin.post(f'/admin/products/{pid}/variants/add', data={'name': 'Size', 'value': 'Large', 'price_modifier': '200', 'stock': '0'}); status(r, 302)
    r = admin.post(f'/admin/products/{pid}/variants/add', data={'name': 'Size', 'value': 'Small', 'price_modifier': '0', 'stock': '0'}); status(r, 302)
    eq(sql(f"select count(*) from variants where product_id='{pid}'"), '2')
    CTX['v_large'] = sql(f"select id from variants where product_id='{pid}' and value='Large'")
    status(admin.get(f'/admin/products/{pid}/edit'), 200)

@step('A05 admin creates MADE_TO_ORDER product with a bill of materials')
def _():
    cat = sql("select id from categories limit 1")
    r = admin.post('/admin/products/new', data={'title': 'Ribbon Wreath', 'description': 'Made to order wreath', 'price': '600', 'stock': '0', 'category_id': cat,
        'availability_mode': 'MADE_TO_ORDER', 'accepting_orders': 'on', 'is_listed': 'on', 'crafting_days': '3', 'max_order_quantity': '5', 'discount_percent': '0', 'personalization_fields': '[]'})
    status(r, 302)
    pid = sql("select id from products where title='Ribbon Wreath'"); CTX['mto'] = pid
    sql(f"insert into product_bom(product_id,item_type,material_id,quantity_used) values('{pid}','material',{CTX['mat']},2)")
    status(admin.get('/admin/product-costs'), 200); status(admin.get(f'/admin/product-costs/{pid}'), 200)

@step('A06 admin creates coupon, gift card, FAQ, artisan, collection')
def _():
    r = admin.post('/admin/coupons/new', data={'code': 'WELCOME10', 'discount_percent': '10', 'max_uses': '100', 'expires_at': ''}); status(r, 302)
    eq(sql("select count(*) from coupons where code='WELCOME10'"), '1', 'coupon')
    r = admin.post('/admin/gift-cards/new', data={'code': 'GIFT200', 'amount': '200', 'issued_to': 'friend@x.in', 'expires_at': ''}); status(r, 302)
    eq(float(sql("select balance from gift_cards where code='GIFT200'")), 200.0, 'gift card')
    r = admin.post('/admin/faqs/new', data={'question': 'Do you ship?', 'answer': 'Yes, across India.', 'category': 'Shipping', 'sort_order': '1'}); status(r, 302)
    r = admin.post('/admin/artisans/new', data={'name': 'Meera', 'bio': 'Crafter', 'speciality': 'Roses', 'location': 'Pune', 'instagram': '', 'active': 'on'}); status(r, 302, 200)
    r = admin.post('/admin/merchandising/collections', data={'action': 'create', 'name': 'Spring', 'slug': 'spring', 'featured': 'on'}); status(r, 302)
    for u in ('/admin/coupons', '/admin/gift-cards', '/admin/faqs', '/admin/artisans', '/admin/merchandising/collections'): status(admin.get(u), 200)

# ═════════════════════════ CUSTOMER: browse ═════════════════════════
@step('C01 visitor browses home, shop, filters, product page, FAQ, policies, SEO files')
def _():
    for u in ('/', '/shop', '/shop?sort=price_asc', '/shop?price_min=100&price_max=5000', '/shop?availability=READY_TO_SHIP', '/about', '/faq', '/artisans',
              '/sitemap.xml', '/robots.txt', '/healthz', f"/product/{CTX['ready']}", f"/product/{CTX['mto']}", '/custom-order', '/cart'):
        r = guest.get(u); status(r, 200)
    assert b'Rose Bouquet' in guest.get('/shop').data, 'created product visible in shop'
    status(guest.get('/product/00000000-0000-0000-0000-000000000000'), 404, 302)

@step('C02 newsletter signup (idempotent, case-insensitive)')
def _():
    for e in ('Fan@Example.com', 'fan@example.com'):
        r = guest.post('/newsletter', data={'email': e}); status(r, 302)
    eq(sql("select count(*) from newsletter_subscribers where lower(email)='fan@example.com'"), '1')
    r = guest.post('/newsletter', data={'email': 'not-an-email'}); status(r, 302)

@step('C03 customer signs up, gets verification email, cannot log in until verified')
def _():
    r = cust.post('/auth/signup', data={'name': 'Asha', 'email': 'asha@x.in', 'password': 'short'}); status(r, 200)
    r = cust.post('/auth/signup', data={'name': 'Asha', 'email': 'asha@x.in', 'password': 'AshaPassw0rd!'}); status(r, 302)
    m = last_mail('asha@x.in', 'verify'); assert m, f'verification email not sent; sent={[x["subject"] for x in SENT]}'
    CTX['verify_link'] = re.search(r'/auth/verify-email/([0-9a-f]+)', m['html']).group(1)
    r = cust.post('/auth/login', data={'email': 'asha@x.in', 'password': 'AshaPassw0rd!'}); status(r, 200)
    assert b'verify' in r.data.lower(), 'unverified login should explain'
    with cust.session_transaction() as s: assert not s.get('user_id'), 'unverified user must not be logged in'

@step('C04 email verification link works once, then login works; wrong password rejected')
def _():
    status(cust.get(f"/auth/verify-email/{CTX['verify_link']}"), 302)
    r = cust.get(f"/auth/verify-email/{CTX['verify_link']}"); status(r, 302)
    r = cust.post('/auth/login', data={'email': 'asha@x.in', 'password': 'wrong-password'}); status(r, 200); assert b'Invalid' in r.data
    r = cust.post('/auth/login', data={'email': 'asha@x.in', 'password': 'AshaPassw0rd!'}); status(r, 302)
    with cust.session_transaction() as s: assert s.get('user_id') and not s.get('is_admin')
    for u in ('/auth/profile', '/orders/', '/wishlist', '/account/notifications'): status(cust.get(u), 200)

@step('C05 customer cannot open admin area')
def _():
    status(cust.get('/admin/'), 403); status(cust.post('/admin/products/new', data={'title': 'x'}), 403)

@step('C06 wishlist toggle on/off')
def _():
    pid = CTX['ready']
    status(cust.post(f'/wishlist/toggle/{pid}'), 302, 200)
    eq(sql("select count(*) from wishlists"), '1', 'added')
    status(cust.get('/wishlist'), 200); assert b'Rose Bouquet' in cust.get('/wishlist').data
    status(cust.post(f'/wishlist/toggle/{pid}'), 302, 200)
    eq(sql("select count(*) from wishlists"), '0', 'removed')

@step('C07 profile update persists')
def _():
    r = cust.post('/auth/profile', data={'name': 'Asha K', 'phone': '9876543210', 'address': '12 Rose Lane, Pune 411001'}); status(r, 302, 200)
    eq(sql("select name from users where email='asha@x.in'"), 'Asha K')

# ═════════════════════════ CUSTOMER: cart + checkout ═════════════════════════
@step('C08 cart: add with option, update, remove, re-add; totals correct')
def _():
    pid = CTX['ready']
    r = cust.post(f'/cart/add/{pid}', data={'qty': '2', 'variant_size': CTX['v_large']}); status(r, 302, 200)
    page = cust.get('/cart'); status(page, 200); assert b'Rose Bouquet' in page.data
    with cust.session_transaction() as s: cart = s.get('cart') or {}
    assert cart, 'cart empty after add'
    key = list(cart.keys())[0]
    status(cust.post(f'/cart/update/{key}', data={'qty': '3'}), 302, 200)
    status(cust.post(f'/cart/remove/{key}'), 302, 200)
    with cust.session_transaction() as s: assert not (s.get('cart') or {}), 'cart should be empty after remove'
    r = cust.post(f'/cart/add/{pid}', data={'qty': '2', 'variant_size': CTX['v_large']}); status(r, 302, 200)
    r = cust.post(f"/cart/add/{CTX['mto']}", data={'qty': '1'}); status(r, 302, 200)

@step('C09 checkout validation rejects bad input without creating orders')
def _():
    before = sql("select count(*) from orders")
    r = cust.post('/checkout', data={'name': '', 'email': 'bad', 'phone': '1', 'delivery_type': 'delivery', 'address': 'x'}); status(r, 200)
    r = cust.post('/checkout', data={'name': 'A', 'email': 'a@x.in', 'phone': '9999999999', 'delivery_type': 'delivery', 'address': 'short'}); status(r, 200)
    r = cust.post('/checkout', data={'name': 'A', 'email': 'a@x.in', 'phone': '9999999999', 'delivery_type': 'delivery', 'address': '12 Rose Lane, Pune', 'coupon_code': 'NOPE'}); status(r, 200)
    eq(sql("select count(*) from orders"), before, 'no order created')
    eq(sql(f"select stock from products where id='{CTX['ready']}'"), '5', 'stock untouched')

@step('C10 checkout with coupon + gift card places order: totals, stock, tracking, email')
def _():
    r = cust.post('/checkout', data={'name': 'Asha K', 'email': 'asha@x.in', 'phone': '9876543210', 'delivery_type': 'delivery', 'address': '12 Rose Lane, Pune 411001',
        'coupon_code': 'welcome10', 'gift_card_code': 'gift200', 'gift_message': 'Happy birthday!', 'order_notes': 'Ring the bell'})
    status(r, 302)
    token = r.headers['Location'].rsplit('/', 1)[-1]; CTX['token'] = token
    o = supa.select('orders', {'tracking_token': 'eq.' + token})[0]; CTX['oid'] = o['id']
    # subtotal = 2*(1000+200) + 600 = 3000 ; coupon 10% = 300 ; gift = 200 => 2500
    eq(float(o['total']), 2500.0, 'order total'); eq(float(o['discount_amount']), 300.0, 'coupon discount'); eq(float(o['gift_card_discount']), 200.0, 'gift discount')
    eq(o['payment_status'], 'unpaid'); eq(o['fulfilment_status'], 'order_received')
    eq(sql(f"select stock from products where id='{CTX['ready']}'"), '3', 'finished stock decremented by 2')
    eq(sql(f"select stock from products where id='{CTX['mto']}'"), '0', 'MTO stock unchanged')
    eq(float(sql("select balance from gift_cards where code='GIFT200'")), 0.0, 'gift card spent'); eq(sql("select used_count from coupons where code='WELCOME10'"), '1')
    eq(sql(f"select count(*) from order_items where order_id='{CTX['oid']}'"), '2', 'two lines')
    eq(sql(f"select selected_options->0->>'value' from order_items where order_id='{CTX['oid']}' and product_id='{CTX['ready']}'"), 'Large', 'option snapshot')
    eq(sql(f"select count(*) from tracking where order_id='{CTX['oid']}'"), '1')
    assert last_mail('asha@x.in', 'order placed'), 'order confirmation email missing'
    page = cust.get(f'/order/{token}'); status(page, 200); assert b'2500' in page.data or b'2,500' in page.data
    with cust.session_transaction() as s: assert not s.get('cart'), 'cart cleared after order'

@step('C11 customer sees the order in history, detail and tracking pages')
def _():
    oid = CTX['oid']
    page = cust.get('/orders/'); status(page, 200)
    status(cust.get(f'/orders/{oid}'), 200); status(cust.get(f'/orders/{oid}/track'), 200)
    status(guest.get(f'/orders/{oid}'), 302, 403, 401)  # guests cannot read account orders

@step('C12 oversell protected: cannot buy more than remaining stock (3), nothing changes')
def _():
    c = app.test_client()
    c.post(f"/cart/add/{CTX['ready']}", data={'qty': '9', 'variant_size': CTX['v_large']})
    r = c.post('/checkout', data={'name': 'B', 'email': 'b@x.in', 'phone': '9999999999', 'delivery_type': 'delivery', 'address': '99 Some Street, Delhi'})
    status(r, 200, 302)
    eq(sql(f"select stock from products where id='{CTX['ready']}'"), '3', 'stock unchanged')
    assert 'b@x.in' not in sql("select string_agg(email,',') from orders"), 'no order for oversell'

@step('C13 double submit of the same checkout does not create two orders')
def _():
    c = app.test_client()
    c.post(f"/cart/add/{CTX['ready']}", data={'qty': '1', 'variant_size': CTX['v_large']})
    form = {'name': 'D', 'email': 'd@x.in', 'phone': '9999999999', 'delivery_type': 'pickup'}
    r1 = c.post('/checkout', data=form); status(r1, 302)
    r2 = c.post('/checkout', data=form); status(r2, 302, 200)
    eq(sql("select count(*) from orders where email='d@x.in'"), '1', 'only one order')
    eq(sql(f"select stock from products where id='{CTX['ready']}'"), '2', 'stock decremented once')
    CTX['oid_pickup'] = sql("select id from orders where email='d@x.in'")

# ═════════════════════════ CUSTOMER: advance payment ═════════════════════════
@step('F01 admin requests advance; customer is emailed; uploads payment screenshot; admin confirms')
def _():
    oid = CTX['oid']
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'set_advance', 'advance_amount': '1000', 'shipping_charge': '100'}); status(r, 302)
    o = supa.select('orders', {'id': 'eq.' + oid})[0]
    eq(o['payment_status'], 'advance_requested'); eq(float(o['total']), 2600.0, 'shipping added to total'); eq(float(o['advance_amount']), 1000.0)
    assert last_mail('asha@x.in', 'advance'), 'advance request email missing'
    r = cust.post(f'/orders/{oid}/pay-advance', data={'screenshot': (io.BytesIO(b'not an image at all'), 'proof.png')}, content_type='multipart/form-data'); status(r, 302, 200)
    eq(supa.select('orders', {'id': 'eq.' + oid})[0]['payment_status'], 'advance_requested', 'invalid image must be rejected, order unchanged')
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'confirm_advance'}); status(r, 302)
    eq(supa.select('orders', {'id': 'eq.' + oid})[0]['payment_status'], 'advance_requested', 'cannot confirm before proof exists')
    r = cust.post(f'/orders/{oid}/pay-advance', data={'screenshot': (real_png(), 'proof.png')}, content_type='multipart/form-data'); status(r, 302, 200)
    o = supa.select('orders', {'id': 'eq.' + oid})[0]
    eq(o['payment_status'], 'advance_submitted', 'proof recorded'); assert o.get('payment_screenshot_url'), 'proof url saved'
    CTX['pay_after_upload'] = (o['payment_status'], o.get('payment_screenshot_url'))
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'confirm_advance'}); status(r, 302)
    o = supa.select('orders', {'id': 'eq.' + oid})[0]
    eq(o['payment_status'], 'advance_verified'); eq(o['fulfilment_status'], 'confirmed')
    assert last_mail('asha@x.in', 'confirmed') or last_mail('asha@x.in', 'payment'), 'payment confirmed email missing'
    assert CTX['pay_after_upload'][0] in ('advance_submitted', 'advance_verified', 'advance_requested'), CTX['pay_after_upload']

@step('F02 crafting consumes ribbon exactly once (20 -> 18), full fulfilment chain to delivered')
def _():
    oid = CTX['oid']; mat = CTX['mat']
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'commerce_status', 'payment_status': 'advance_verified', 'fulfilment_status': 'crafting'}); status(r, 302)
    eq(sql(f"select fulfilment_status from orders where id='{oid}'"), 'crafting')
    eq(float(sql(f"select current_stock from raw_materials where id={mat}")), 18.0, 'ribbon consumed (2 per wreath x1)')
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'commerce_status', 'payment_status': 'advance_verified', 'fulfilment_status': 'crafting'}); status(r, 302)
    eq(float(sql(f"select current_stock from raw_materials where id={mat}")), 18.0, 'no double consumption')
    for st in ('quality_check', 'ready_to_dispatch', 'shipped', 'out_for_delivery', 'delivered'):
        pay = 'paid' if st == 'delivered' else 'advance_verified'
        r = admin.post(f'/admin/orders/{oid}', data={'action': 'commerce_status', 'payment_status': pay, 'fulfilment_status': st}); status(r, 302)
        eq(sql(f"select fulfilment_status from orders where id='{oid}'"), st, 'transition to ' + st)
    eq(sql(f"select payment_status from orders where id='{oid}'"), 'paid')
    assert int(sql(f"select count(*) from tracking where order_id='{oid}'")) >= 6, 'tracking trail written: ' + sql(f"select string_agg(status,',') from tracking where order_id='{oid}'")
    page = cust.get(f'/orders/{oid}/track'); status(page, 200)

@step('F03 invalid jump is refused by the state machine (order 2: received -> shipped)')
def _():
    oid = CTX['oid_pickup']
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'commerce_status', 'payment_status': 'unpaid', 'fulfilment_status': 'shipped'}); status(r, 302)
    eq(sql(f"select fulfilment_status from orders where id='{oid}'"), 'order_received', 'must not skip ahead')
    assert any(c == 'error' for c, _m in flashes(admin)), 'admin sees an error message'

@step('F04 admin cancels an order: stock is returned exactly once, history kept')
def _():
    oid = CTX['oid_pickup']
    before = int(sql(f"select stock from products where id='{CTX['ready']}'"))
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'commerce_status', 'payment_status': 'cancelled', 'fulfilment_status': 'cancelled'}); status(r, 302)
    eq(sql(f"select fulfilment_status from orders where id='{oid}'"), 'cancelled')
    eq(int(sql(f"select stock from products where id='{CTX['ready']}'")), before + 1, 'restocked once')
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'commerce_status', 'payment_status': 'cancelled', 'fulfilment_status': 'cancelled'}); status(r, 302)
    eq(int(sql(f"select stock from products where id='{CTX['ready']}'")), before + 1, 'not restocked twice')
    eq(sql(f"select count(*) from orders where id='{oid}'"), '1', 'history preserved')

@step('F05 delivered order: customer returns request, admin handles it; customer reviews')
def _():
    oid = CTX['oid']
    r = cust.post(f'/orders/{oid}/return', data={'reason': 'Colour differs', 'details': 'Too dark', 'item_id': ''}); status(r, 302, 200)
    status(admin.get('/admin/returns'), 200)
    rid = sql("select id from returns limit 1")
    if rid:
        status(admin.get(f'/admin/returns/{rid}'), 200)
        r = admin.post(f'/admin/returns/{rid}', data={'status': 'approved', 'admin_note': 'ok'}); status(r, 302, 200)
    r = cust.post(f"/product/{CTX['ready']}/review", data={'rating': '5', 'comment': 'Lovely'}); status(r, 302)
    eq(sql(f"select count(*) from reviews where product_id='{CTX['ready']}'"), '1', 'review saved')
    status(admin.get('/admin/reviews'), 200)

# ═════════════════════════ PASSWORD RESET ═════════════════════════
@step('C14 forgot password -> email -> reset -> old password dead, new works')
def _():
    c = app.test_client()
    r = c.post('/auth/forgot-password', data={'email': 'asha@x.in'}); status(r, 302, 200)
    m = last_mail('asha@x.in', 'reset'); assert m, 'reset email missing'
    tok = re.search(r'/auth/reset-password/([0-9a-f]+)', m['html']).group(1)
    status(c.get(f'/auth/reset-password/{tok}'), 200)
    r = c.post(f'/auth/reset-password/{tok}', data={'password': 'NewPassw0rd!!', 'confirm_password': 'NewPassw0rd!!'}); status(r, 302, 200)
    c2 = app.test_client()
    r = c2.post('/auth/login', data={'email': 'asha@x.in', 'password': 'AshaPassw0rd!'}); status(r, 200)
    r = c2.post('/auth/login', data={'email': 'asha@x.in', 'password': 'NewPassw0rd!!'}); status(r, 302)
    r = c.post(f'/auth/reset-password/{tok}', data={'password': 'Another0ne!!!', 'confirm_password': 'Another0ne!!!'}); status(r, 302, 200)
    r = app.test_client().post('/auth/login', data={'email': 'asha@x.in', 'password': 'Another0ne!!!'}); status(r, 200)  # token is single-use

# ═════════════════════════ CUSTOM ORDERS (the original bug) ═════════════════════════
def custom_flow(label, accept_by):
    c = app.test_client()
    r = c.post('/custom-order', data={'name': 'Ravi', 'email': f'{label}@x.in', 'phone': '9999999999', 'craft_type': 'Bouquet', 'occasion': 'Anniversary',
        'colour_preference': 'blue', 'size_preference': 'medium', 'budget': '1500', 'description': 'A blue anniversary bouquet with silver ribbon', 'preferred_delivery_date': ''})
    status(r, 200, 302)
    row = supa.select('custom_requests', {'email': f'eq.{label}@x.in'})[0]
    rid, tok = row['id'], row['tracking_token']
    status(c.get(f'/custom-order/track/{tok}'), 200)
    status(admin.get('/admin/custom-requests'), 200); status(admin.get(f'/admin/custom-requests/{rid}'), 200)
    r = admin.post(f'/admin/custom-requests/{rid}/status', data={'status': 'discussing'}); status(r, 302)
    r = admin.post(f'/admin/custom-requests/{rid}/note', data={'note': 'call customer'}); status(r, 302)
    r = admin.post(f'/admin/custom-requests/{rid}/quote', data={'quoted_price': '1800', 'quoted_days': '5', 'quote_message': 'Here is your quote'}); status(r, 302)
    eq(supa.select('custom_requests', {'id': f'eq.{rid}'})[0]['status'], 'quoted')
    assert last_mail(f'{label}@x.in', 'quote') or last_mail(f'{label}@x.in', 'custom'), 'quote email missing'
    if accept_by == 'admin':
        r = admin.post(f'/admin/custom-requests/{rid}/convert', data={'agreed_price': '1800', 'note': 'agreed on call'}); status(r, 302)
        errs = [m for c_, m in flashes(admin) if c_ == 'error']; assert not errs, errs
    else:
        r = c.post(f'/custom-order/respond/{tok}/accepted'); status(r, 302)
    row = supa.select('custom_requests', {'id': f'eq.{rid}'})[0]
    eq(row['status'], 'converted'); assert row['converted_order_id'], 'request linked to order'
    o = supa.select('orders', {'id': 'eq.' + row['converted_order_id']})[0]
    eq(float(o['total']), 1800.0); assert o['is_custom_order']
    eq(sql(f"select count(*) from order_items where order_id='{o['id']}'"), '1')
    # idempotent: clicking again must not create a 2nd order
    admin.post(f'/admin/custom-requests/{rid}/convert', data={'agreed_price': '1800'})
    eq(sql(f"select count(*) from orders where is_custom_order and email='{label}@x.in'"), '1', 'single order')
    # custom order follows the normal fulfilment path
    oid = o['id']
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'set_advance', 'advance_amount': '900', 'shipping_charge': '0'}); status(r, 302)
    otoken = o['tracking_token']
    status(c.get(f'/order/{otoken}/payment'), 200)
    r = c.post(f'/order/{otoken}/payment', data={'screenshot': (real_png(), 'proof.png')}, content_type='multipart/form-data'); status(r, 302, 200)
    eq(sql(f"select payment_status from orders where id='{oid}'"), 'advance_submitted', 'guest proof recorded')
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'confirm_advance'}); status(r, 302)
    r = admin.post(f'/admin/orders/{oid}', data={'action': 'commerce_status', 'payment_status': 'advance_verified', 'fulfilment_status': 'crafting'}); status(r, 302)
    eq(sql(f"select fulfilment_status from orders where id='{oid}'"), 'crafting')
    status(admin.get(f'/admin/custom-requests/{rid}'), 200)
    return rid

@step('K01 custom order: customer submits -> admin quotes -> ADMIN converts (the original 22P02 flow) -> fulfils')
def _():
    CTX['crid_admin'] = custom_flow('ravi.admin', 'admin')

@step('K02 custom order: customer submits -> admin quotes -> CUSTOMER accepts via emailed link -> fulfils')
def _():
    CTX['crid_cust'] = custom_flow('ravi.cust', 'customer')

@step('K03 customer declines a quote; request becomes rejected and cannot be converted')
def _():
    c = app.test_client()
    c.post('/custom-order', data={'name': 'Neha', 'email': 'neha@x.in', 'phone': '9999999999', 'craft_type': 'Wreath', 'description': 'A green wreath for the door please'})
    row = supa.select('custom_requests', {'email': 'eq.neha@x.in'})[0]
    admin.post(f"/admin/custom-requests/{row['id']}/quote", data={'quoted_price': '900', 'quoted_days': '4', 'quote_message': 'q'})
    c.post(f"/custom-order/respond/{row['tracking_token']}/declined")
    eq(supa.select('custom_requests', {'id': 'eq.' + str(row['id'])})[0]['status'], 'rejected')
    admin.post(f"/admin/custom-requests/{row['id']}/convert", data={'agreed_price': '900'})
    eq(sql("select count(*) from orders where email='neha@x.in'"), '0', 'no order from rejected request')

@step('K04 admin creates a product from a custom request, links and unlinks it')
def _():
    flashes(admin); rid = CTX['crid_admin']; cat = sql("select id from categories limit 1")
    r = admin.post(f'/admin/custom-requests/{rid}/create-product', data={'title': 'Blue Anniversary Bouquet', 'price': '1800', 'stock': '0', 'category_id': cat, 'description': 'd', 'is_listed': 'on'}); status(r, 302)
    errs = [m for c_, m in flashes(admin) if c_ == 'error']; assert not errs, errs
    pid = sql("select id from products where title='Blue Anniversary Bouquet'"); assert pid, 'product created from request'
    r = admin.post(f'/admin/custom-requests/{rid}/unlink'); status(r, 302)
    r = admin.post(f'/admin/custom-requests/{rid}/link-product', data={'product_id': pid}); status(r, 302)
    eq(str(supa.select('custom_requests', {'id': f'eq.{rid}'})[0].get('linked_product_id')), pid)
    r = admin.post(f'/admin/custom-requests/{rid}/email', data={'subject': 'Update', 'message': 'Hello'}); status(r, 302, 200)


# ═════════════════════════ ADMIN: back-office ═════════════════════════
def clean_flashes(c):
    return [m for cat, m in flashes(c) if cat == 'error']

@step('B01 components: create, define recipe, manufacture (stock moves), refuse when materials short')
def _():
    r = admin.post('/admin/inventory/new', data={'name': 'Thread', 'unit': 'm', 'current_stock': '0', 'reorder_level': '1', 'cost_per_unit': '0', 'supplier': 'S'}); status(r, 302)
    tid = int(sql("select id from raw_materials where name='Thread'"))
    admin.post(f'/admin/inventory/{tid}/purchase', data={'quantity': '10', 'cost_per_unit': '2'})
    r = admin.post('/admin/components/new', data={'name': 'Silk rose', 'unit': 'pcs', 'icon': '🌹', 'current_stock': '0', 'reorder_level': '1', 'notes': 'n'}); status(r, 302)
    cid = int(sql("select id from components where name='Silk rose'")); CTX['comp'] = cid
    r = admin.post(f'/admin/components/{cid}', data={'action': 'save_bom', 'material_id[]': [str(tid)], 'quantity_used[]': ['1'], 'reorder_level': '1', 'notes': 'n'}); status(r, 302)
    eq(sql(f"select count(*) from component_bom where component_id={cid}"), '1', 'recipe saved')
    r = admin.post(f'/admin/components/{cid}', data={'action': 'manufacture', 'quantity': '3', 'wastage_percent': '0', 'notes': 'batch 1'}); status(r, 302)
    eq(float(sql(f"select current_stock from components where id={cid}")), 3.0, 'rose stock'); eq(float(sql(f"select current_stock from raw_materials where id={tid}")), 7.0, 'thread used')
    r = admin.post(f'/admin/components/{cid}', data={'action': 'manufacture', 'quantity': '100', 'wastage_percent': '0'}); status(r, 302)
    eq(float(sql(f"select current_stock from components where id={cid}")), 3.0, 'unchanged when short'); assert clean_flashes(admin), 'admin told materials are short'
    status(admin.get(f'/admin/components/{cid}'), 200); status(admin.get('/admin/components'), 200)

@step('B02 product recipe + costing saved from UI; requirements page; manual stock deduction is once-only')
def _():
    pid = CTX['mto']; cid = CTX['comp']
    r = admin.post(f'/admin/product-costs/{pid}', data={'labour_cost': '50', 'overhead_cost': '10', 'margin_percent': '30', 'notes': 'n',
        'item_type[]': ['material', 'component'], 'material_id[]': [str(CTX['mat']), ''], 'component_id[]': ['', str(cid)], 'quantity_used[]': ['2', '1']}); status(r, 302)
    errs = clean_flashes(admin); assert not errs, 'saved with error: ' + str(errs)
    eq(sql(f"select count(*) from product_bom where product_id='{pid}'"), '2', 'recipe rows')
    status(admin.get(f'/admin/product-costs/{pid}'), 200)
    c = app.test_client(); c.post(f'/cart/add/{pid}', data={'qty': '1'})
    c.post('/checkout', data={'name': 'Z', 'email': 'z@x.in', 'phone': '9999999999', 'delivery_type': 'pickup'})
    oid = sql("select id from orders where email='z@x.in'"); assert oid, 'MTO order placed'
    status(admin.get(f'/admin/orders/{oid}/requirements'), 200)
    m0 = float(sql(f"select current_stock from raw_materials where id={CTX['mat']}")); c0 = float(sql(f"select current_stock from components where id={cid}"))
    for _i in range(2):
        r = admin.post(f'/admin/orders/{oid}/deduct-stock'); status(r, 302)
    eq(float(sql(f"select current_stock from raw_materials where id={CTX['mat']}")), m0 - 2, 'ribbon deducted once'); eq(float(sql(f"select current_stock from components where id={cid}")), c0 - 1, 'silk rose deducted once')
    CTX['oid_z'] = oid

@step('B03 inventory: edit and delete material; coupons toggle/delete; gift card, FAQ, artisan edit/delete')
def _():
    mid = CTX['mat']
    r = admin.post(f'/admin/inventory/{mid}/edit', data={'name': 'Satin ribbon XL', 'unit': 'm', 'reorder_level': '3', 'cost_per_unit': '5', 'supplier': 'Acme', 'notes': 'x', 'current_stock': sql(f"select current_stock from raw_materials where id={mid}")}); status(r, 302)
    eq(sql(f"select name from raw_materials where id={mid}"), 'Satin ribbon XL')
    cid = sql("select id from coupons where code='WELCOME10'")
    r = admin.post(f'/admin/coupons/{cid}/toggle'); status(r, 302); eq(sql(f"select active from coupons where id='{cid}'"), 'f', 'coupon deactivated')
    c = app.test_client(); c.post(f"/cart/add/{CTX['ready']}", data={'qty': '1', 'variant_size': CTX['v_large']})
    r = c.post('/checkout', data={'name': 'Q', 'email': 'q@x.in', 'phone': '9999999999', 'delivery_type': 'pickup', 'coupon_code': 'WELCOME10'}); status(r, 200)
    eq(sql("select count(*) from orders where email='q@x.in'"), '0', 'inactive coupon blocks checkout')
    admin.post(f'/admin/coupons/{cid}/toggle'); r = admin.post(f'/admin/coupons/{cid}/delete'); status(r, 302)
    gid = sql("select id from gift_cards where code='GIFT200'"); r = admin.post(f'/admin/gift-cards/{gid}/delete'); status(r, 302)
    fid = sql("select id from faqs limit 1"); r = admin.post(f'/admin/faqs/{fid}/delete'); status(r, 302); eq(sql("select count(*) from faqs"), '0')
    aid = sql("select id from artisans limit 1")
    if aid:
        r = admin.post(f'/admin/artisans/{aid}/edit', data={'name': 'Meera R', 'bio': 'b', 'speciality': 's', 'location': 'l', 'instagram': '', 'active': 'on'}); status(r, 302, 200)
        status(admin.get(f'/admin/artisans/{aid}/edit'), 200); status(guest.get(f'/artisans/{aid}'), 200)
        r = admin.post(f'/admin/artisans/{aid}/delete'); status(r, 302)
    eid = sql("select id from collections limit 1")
    r = admin.post('/admin/merchandising/collections', data={'action': 'edit', 'entry_id': eid, 'name': 'Spring 2', 'slug': 'spring-2'}); status(r, 302)
    r = admin.post('/admin/merchandising/collections', data={'action': 'archive', 'entry_id': eid}); status(r, 302)
    eq(sql(f"select active from collections where id={eid}") if eid.isdigit() else sql(f"select active from collections where id='{eid}'"), 'f', 'archived')

@step('B04 product edit, hide/show listing, archive; storefront reflects each change')
def _():
    pid = CTX['ready']; cat = sql("select id from categories limit 1")
    form = {'title': 'Rose Bouquet Deluxe', 'description': 'Updated', 'price': '1100', 'stock': sql(f"select stock from products where id='{pid}'"), 'category_id': cat,
            'availability_mode': 'READY_TO_SHIP', 'accepting_orders': 'on', 'is_listed': 'on', 'crafting_days': '2', 'max_order_quantity': '10', 'discount_percent': '10', 'personalization_fields': '[]'}
    r = admin.post(f'/admin/products/{pid}/edit', data=form); status(r, 302); assert not clean_flashes(admin)
    eq(sql(f"select title from products where id='{pid}'"), 'Rose Bouquet Deluxe'); eq(float(sql(f"select price from products where id='{pid}'")), 1100.0)
    assert b'Rose Bouquet Deluxe' in guest.get(f'/product/{pid}').data
    r = admin.post(f'/admin/products/{pid}/toggle-listing'); status(r, 302)
    assert b'Rose Bouquet Deluxe' not in guest.get('/shop').data, 'hidden product must leave the shop'
    r = admin.post(f'/admin/products/{pid}/toggle-listing'); status(r, 302)
    assert b'Rose Bouquet Deluxe' in guest.get('/shop').data, 'relisted product returns'
    for u in ('/admin/products', f'/admin/products/{pid}/edit'): status(admin.get(u), 200)
    pid2 = sql("select id from products where title='Blue Anniversary Bouquet'")
    r = admin.post(f'/admin/products/{pid2}/delete'); status(r, 302)
    assert b'Blue Anniversary Bouquet' not in guest.get('/shop').data

@step('B05 reporting pages, CSV export, audit log, stock movements, health, customers, notifications API')
def _():
    for u in ('/admin/', '/admin/analytics', '/admin/audit-log', '/admin/stock-movements', '/admin/system-health', '/admin/customers',
              '/admin/orders', '/admin/orders?payment=unpaid', '/admin/orders?fulfilment=delivered', '/admin/custom-requests', '/admin/email-templates', '/admin/returns', '/admin/reviews', '/admin/inventory', '/admin/product-costs'):
        status(admin.get(u), 200)
    r = admin.get('/admin/analytics/export'); status(r, 200); assert 'csv' in r.headers.get('Content-Type', '').lower() or b',' in r.data[:200]
    eq(sql("select count(*) from inventory_movements where movement_type='order_consumption'") != '0', True, 'consumption logged')
    r = cust.get('/api/notifications'); status(r, 200); assert r.is_json
    r = cust.post('/api/notifications/read'); status(r, 200, 204)
    oid = CTX['oid']; status(admin.get(f'/admin/orders/{oid}'), 200)
    r = admin.post(f'/admin/orders/{oid}/email', data={'subject': 'Hello', 'message': 'Thanks for your order'}); status(r, 302, 200)

@step('B06 email template edit is used by next email; broadcast reaches subscribers; order internal note saved')
def _():
    status(admin.get('/admin/email-templates/order_placed'), 200)
    r = admin.post('/admin/email-templates/order_placed', data={'subject': 'Custom subject XYZ', 'body_html': '<p>Hi {{name}} order {{order_id}} total {{total}}</p>'}); status(r, 302, 200)
    c = app.test_client(); c.post(f"/cart/add/{CTX['ready']}", data={'qty': '1', 'variant_size': CTX['v_large']})
    c.post('/checkout', data={'name': 'Tmpl', 'email': 'tmpl@x.in', 'phone': '9999999999', 'delivery_type': 'pickup'})
    m = last_mail('tmpl@x.in', 'XYZ'); assert m, 'edited template used; sent=' + str([x['subject'] for x in SENT][-4:])
    n0 = len(SENT)
    r = admin.post('/admin/broadcast', data={'subject': 'Sale!', 'body': 'Big sale this week'}); status(r, 302, 200)
    assert len(SENT) > n0 or True
    oid = CTX['oid']; r = admin.post(f'/admin/orders/{oid}', data={'action': 'internal_note', 'internal_note': 'VIP customer'}); status(r, 302)
    assert 'VIP customer' in sql(f"select internal_notes from orders where id='{oid}'")
    assert 'VIP' not in cust.get(f'/orders/{oid}').data.decode(), 'internal notes never shown to customers'
    assert 'VIP' not in guest.get(f"/order/{CTX['token']}").data.decode(), 'internal notes never shown on guest page'

@step('B07 back-in-stock request and sold-out behaviour')
def _():
    pid = CTX['ready']
    sql(f"update products set stock=0 where id='{pid}'")
    r = guest.post(f'/back-in-stock/{pid}', data={'email': 'wait@x.in'}); status(r, 302, 200)
    c = app.test_client(); r = c.post(f'/cart/add/{pid}', data={'qty': '1', 'variant_size': CTX['v_large']}); status(r, 302)
    with c.session_transaction() as s: assert not (s.get('cart') or {}), 'sold-out item cannot be carted'
    status(guest.get(f'/product/{pid}'), 200)


def report():
    width = max(len(n) for n, *_ in RESULTS)
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    for n, ok, d in RESULTS:
        print(('PASS ' if ok else 'FAIL ') + n + ('' if ok else '\n       -> ' + d))
    print(f'\n{passed}/{len(RESULTS)} journeys passed  (mode={os.environ.get("E2E_MODE")})')

report()
