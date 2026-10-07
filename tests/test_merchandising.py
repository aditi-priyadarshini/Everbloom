"""Publication and merchandising regressions; no external database access."""
import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict
import models
import supa


@pytest.fixture
def catalogue(monkeypatch):
    tables = {
        'categories': [{'id': 1, 'name': 'Live'}, {'id': 2, 'name': 'Empty'},
                       {'id': 3, 'name': 'Draft only'}, {'id': 4, 'name': 'Inactive', 'active': False}],
        'products': [{'id': 'live', 'title': 'Live creation', 'category_id': 1, 'price': 100,
                      'is_listed': True, 'availability_mode': 'MADE_TO_ORDER', 'stock': 0,
                      'created_at': '2025-01-01'},
                     {'id': 'draft', 'category_id': 3, 'price': 100, 'availability_mode': 'DRAFT'},
                     {'id': 'hidden', 'category_id': 2, 'price': 100, 'is_listed': False},
                     {'id': 'inactive', 'category_id': 4, 'price': 100, 'is_listed': True}],
        'collections': [{'id': 1, 'name': 'Populated'}, {'id': 2, 'name': 'Empty collection'},
                        {'id': 3, 'name': 'Archived collection', 'active': False}],
        'occasions': [{'id': 1, 'name': 'Used'}, {'id': 2, 'name': 'Unused'}],
        'collection_products': [{'collection_id': 1, 'product_id': 'live'},
                                {'collection_id': 2, 'product_id': 'draft'},
                                {'collection_id': 3, 'product_id': 'live'}],
        'product_occasions': [{'occasion_id': 1, 'product_id': 'live'}],
    }
    calls = []
    def select(table, filters=None, **kwargs):
        calls.append(table)
        rows = tables.get(table, [])
        for key, value in (filters or {}).items():
            if value == 'eq.true': rows = [row for row in rows if row.get(key, True)]
        return rows
    monkeypatch.setattr(supa, 'select', select)
    return tables, calls


def test_public_visibility_and_request_cache(catalogue):
    _, calls = catalogue
    with Flask(__name__).test_request_context():
        public = models.get_public_merchandising()
        assert [c['id'] for c in public['categories']] == [1]
        assert [c['id'] for c in public['collections']] == [1]
        assert [c['id'] for c in public['occasions']] == [1]
        assert len(calls) == 6
        assert models.get_public_merchandising() is public
        assert len(calls) == 6


def test_admin_counts_include_unpublished(catalogue):
    categories = models.merchandising_counts('categories')
    counts = {c['id']: (c['product_count'], c['live_count'], c['storefront_visible']) for c in categories}
    assert counts[1] == (1, 1, True)
    assert counts[2] == (1, 0, False)
    assert counts[3] == (1, 0, False)
    assert counts[4] == (1, 1, False)


def test_newest_explicitly_orders_dates(catalogue, monkeypatch):
    from app import create_app
    tables, _ = catalogue
    tables['products'].insert(0, dict(tables['products'][0], id='new', title='Newest creation', created_at='2026-09-01'))
    # Force reverse input order to verify route sorting rather than database defaults.
    tables['products'].reverse()
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, RATELIMIT_ENABLED=False)
    response = app.test_client().get('/shop?sort=newest')
    assert response.status_code == 200
    assert response.data.index(b'Newest creation') < response.data.index(b'Live creation')
    assert b'Empty collection' not in response.data
    assert b'Draft only' not in response.data
    assert b'Unused' not in response.data


def test_image_order_preserves_urls_and_removals():
    from routes.admin import _parse_product_form
    app = Flask(__name__)
    with app.test_request_context(method='POST', data=MultiDict([
        ('title', 'Creation'), ('price', '100'), ('image_order', '2'),
        ('image_order', '0'), ('image_order', '1'), ('remove_image', '0')])):
        from flask import request
        parsed=_parse_product_form(request, {'images': ['a', 'b', 'c'], 'image_alt_texts':['First','Second','Third']})
        assert parsed['images'] == ['c', 'b']
        assert parsed['image_alt_texts'] == ['Third','Second']
    with app.test_request_context(method='POST', data=MultiDict([
        ('title', 'Creation'), ('price', '100'), ('image_order', '0'), ('image_order', '0')])):
        from flask import request
        with pytest.raises(ValueError, match='Invalid image order'):
            _parse_product_form(request, {'images': ['a', 'b']})


def test_merchandising_archive_preserves_category(monkeypatch):
    from app import create_app
    calls=[]
    monkeypatch.setattr(supa,'select',lambda table,*a,**k:[{'id':1,'name':'Category'}] if table=='categories' else [])
    monkeypatch.setattr(models,'get_user_by_id',lambda uid:{'id':uid,'is_admin':True})
    monkeypatch.setattr(supa,'update',lambda *args:calls.append(args) or True)
    monkeypatch.setattr(supa,'insert',lambda *args,**kwargs:True)
    app=create_app();app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,RATELIMIT_ENABLED=False)
    client=app.test_client()
    with client.session_transaction() as session:session['user_id']='admin';session['is_admin']=True
    response=client.post('/admin/merchandising/categories',data={'action':'archive','entry_id':'1'})
    assert response.status_code==302
    assert calls==[('categories',{'id':'eq.1'},{'active':False})]


def test_empty_homepage_and_dynamic_category_layouts(catalogue):
    from app import create_app
    tables,_=catalogue
    app=create_app();app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,RATELIMIT_ENABLED=False)
    client=app.test_client()
    for count in range(5):
        tables['categories']=[{'id':i,'name':f'Category {i}'} for i in range(count)]
        tables['products']=[{'id':str(i),'title':f'Creation {i}','category_id':i,'price':100,'is_listed':True,'availability_mode':'MADE_TO_ORDER','images':[]} for i in range(count)]
        response=client.get('/')
        assert response.status_code==200
        if count: assert f'category-count-{count}'.encode() in response.data
        else: assert b'category-grid' not in response.data
        assert b'Empty collection' not in response.data
        assert b'Unused' not in response.data


def test_checkout_error_retains_customer_choices(catalogue, monkeypatch):
    from app import create_app
    monkeypatch.setattr(supa,'rpc',lambda *a,**k:None)
    app=create_app();app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,RATELIMIT_ENABLED=False)
    client=app.test_client()
    with client.session_transaction() as session:session['cart']={'live':1}
    response=client.post('/checkout',data={
        'name':'Ada','email':'ada@example.com','phone':'9876543210',
        'delivery_type':'pickup','gift_message':'For your new chapter',
        'order_notes':'Please email before collection',
    })
    assert response.status_code==200
    assert b'We could not place your order' in response.data
    assert b'value="Ada"' in response.data
    assert b'value="ada@example.com"' in response.data
    assert b'value="pickup" checked' in response.data
    assert b'For your new chapter' in response.data
    assert b'Please email before collection' in response.data


def test_null_active_merchandising_is_hidden(catalogue):
    tables,_=catalogue
    tables['collections'][0]['active']=None
    with Flask(__name__).test_request_context():
        assert models.get_public_merchandising()['collections']==[]


@pytest.mark.parametrize('accepted',[True,False])
def test_admin_context_action_keeps_server_validation(catalogue,monkeypatch,accepted):
    from app import create_app
    rpc_calls=[];tracking=[]
    monkeypatch.setattr(models,'get_order',lambda oid:{'id':oid,'status':'advance_confirmed','fulfilment_status':'confirmed','payment_status':'advance_verified'})
    monkeypatch.setattr(models,'get_user_by_id',lambda uid:{'id':uid,'is_admin':True})
    monkeypatch.setattr(models,'add_tracking',lambda *a:tracking.append(a))
    monkeypatch.setattr(supa,'insert',lambda *a,**k:True)
    monkeypatch.setattr(supa,'rpc',lambda name,args:rpc_calls.append((name,args)) or accepted)
    app=create_app();app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,RATELIMIT_ENABLED=False)
    client=app.test_client()
    with client.session_transaction() as session:session['user_id']='admin';session['is_admin']=True
    response=client.post('/admin/orders/o',data={'action':'commerce_status','payment_status':'advance_verified','fulfilment_status':'crafting'})
    assert response.status_code==302
    assert rpc_calls==[('update_commerce_order',{'p_order_id':'o','p_data':{'payment_status':'advance_verified','fulfilment_status':'crafting'}})]
    assert bool(tracking)==accepted
