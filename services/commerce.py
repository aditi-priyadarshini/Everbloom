"""Shared commerce rules. Client prices are never accepted."""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date, datetime, timedelta, timezone
import hashlib
import json

MODES = ('READY_TO_SHIP', 'MADE_TO_ORDER', 'PREORDER', 'ONE_OF_ONE', 'CUSTOM_ONLY', 'UNAVAILABLE', 'DRAFT', 'ARCHIVED')
PAYMENT_STATUSES = ('unpaid','advance_requested','advance_submitted','advance_verified','partially_paid','paid','COD_due','refunded','partially_refunded','failed','cancelled')
FULFILMENT_STATUSES = ('order_received','awaiting_confirmation','confirmed','crafting','quality_check','ready_to_dispatch','shipped','out_for_delivery','ready_for_pickup','delivered','cancelled')

def money(value):
    try:
        result = Decimal(str(value or 0)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError('Invalid amount') from exc
    if not result.is_finite():
        raise ValueError('Invalid amount')
    return result

def price(product, variants=()):
    base = money(product['price'])
    if product.get('sale_price') is not None:
        base = money(product['sale_price'])
    else:
        base = money(base * (100 - min(100, max(0, int(product.get('discount_percent') or 0)))) / 100)
    return max(Decimal(0), money(base + sum((money(v.get('price_modifier')) for v in variants), Decimal(0))))

def availability(p):
    mode = p.get('availability_mode') or ('READY_TO_SHIP' if int(p.get('stock') or 0)>0 else 'MADE_TO_ORDER' if p.get('allow_preorder') else 'UNAVAILABLE')
    published = p.get('is_listed', True) and mode not in ('DRAFT','ARCHIVED')
    enabled = published and p.get('accepting_orders', True)
    labels = {'READY_TO_SHIP':'Ready to dispatch','MADE_TO_ORDER':'Made especially for you','PREORDER':'Preorder','ONE_OF_ONE':'One of a kind','CUSTOM_ONLY':'Request something similar','UNAVAILABLE':'Temporarily unavailable','DRAFT':'Unpublished','ARCHIVED':'Archived'}
    if mode in ('READY_TO_SHIP','ONE_OF_ONE') and int(p.get('stock') or 0)<=0:
        enabled=False; labels[mode]='Sold' if mode=='ONE_OF_ONE' else 'Temporarily unavailable'
    if mode=='PREORDER':
        today=date.today().isoformat()
        enabled=enabled and (not p.get('preorder_opens') or str(p['preorder_opens'])[:10]<=today) and (not p.get('preorder_closes') or str(p['preorder_closes'])[:10]>=today)
    return {'mode':mode,'label':labels.get(mode,'Unavailable'),'purchasable':bool(enabled and mode in MODES[:4]),'published':bool(published)}

def line_key(product_id, variant_ids=(), personalization=None):
    payload=json.dumps([str(product_id),sorted(map(str,variant_ids)),personalization or {}],sort_keys=True,separators=(',',':'))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]

def quantity(value):
    try: result=int(value)
    except (ValueError,TypeError): raise ValueError('Enter a valid quantity.')
    if not 1<=result<=99: raise ValueError('Quantity must be between 1 and 99.')
    return result

def earliest_date(items, buffer=0):
    days=max((int(i['product'].get('lead_time_max') or i['product'].get('crafting_days') or 0) for i in items),default=0)
    return date.today()+timedelta(days=max(0,days)+max(0,int(buffer)))

def coupon_discount(coupon, subtotal):
    if not coupon or not coupon.get('active',True): raise ValueError('Invalid or inactive coupon.')
    now=datetime.now(timezone.utc)
    for key,expired in [('starts_at',False),('expires_at',True)]:
        if coupon.get(key):
            dt=datetime.fromisoformat(coupon[key].replace('Z','+00:00'))
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            if (expired and dt<now) or (not expired and dt>now): raise ValueError('Coupon is outside its valid dates.')
    if money(subtotal)<money(coupon.get('minimum_order_value')): raise ValueError('Order does not meet the coupon minimum.')
    if coupon.get('usage_limit') is not None and int(coupon.get('used_count') or 0)>=int(coupon['usage_limit']): raise ValueError('Coupon usage limit reached.')
    result=money(coupon.get('discount_value')) if coupon.get('discount_type')=='fixed' else money(money(subtotal)*money(coupon.get('discount_percent'))/100)
    if coupon.get('maximum_discount') is not None: result=min(result,money(coupon['maximum_discount']))
    return max(Decimal(0),min(money(subtotal),result))
