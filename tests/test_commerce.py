from decimal import Decimal
from datetime import date, timedelta
import pytest
from services.commerce import availability,price,line_key,quantity,coupon_discount,earliest_date

@pytest.mark.parametrize('mode,stock,expected',[('MADE_TO_ORDER',0,True),('READY_TO_SHIP',0,False),('READY_TO_SHIP',2,True),('ONE_OF_ONE',0,False),('CUSTOM_ONLY',2,False),('DRAFT',10,False),('UNAVAILABLE',2,False)])
def test_availability(mode,stock,expected):
    assert availability({'availability_mode':mode,'stock':stock})['purchasable'] is expected

def test_legacy_availability():
    assert availability({'stock':0,'allow_preorder':True})['mode']=='MADE_TO_ORDER'
    assert not availability({'stock':1,'is_listed':False})['published']

def test_money_and_options():
    assert price({'price':'99.95','discount_percent':10},[{'price_modifier':'20.05'}])==Decimal('110.01')
    assert price({'price':100,'sale_price':75,'discount_percent':50})==Decimal('75.00')

def test_cart_separates_variants_and_personalisation():
    assert line_key('p',[1]) != line_key('p',[2])
    assert line_key('p',[1],{'name':'A'}) != line_key('p',[1],{'name':'B'})
    assert line_key('p',[1,2]) == line_key('p',[2,1])

@pytest.mark.parametrize('value',[-1,0,100,'bad'])
def test_invalid_quantity(value):
    with pytest.raises(ValueError): quantity(value)

def test_coupon_rules():
    assert coupon_discount({'active':True,'discount_percent':20,'maximum_discount':15},100)==15
    assert coupon_discount({'active':True,'discount_type':'fixed','discount_value':150},100)==100
    for c in [{'active':False},{'minimum_order_value':200},{'usage_limit':1,'used_count':1},{'expires_at':'2000-01-01T00:00:00Z'}]:
        with pytest.raises(ValueError): coupon_discount(c,100)

def test_slowest_lead_time():
    assert earliest_date([{'product':{'lead_time_max':2}},{'product':{'lead_time_max':7}}],2)==date.today()+timedelta(days=9)
