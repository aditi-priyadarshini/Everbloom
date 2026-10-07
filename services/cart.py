import models
from services.commerce import availability, price, quantity, line_key

def normalize(cart):
    result={}
    for key,value in cart.items():
        if isinstance(value,int):
            result[line_key(key)]={'product_id':str(key),'qty':value,'variant_ids':[],'personalization':{}}
        else: result[key]=value
    return result

def resolve(cart, strict=True):
    items=[]
    for key,line in normalize(cart).items():
        p=models.get_product(line['product_id'])
        if not p or not availability(p)['published']:
            if strict: raise ValueError('A product in your bag is no longer available. Please remove it.')
            p={'id':line['product_id'],'title':'Unavailable creation','price':0,'images':[],'stock':0,'availability_mode':'UNAVAILABLE'}
        qty=quantity(line['qty'])
        choices={str(v['id']):v for v in models.get_variants(p['id'])}
        ids=line.get('variant_ids',[])
        if any(str(vid) not in choices for vid in ids):
            if strict: raise ValueError('A selected option is no longer available. Please add the product again.')
            ids=[]
            p={**p,'availability_mode':'UNAVAILABLE'}
        variants=[choices[str(vid)] for vid in ids]
        unit=price(p,variants)
        items.append({'key':key,'product':p,'qty':qty,'variants':variants,'variant_ids':ids,'personalization':line.get('personalization',{}),'unit_price':unit,'subtotal':unit*qty})
    return items

def selection(p,form):
    variants=models.get_variants(p['id']); selected=[]
    for name in dict.fromkeys(v['name'] for v in variants):
        chosen=form.get('variant_'+name.lower().replace(' ','_'))
        match=next((v for v in variants if v['name']==name and str(v['id'])==str(chosen)),None)
        if not match: raise ValueError('Choose an option for '+name+'.')
        selected.append(str(match['id']))
    fields=p.get('personalization_fields') or []
    personal={}
    for field in fields:
        key=field['name']; value=form.get('personalization_'+key,'').strip()[:1000]
        if field.get('required') and not value: raise ValueError('Please complete '+field.get('label',key)+'.')
        if value: personal[key]=value
    return selected,personal
