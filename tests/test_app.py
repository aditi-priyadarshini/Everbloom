import pytest
from app import create_app
import models,supa
from services.cart import normalize,resolve

@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(supa,'select',lambda *a,**k:[])
    monkeypatch.setattr(supa,'insert',lambda *a,**k:{'id':'test'})
    app=create_app(); app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,RATELIMIT_ENABLED=False)
    return app

def test_admin_guard(app):
    response=app.test_client().get('/admin/')
    assert response.status_code==403

def test_account_guard(app):
    assert app.test_client().get('/orders/').status_code==302

def test_csrf(app):
    app.config['WTF_CSRF_ENABLED']=True
    assert app.test_client().post('/cart/add/p').status_code==400

@pytest.mark.parametrize('url',['/','/shop','/cart','/auth/login','/auth/signup','/about','/faq','/custom-order','/policies/privacy','/does-not-exist'])
def test_public_pages(app,url):
    response=app.test_client().get(url)
    assert response.status_code==(404 if url=='/does-not-exist' else 200)
    assert b'Traceback' not in response.data

def test_safe_next(app):
    from routes.auth import safe_next
    with app.test_request_context():
        assert safe_next('https://evil.example')=='/'
        assert safe_next('//evil.example')=='/'
        assert safe_next('/orders/')=='/orders/'

def test_review_eligibility(monkeypatch):
    monkeypatch.setattr(models,'get_orders',lambda **k:[{'id':'o','status':'delivered'}])
    monkeypatch.setattr(models,'get_order_items',lambda oid:[{'product_id':'p'}])
    assert models.review_eligible('p','u')
    assert not models.review_eligible('other','u')

def test_legacy_cart_and_variants(monkeypatch):
    from services.commerce import line_key
    assert normalize({'p':2})[line_key('p')]['qty']==2
    monkeypatch.setattr(models,'get_product',lambda pid:{'id':pid,'price':100,'stock':5})
    monkeypatch.setattr(models,'get_variants',lambda pid:[{'id':1,'price_modifier':25,'name':'Size','value':'Grand'}])
    items=resolve({'key':{'product_id':'p','qty':2,'variant_ids':['1'],'personalization':{'name':'A'}}})
    assert items[0]['subtotal']==250
    assert items[0]['personalization']['name']=='A'

def test_production_uses_rpc(monkeypatch):
    calls=[]
    monkeypatch.setattr(supa,'rpc',lambda name,args:calls.append((name,args)) or True)
    assert models.deduct_order_materials('o')
    assert calls==[('consume_order_inventory',{'p_order_id':'o'})]
    assert models.delete_order('o')
    assert calls[-1][0]=='cancel_commerce_order'

def test_custom_conversion_is_repeat_safe(monkeypatch):
    monkeypatch.setattr(models,'get_custom_request',lambda rid:{'converted_order_id':'o'})
    monkeypatch.setattr(models,'get_order',lambda oid:{'id':oid})
    assert models.convert_custom_to_order('r',100)==({'id':'o'},None)

def test_templates_compile(app):
    from pathlib import Path
    for file in Path('templates').rglob('*.html'):
        app.jinja_env.get_template(str(file.relative_to('templates')))

@pytest.mark.parametrize('url',['/admin/','/admin/orders','/admin/products','/admin/products/new','/admin/customers','/admin/coupons','/admin/custom-requests','/admin/settings','/admin/analytics','/admin/gift-cards','/admin/returns','/admin/artisans','/admin/artisans/new','/admin/faqs','/admin/broadcast','/admin/components','/admin/inventory','/admin/product-costs','/admin/reviews','/admin/stock-movements','/admin/audit-log','/admin/merchandising/collections'])
def test_admin_page_render(app,monkeypatch,url):
    monkeypatch.setattr(models,'get_user_by_id',lambda uid:{'id':uid,'is_admin':True})
    client=app.test_client()
    with client.session_transaction() as session:
        session['user_id']='admin';session['is_admin']=True
    response=client.get(url)
    assert response.status_code==200, response.data.decode()[:1000]

def test_product_cart_checkout_options(app,monkeypatch):
    product={'id':'p','title':'Bouquet','price':100,'stock':0,'availability_mode':'MADE_TO_ORDER','is_listed':True,'images':[],'crafting_days':3,'personalization_fields':[{'name':'recipient','label':'Recipient','required':True}]}
    monkeypatch.setattr(models,'get_product',lambda pid:product)
    monkeypatch.setattr(models,'get_variants',lambda pid:[{'id':1,'name':'Size','value':'Grand','price_modifier':50}])
    client=app.test_client()
    assert client.get('/product/p').status_code==200
    assert client.post('/cart/add/p',data={'qty':2,'variant_size':'1','personalization_recipient':'Ada'}).status_code==302
    response=client.get('/cart')
    assert response.status_code==200 and b'Ada' in response.data and b'Grand' in response.data
    assert client.get('/checkout').status_code==200
    captured=[]
    monkeypatch.setattr(supa,'rpc',lambda name,args:captured.append((name,args)) or {'id':'o','tracking_token':'private'})
    import emails
    monkeypatch.setattr(emails,'send_order_placed',lambda *a:True)
    response=client.post('/checkout',data={'name':'Ada','email':'ada@example.com','phone':'9876543210','address':'A complete test address','delivery_type':'delivery'})
    assert response.status_code==302 and response.location.endswith('/order/private')
    line=captured[0][1]['p_lines'][0]
    assert line['variant_ids']==['1'] and line['personalization']=={'recipient':'Ada'} and line['quantity']==2
    assert 'price' not in line

def test_impossible_delivery_date_rejected(app,monkeypatch):
    monkeypatch.setattr(models,'get_product',lambda pid:{'id':pid,'title':'Made','price':100,'stock':0,'allow_preorder':True,'crafting_days':7})
    client=app.test_client()
    with client.session_transaction() as session: session['cart']={'p':1}
    response=client.post('/checkout',data={'name':'Test','email':'test@example.com','phone':'9876543210','address':'Complete test address','delivery_type':'delivery','preferred_delivery_date':'2000-01-01'})
    assert response.status_code==200 and b'Choose a date' in response.data

def test_unavailable_cart_line_can_be_removed(app,monkeypatch):
    monkeypatch.setattr(models,'get_product',lambda pid:None)
    client=app.test_client()
    with client.session_transaction() as session:session['cart']={'p':1}
    response=client.get('/cart')
    assert b'Unavailable creation' in response.data and b'cart/remove/' in response.data
