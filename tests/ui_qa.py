"""Local UI smoke checks. Run: python tests/ui_qa.py [--empty].

Requires requirements-dev.txt and Chromium. Never contacts production services.
"""
import argparse
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import models
import supa
from flask import redirect, session
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

product={'id':'qa-product','title':'QA handmade creation','description':'QA product story and materials.','price':1250,'stock':5,'category_id':1,'images':['/static/favicon.svg?one','/static/favicon.svg?two'],'image_alt_texts':['QA first image','QA second image'],'featured':True,'is_listed':True,'availability_mode':'READY_TO_SHIP','crafting_days':3,'personalization_fields':[{'name':'recipient','label':'Recipient name','required':True}],'created_at':'2026-10-01','discount_percent':0}
order={'id':'qa-order-0001','name':'QA customer','email':'qa@example.invalid','phone':'9876543210','address':'QA address','total':1250,'advance_amount':0,'shipping_charge':0,'discount_amount':0,'delivery_type':'delivery','created_at':'2026-10-01','status':'advance_confirmed','fulfilment_status':'confirmed','payment_status':'advance_verified','internal_notes':''}
material={'id':1,'name':'QA material','unit':'pieces','current_stock':2,'reorder_level':5,'cost_per_unit':20,'supplier':"QA's supplier",'active':True}
tables={'products':[product], 'categories':[{'id':1,'name':'QA category','slug':'qa-category'},{'id':2,'name':'QA empty category','slug':'qa-empty'}], 'raw_materials':[material], 'orders':[order], 'order_items':[{'id':'qa-item','order_id':order['id'],'product_id':product['id'],'title':product['title'],'price':1250,'quantity':1,'personalization':{'recipient':'QA recipient'},'variant_ids':[]}], 'variants':[{'id':1,'product_id':product['id'],'name':'Size','value':'Regular','price_modifier':0}]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--empty',action='store_true')
    parser.add_argument('--only',help='Check one supported page at every width')
    parser.add_argument('--output',default='/tmp/everbloom-qa')
    args=parser.parse_args()
    def select(table, filters=None, **kwargs):
        rows=[] if args.empty else tables.get(table,[])
        for key,value in (filters or {}).items():
            if value.startswith('eq.'):
                rows=[row for row in rows if str(row.get(key,'')).lower()==value[3:].lower()]
        return rows
    supa.select=select
    supa.insert=lambda *a,**k:{'id':'qa'}
    supa.update=lambda *a,**k:True
    supa.delete=lambda *a,**k:True
    supa.rpc=lambda *a,**k:None
    supa.upload_file=lambda *a,**k:None
    models.get_user_by_id=lambda uid:{'id':uid,'name':'QA','is_admin':True}
    from app import create_app
    app=create_app()
    app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,RATELIMIT_ENABLED=False)
    app.jinja_env.auto_reload=True
    @app.get('/__qa_admin')
    def admin_session():
        session.update(user_id='qa',is_admin=True,user_name='QA')
        return redirect('/admin/')
    @app.get('/__qa_cart')
    def cart_session():
        session['cart']={'qa':{'product_id':product['id'],'qty':1,'variant_ids':['1'],'personalization':{'recipient':'QA recipient'}}}
        return redirect('/cart')
    server=make_server('127.0.0.1',0,app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    errors=[];checks=[]
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page()
            page.route('https://**/*',lambda route:route.abort())
            page.on('pageerror',lambda error:errors.append(str(error)))
            for width in [360,390,430,768,1024,1280,1440]:
                page.context.clear_cookies()
                page.set_viewport_size({'width':width,'height':900})
                if not args.empty:page.goto(base+'/__qa_cart')
                public=['/','/shop','/cart','/custom-order','/auth/login']
                if not args.empty:public+=['/product/qa-product','/checkout']
                admin=['/admin/','/admin/products','/admin/products/new','/admin/orders','/admin/inventory','/admin/components','/admin/settings','/admin/analytics','/admin/merchandising/categories']
                if not args.empty:admin+=['/admin/products/qa-product/edit','/admin/orders/qa-order-0001','/admin/inventory/1']
                if args.only:
                    if args.only not in public+admin:parser.error('Unsupported page: '+args.only)
                    public=[path for path in public if path==args.only]
                    admin=[path for path in admin if path==args.only]
                for area,paths in [('public',public),('admin',admin)]:
                    if area=='admin':page.goto(base+'/__qa_admin')
                    for path in paths:
                        response=page.goto(base+path);page.wait_for_load_state('networkidle')
                        assert response.status==200,(path,response.status)
                        scroll=page.evaluate('document.documentElement.scrollWidth')
                        if scroll>width:errors.append(f'Overflow {path} at {width}: {scroll}')
                        if width in [390,1440] and path in ['/','/admin/','/cart','/checkout','/admin/orders/qa-order-0001']:
                            mode='empty' if args.empty else 'populated'
                            page.screenshot(path=str(output/f'{mode}-{path.strip("/").replace("/","-") or "home"}-{width}.png'),full_page=True)
                        if path=='/' and width<=1024:
                            page.locator('#hamburger').click();assert page.locator('#mobileNav').evaluate('(el)=>el.open')
                            page.keyboard.press('Escape');page.locator('#mobileNav').wait_for(state='hidden')
                            assert page.locator('#hamburger').evaluate('(el)=>el===document.activeElement')
                        if path=='/shop' and width<768:
                            page.locator('[data-filter-sort]').click();assert page.locator('[name=sort]').evaluate('(el)=>el===document.activeElement')
                            page.keyboard.press('Escape');page.locator('.shop-layout>#shopFilters').wait_for(state='attached')
                        if path=='/product/qa-product':
                            page.locator('[data-gallery-src]').nth(1).click();assert page.locator('#mainImg').get_attribute('alt')=='QA second image'
                        if path=='/cart' and not args.empty:assert 'QA recipient' in page.inner_text('main')
                        if path=='/admin/' and width<=768:
                            page.locator('[data-admin-open]').click();assert page.locator('#adminSidebar').get_attribute('aria-modal')=='true'
                            page.keyboard.press('Escape');assert not page.locator('#adminSidebar').evaluate('(el)=>el.classList.contains("open")')
                        if path=='/admin/products/qa-product/edit':
                            page.locator('[data-image-move="1"]').first.click();assert page.locator('[name=image_order]').first.input_value()=='1'
                            assert page.locator('.personalisation-editor').is_visible()
                        if path=='/admin/inventory' and not args.empty:
                            page.locator('button.table-action',has_text='Receive stock').first.click();assert page.locator('#purchaseModal').evaluate('(el)=>el.open')
                            page.keyboard.press('Escape');page.locator('#purchaseModal').wait_for(state='hidden')
                            page.locator('button.table-action',has_text='Edit').first.click();assert page.locator('#editSupplier').input_value()=="QA's supplier"
                            page.keyboard.press('Escape');page.locator('#editModal').wait_for(state='hidden')
                            page.locator('[data-material-search]').fill('no match');assert not page.locator('[data-material-row]').first.is_visible()
                            page.locator('[data-material-search]').fill('QA');assert page.locator('[data-material-row]').first.is_visible()
                checks.append({'width':width,'pages':len(public)+len(admin)})
                print(f'{width}px checked',flush=True)
            browser.close()
        report={'mode':'empty' if args.empty else 'populated','checks':checks,'errors':errors}
        (output/(report['mode']+'-results.json')).write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2));assert not errors
    finally:
        server.shutdown();thread.join(timeout=5)


if __name__=='__main__':main()
