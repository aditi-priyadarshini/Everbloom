-- Exercises EVERY database function and its failure modes. Run on a disposable
-- migrated database:  psql -v ON_ERROR_STOP=1 -f tests/all_functions.sql
-- Everything runs inside one transaction that is rolled back.
-- Prints one row per FAILED check; prints "ALL n CHECKS PASSED" otherwise.
begin;
create temp table res(name text, pass boolean, detail text);

-- helpers --------------------------------------------------------------------
create function pg_temp.chk(n text, c boolean, d text default '') returns void language sql as
$$ insert into res values(n, coalesce(c,false), d) $$;

-- run q; pass only if it raises an error whose text contains `expect`
create function pg_temp.fails(n text, q text, expect text) returns void language plpgsql as $$
begin
  execute q;
  insert into res values(n, false, 'expected failure but succeeded');
exception when others then
  insert into res values(n, sqlerrm ilike '%'||expect||'%', sqlerrm);
end $$;

create function pg_temp.po(k text, extra jsonb default '{}') returns jsonb language sql as
$$ select jsonb_build_object('name','T','email','t@x.in','phone','1','address','a',
   'delivery_type','delivery','tracking_token','tok-'||k,'idempotency_key',k) || extra $$;

create function pg_temp.line(pid uuid, q int default 1, extra jsonb default '{}') returns jsonb language sql as
$$ select jsonb_build_array(jsonb_build_object('product_id',pid,'quantity',q) || extra) $$;

do $$
declare
  p_ready uuid; p_var uuid; p_pers uuid; p_mto uuid; p_unl uuid; p_closed uuid; p_unav uuid;
  p_pre uuid; p_one uuid; p_max uuid; p_other uuid;
  vS bigint; vL bigint; vR bigint; vB bigint; vOther bigint;
  mat bigint; mat2 bigint; comp bigint; r jsonb; r2 jsonb; oid uuid; n int; st numeric;
begin
  -- ===== fixtures =====
  insert into products(title,price,stock,availability_mode,crafting_days) values('Ready',100,50,'READY_TO_SHIP',0) returning id into p_ready;
  insert into products(title,price,stock,availability_mode,crafting_days) values('Var',100,20,'READY_TO_SHIP',0) returning id into p_var;
  insert into products(title,price,stock,availability_mode,crafting_days,personalization_fields)
    values('Pers',100,20,'READY_TO_SHIP',0,'[{"name":"text","required":true}]') returning id into p_pers;
  insert into products(title,price,stock,availability_mode,crafting_days) values('Mto',200,0,'MADE_TO_ORDER',3) returning id into p_mto;
  insert into products(title,price,stock,availability_mode,is_listed) values('Unlisted',100,5,'READY_TO_SHIP',false) returning id into p_unl;
  insert into products(title,price,stock,availability_mode,accepting_orders) values('Closed',100,5,'READY_TO_SHIP',false) returning id into p_closed;
  insert into products(title,price,stock,availability_mode) values('Unavail',100,5,'UNAVAILABLE') returning id into p_unav;
  insert into products(title,price,stock,availability_mode,preorder_closes) values('Pre',100,0,'PREORDER',current_date-1) returning id into p_pre;
  insert into products(title,price,stock,availability_mode) values('One',100,1,'ONE_OF_ONE') returning id into p_one;
  insert into products(title,price,stock,availability_mode,max_order_quantity) values('Max',100,50,'READY_TO_SHIP',2) returning id into p_max;
  insert into products(title,price,stock,availability_mode) values('Other',100,5,'READY_TO_SHIP') returning id into p_other;
  insert into variants(product_id,name,value,price_modifier) values(p_var,'Size','S',0) returning id into vS;
  insert into variants(product_id,name,value,price_modifier) values(p_var,'Size','L',50) returning id into vL;
  insert into variants(product_id,name,value,price_modifier) values(p_var,'Color','Red',0) returning id into vR;
  insert into variants(product_id,name,value,price_modifier) values(p_var,'Color','Blue',10) returning id into vB;
  insert into variants(product_id,name,value,price_modifier) values(p_other,'Size','X',0) returning id into vOther;
  insert into coupons(code,discount_percent,expires_at) values('EXP',10,now()-interval '1 day');
  insert into coupons(code,discount_percent,minimum_order_value) values('MIN',10,500);
  insert into coupons(code,discount_type,discount_value) values('FIX','fixed',30);
  insert into coupons(code,discount_percent,maximum_discount) values('CAP',50,5);
  insert into coupons(code,discount_percent,active) values('OFF',10,false);
  insert into gift_cards(code,amount,balance,active) values('GOFF',50,50,false);
  insert into gift_cards(code,amount,balance) values('G20',20,20);
  insert into gift_cards(code,amount,balance) values('GBIG',1000,1000);

  -- ===== place_commerce_order: validation =====
  perform pg_temp.fails('empty cart rejected', $q$select place_commerce_order(pg_temp.po('e1'),'[]'::jsonb)$q$, 'Invalid cart');
  perform pg_temp.fails('unknown product rejected', format($q$select place_commerce_order(pg_temp.po('u1'),pg_temp.line(%L))$q$, gen_random_uuid()), 'Product unavailable');
  perform pg_temp.fails('unlisted product rejected', format($q$select place_commerce_order(pg_temp.po('u2'),pg_temp.line(%L))$q$, p_unl), 'Product unavailable');
  perform pg_temp.fails('not-accepting-orders rejected', format($q$select place_commerce_order(pg_temp.po('u3'),pg_temp.line(%L))$q$, p_closed), 'Product unavailable');
  perform pg_temp.fails('UNAVAILABLE mode rejected', format($q$select place_commerce_order(pg_temp.po('u4'),pg_temp.line(%L))$q$, p_unav), 'Product unavailable');
  perform pg_temp.fails('qty 0 rejected', format($q$select place_commerce_order(pg_temp.po('q0'),pg_temp.line(%L,0))$q$, p_ready), 'Invalid quantity');
  perform pg_temp.fails('qty negative rejected', format($q$select place_commerce_order(pg_temp.po('q1'),pg_temp.line(%L,-3))$q$, p_ready), 'Invalid quantity');
  perform pg_temp.fails('qty above product max rejected', format($q$select place_commerce_order(pg_temp.po('q2'),pg_temp.line(%L,3))$q$, p_max), 'Invalid quantity');
  perform pg_temp.fails('oversell rejected', format($q$select place_commerce_order(pg_temp.po('q3'),pg_temp.line(%L,51))$q$, p_ready), 'Insufficient finished goods');
  perform pg_temp.fails('closed preorder rejected', format($q$select place_commerce_order(pg_temp.po('q4'),pg_temp.line(%L))$q$, p_pre), 'Preorder closed');
  perform pg_temp.fails('variant of another product rejected', format($q$select place_commerce_order(pg_temp.po('v1'),pg_temp.line(%L,1,jsonb_build_object('variant_ids',jsonb_build_array(%s))))$q$, p_var, vOther), 'Invalid variant');
  perform pg_temp.fails('duplicate variant group rejected', format($q$select place_commerce_order(pg_temp.po('v2'),pg_temp.line(%L,1,jsonb_build_object('variant_ids',jsonb_build_array(%s,%s))))$q$, p_var, vS, vL), 'Duplicate variant group');
  perform pg_temp.fails('missing variant group rejected', format($q$select place_commerce_order(pg_temp.po('v3'),pg_temp.line(%L,1,jsonb_build_object('variant_ids',jsonb_build_array(%s))))$q$, p_var, vS), 'Missing variant');
  perform pg_temp.fails('missing required personalization rejected', format($q$select place_commerce_order(pg_temp.po('pz'),pg_temp.line(%L))$q$, p_pers), 'Missing personalization');
  perform pg_temp.fails('delivery date too early rejected', format($q$select place_commerce_order(pg_temp.po('d1',jsonb_build_object('preferred_delivery_date',current_date::text)),pg_temp.line(%L))$q$, p_mto), 'Delivery date too early');
  perform pg_temp.fails('expired coupon rejected', format($q$select place_commerce_order(pg_temp.po('c1',jsonb_build_object('coupon_code','exp')),pg_temp.line(%L))$q$, p_ready), 'Coupon invalid');
  perform pg_temp.fails('inactive coupon rejected', format($q$select place_commerce_order(pg_temp.po('c2',jsonb_build_object('coupon_code','OFF')),pg_temp.line(%L))$q$, p_ready), 'Coupon invalid');
  perform pg_temp.fails('coupon below minimum rejected', format($q$select place_commerce_order(pg_temp.po('c3',jsonb_build_object('coupon_code','MIN')),pg_temp.line(%L))$q$, p_ready), 'Coupon invalid');
  perform pg_temp.fails('unknown coupon rejected', format($q$select place_commerce_order(pg_temp.po('c4',jsonb_build_object('coupon_code','NOPE')),pg_temp.line(%L))$q$, p_ready), 'Coupon invalid');
  perform pg_temp.fails('inactive gift card rejected', format($q$select place_commerce_order(pg_temp.po('g1',jsonb_build_object('gift_card_code','goff')),pg_temp.line(%L))$q$, p_ready), 'Gift card invalid');
  perform pg_temp.fails('unknown gift card rejected', format($q$select place_commerce_order(pg_temp.po('g2',jsonb_build_object('gift_card_code','NOPE')),pg_temp.line(%L))$q$, p_ready), 'Gift card invalid');
  select stock into st from products where id=p_ready;
  perform pg_temp.chk('failed orders never changed stock', st=50, 'stock='||st);

  -- ===== place_commerce_order: pricing =====
  r := place_commerce_order(pg_temp.po('ok1'), pg_temp.line(p_var,2,jsonb_build_object('variant_ids',jsonb_build_array(vL,vB))));
  perform pg_temp.chk('variant pricing: (100+50+10)*2=320', (r->>'total')::numeric=320, r->>'total');
  perform pg_temp.chk('variant stock decremented', (select stock from products where id=p_var)=18);
  r := place_commerce_order(pg_temp.po('fix1',jsonb_build_object('coupon_code','fix')), pg_temp.line(p_ready,1));
  perform pg_temp.chk('fixed coupon 100-30=70 (code case-insensitive)', (r->>'total')::numeric=70, r->>'total');
  r := place_commerce_order(pg_temp.po('cap1',jsonb_build_object('coupon_code','CAP')), pg_temp.line(p_ready,1));
  perform pg_temp.chk('max-discount cap: 50% capped to 5 => 95', (r->>'total')::numeric=95, r->>'total');
  r := place_commerce_order(pg_temp.po('gc1',jsonb_build_object('gift_card_code','g20')), pg_temp.line(p_ready,1));
  perform pg_temp.chk('gift card partial: 100-20=80', (r->>'total')::numeric=80, r->>'total');
  perform pg_temp.chk('gift card emptied and deactivated', (select balance=0 and not active from gift_cards where code='G20'));
  r := place_commerce_order(pg_temp.po('gc2',jsonb_build_object('gift_card_code','GBIG')), pg_temp.line(p_ready,1));
  perform pg_temp.chk('big gift card covers whole order => total 0', (r->>'total')::numeric=0, r->>'total');
  perform pg_temp.chk('big gift card keeps remainder 900', (select balance from gift_cards where code='GBIG')=900);
  r := place_commerce_order(pg_temp.po('one1'), pg_temp.line(p_one,1));
  perform pg_temp.fails('one-of-one cannot be sold twice', format($q$select place_commerce_order(pg_temp.po('one2'),pg_temp.line(%L))$q$, p_one), 'Insufficient finished goods');
  r := place_commerce_order(pg_temp.po('pz1'), pg_temp.line(p_pers,1,jsonb_build_object('personalization',jsonb_build_object('text','Ada'))));
  perform pg_temp.chk('personalization stored on line', (select personalization->>'text' from order_items where order_id=(r->>'id')::uuid)='Ada');
  -- idempotency
  r := place_commerce_order(pg_temp.po('idem'), pg_temp.line(p_max,1)); r2 := place_commerce_order(pg_temp.po('idem'), pg_temp.line(p_max,1));
  perform pg_temp.chk('idempotency key returns same order', r->>'id'=r2->>'id');
  perform pg_temp.chk('idempotent retry decrements stock once', (select stock from products where id=p_max)=49);
  perform pg_temp.chk('tracking row created at checkout', exists(select 1 from tracking where order_id=(r->>'id')::uuid and status='placed'));

  -- ===== update_commerce_order + state machine =====
  r := place_commerce_order(pg_temp.po('st1'), pg_temp.line(p_ready,1)); oid := (r->>'id')::uuid;
  perform pg_temp.fails('unknown order rejected', format($q$select update_commerce_order(%L,'{}'::jsonb)$q$, gen_random_uuid()), 'Unknown order');
  perform pg_temp.fails('advance greater than total rejected', format($q$select update_commerce_order(%L,'{"advance_amount":9999}'::jsonb)$q$, oid), 'Invalid order amount');
  perform pg_temp.fails('negative shipping rejected', format($q$select update_commerce_order(%L,'{"shipping_charge":-1}'::jsonb)$q$, oid), 'Invalid order amount');
  perform pg_temp.fails('bad payment status rejected by constraint', format($q$select update_commerce_order(%L,'{"payment_status":"banana"}'::jsonb)$q$, oid), 'orders_payment_status_check');
  perform pg_temp.fails('jump order_received->shipped rejected', format($q$select update_commerce_order(%L,'{"fulfilment_status":"shipped"}'::jsonb)$q$, oid), 'Invalid fulfilment transition');
  r := update_commerce_order(oid,'{"payment_status":"advance_verified","advance_amount":40,"internal_notes":"paid 40"}'::jsonb);
  perform pg_temp.chk('payment update persisted', r->>'payment_status'='advance_verified' and (r->>'advance_amount')::numeric=40 and r->>'internal_notes'='paid 40');
  perform update_commerce_order(oid,'{"fulfilment_status":"confirmed"}'::jsonb);
  perform update_commerce_order(oid,'{"fulfilment_status":"crafting"}'::jsonb);
  perform update_commerce_order(oid,'{"fulfilment_status":"quality_check"}'::jsonb);
  perform update_commerce_order(oid,'{"fulfilment_status":"ready_to_dispatch"}'::jsonb);
  perform update_commerce_order(oid,'{"fulfilment_status":"shipped"}'::jsonb);
  perform pg_temp.chk('legacy status mirrors fulfilment (shipped)', (select status from orders where id=oid)='shipped');
  perform update_commerce_order(oid,'{"fulfilment_status":"out_for_delivery"}'::jsonb);
  perform update_commerce_order(oid,'{"fulfilment_status":"delivered"}'::jsonb);
  perform pg_temp.fails('cannot go backwards from delivered', format($q$select update_commerce_order(%L,'{"fulfilment_status":"crafting"}'::jsonb)$q$, oid), 'Invalid fulfilment transition');
  perform pg_temp.fails('cannot cancel a delivered order', format($q$select cancel_commerce_order(%L)$q$, oid), 'return workflow');
  -- cancel through update restocks once
  r := place_commerce_order(pg_temp.po('st2'), pg_temp.line(p_max,2)); oid := (r->>'id')::uuid;
  select stock into st from products where id=p_max;
  perform update_commerce_order(oid,'{"fulfilment_status":"cancelled"}'::jsonb);
  perform pg_temp.chk('cancel via update restocks', (select stock from products where id=p_max)=st+2);
  perform cancel_commerce_order(oid);
  perform pg_temp.chk('second cancel does not restock again', (select stock from products where id=p_max)=st+2);
  perform pg_temp.fails('cancel unknown order rejected', format($q$select cancel_commerce_order(%L)$q$, gen_random_uuid()), 'Unknown order');
  -- legacy status field syncs payment state
  r := place_commerce_order(pg_temp.po('st3'), pg_temp.line(p_ready,1)); oid := (r->>'id')::uuid;
  update orders set status='advance_confirmed' where id=oid;
  perform pg_temp.chk('status advance_confirmed => payment verified + fulfilment confirmed',
    (select payment_status='advance_verified' and fulfilment_status='confirmed' from orders where id=oid));

  -- legacy single-status path (admin 'update_status' action sends only {"status":..})
  r := place_commerce_order(pg_temp.po('leg1'), pg_temp.line(p_ready,1)); oid := (r->>'id')::uuid;
  r := update_commerce_order(oid,'{"status":"advance_paid"}'::jsonb);
  perform pg_temp.chk('legacy status advance_paid => payment advance_submitted', r->>'payment_status'='advance_submitted', r->>'payment_status');
  r := update_commerce_order(oid,'{"status":"advance_confirmed"}'::jsonb);
  perform pg_temp.chk('legacy advance_confirmed => verified + confirmed', r->>'payment_status'='advance_verified' and r->>'fulfilment_status'='confirmed');
  r := update_commerce_order(oid,'{"status":"crafting"}'::jsonb);
  perform pg_temp.chk('legacy crafting => fulfilment crafting', r->>'fulfilment_status'='crafting');
  perform pg_temp.fails('legacy status cannot skip to delivered', format($q$select update_commerce_order(%L,'{"status":"delivered"}'::jsonb)$q$, oid), 'Invalid fulfilment transition');
  r := update_commerce_order(oid,'{"status":"cancelled"}'::jsonb);
  perform pg_temp.chk('legacy cancelled => cancelled + restocked', r->>'fulfilment_status'='cancelled' and (r->>'inventory_restored')::boolean);

  -- ===== consume_order_inventory / BOM / production =====
  insert into raw_materials(name,current_stock,unit,cost_per_unit) values('Wire',10,'m',2) returning id into mat;
  insert into raw_materials(name,current_stock,unit) values('Silk',1,'m') returning id into mat2;
  insert into products(title,price,stock,availability_mode) values('Bom',100,0,'MADE_TO_ORDER') returning id into p_other;
  insert into product_bom(product_id,item_type,material_id,quantity_used) values(p_other,'material',mat,3);
  insert into product_bom(product_id,item_type,material_id,quantity_used) values(p_other,'material',mat2,1);
  r := place_commerce_order(pg_temp.po('bom1'), pg_temp.line(p_other,2)); oid := (r->>'id')::uuid;
  perform pg_temp.fails('insufficient material blocks crafting', format($q$select consume_order_inventory(%L)$q$, oid), 'Insufficient material');
  perform pg_temp.chk('failed consumption is all-or-nothing (wire untouched)', (select current_stock from raw_materials where id=mat)=10);
  update raw_materials set current_stock=5 where id=mat2;
  perform consume_order_inventory(oid);
  perform pg_temp.chk('materials deducted (wire 10-6, silk 5-2)', (select current_stock from raw_materials where id=mat)=4 and (select current_stock from raw_materials where id=mat2)=3);
  perform pg_temp.chk('consumption movements logged', (select count(*) from inventory_movements where order_id=oid and movement_type='order_consumption')=2);
  perform pg_temp.fails('cannot consume for cancelled order', format($q$select (cancel_commerce_order(%L), consume_order_inventory(%L))$q$, oid, oid), 'Order unavailable');

  -- receive_material
  r := receive_material(jsonb_build_object('material_id',mat,'quantity',5,'cost_per_unit',3,'supplier','S'));
  perform pg_temp.chk('receive_material adds stock and sets cost', (select current_stock=9 and cost_per_unit=3 from raw_materials where id=mat));
  perform pg_temp.chk('receive_material total_cost=15 expenditure row', (r->>'total_cost')::numeric=15);
  perform pg_temp.fails('receive qty 0 rejected', format($q$select receive_material(jsonb_build_object('material_id',%s,'quantity',0,'cost_per_unit',1))$q$, mat), 'Invalid purchase');
  perform pg_temp.fails('receive negative cost rejected', format($q$select receive_material(jsonb_build_object('material_id',%s,'quantity',1,'cost_per_unit',-1))$q$, mat), 'Invalid purchase');
  perform pg_temp.fails('receive unknown material rejected', $q$select receive_material('{"material_id":999999,"quantity":1,"cost_per_unit":1}'::jsonb)$q$, 'Material not found');
  perform pg_temp.chk('missing-cost purchase did not wipe cost (still 3)', (select cost_per_unit from raw_materials where id=mat)=3);
  perform pg_temp.fails('receive garbage quantity gives clear error', format($q$select receive_material(jsonb_build_object('material_id',%s,'quantity','abc','cost_per_unit',1))$q$, mat), 'Invalid purchase');
  perform pg_temp.fails('receive MISSING quantity gives clear error', format($q$select receive_material(jsonb_build_object('material_id',%s,'cost_per_unit',1))$q$, mat), 'Invalid purchase');
  perform pg_temp.fails('receive MISSING cost gives clear error', format($q$select receive_material(jsonb_build_object('material_id',%s,'quantity',1))$q$, mat), 'Invalid purchase');

  -- produce_component
  insert into components(name,current_stock) values('Rose',0) returning id into comp;
  perform pg_temp.fails('produce without recipe rejected', format($q$select produce_component(%s,1,0,'')$q$, comp), 'recipe');
  perform pg_temp.fails('produce unknown component rejected', $q$select produce_component(999999,1,0,'')$q$, 'Unknown component');
  insert into component_bom(component_id,material_id,quantity_used) values(comp,mat,2);
  perform pg_temp.fails('produce qty 0 rejected', format($q$select produce_component(%s,0,0,'')$q$, comp), 'Invalid production quantity');
  perform pg_temp.fails('produce wastage >100 rejected', format($q$select produce_component(%s,1,101,'')$q$, comp), 'Invalid production quantity');
  perform pg_temp.fails('produce insufficient material rejected', format($q$select produce_component(%s,100,0,'')$q$, comp), 'Insufficient material');
  perform produce_component(comp, 2, 50, 'batch');   -- needs 2*2*1.5 = 6 wire (have 9)
  perform pg_temp.chk('produce: wire 9-6=3, rose +2', (select current_stock from raw_materials where id=mat)=3 and (select current_stock from components where id=comp)=2);
  perform pg_temp.chk('produce: wastage cost = cost 3 x (2 per unit x 2 units x 50%) = 6', (select waste_cost from manufacture_log where component_id=comp)=6,
    (select waste_cost::text from manufacture_log where component_id=comp));
  perform pg_temp.chk('stock audit trigger recorded balance changes', (select count(*) from inventory_movements where movement_type='balance_change')>=3);
  perform pg_temp.fails('negative stock blocked', format($q$update raw_materials set current_stock=-1 where id=%s$q$, mat), 'current_stock_check');

  -- subscribe_newsletter
  perform pg_temp.chk('newsletter subscribe returns true', subscribe_newsletter('Hello@Example.com'));
  perform subscribe_newsletter('hello@example.com'); perform subscribe_newsletter('HELLO@EXAMPLE.COM');
  select count(*) into n from newsletter_subscribers where lower(email)='hello@example.com';
  perform pg_temp.chk('newsletter dedups case-insensitively (1 row)', n=1, 'rows='||n);
  update newsletter_subscribers set active=false where email='hello@example.com';
  perform subscribe_newsletter('hello@example.com');
  perform pg_temp.chk('newsletter re-subscribe reactivates', (select active from newsletter_subscribers where email='hello@example.com'));

  -- convert_custom_request (id passed as text; works for any id type)
  declare cid text; cr jsonb; cr2 jsonb; begin
    insert into custom_requests(name,email,description,status) values('C','c@x.in','bouquet','quoted') returning id::text into cid;
    cr := convert_custom_request(cid, 300, 'note'); cr2 := convert_custom_request(cid, 300, 'again');
    perform pg_temp.chk('custom conversion idempotent', cr->>'id'=cr2->>'id');
    perform pg_temp.chk('custom order total/flags', (cr->>'total')::numeric=300 and (cr->>'is_custom_order')::boolean);
    perform pg_temp.chk('custom order follows state machine', (update_commerce_order((cr->>'id')::uuid,'{"fulfilment_status":"confirmed"}'::jsonb))->>'fulfilment_status'='confirmed');
    perform pg_temp.fails('custom: unknown id rejected', $q$select convert_custom_request('999999',100)$q$, 'does not exist');
    perform pg_temp.fails('custom: bad price rejected', format($q$select convert_custom_request(%L,0)$q$, cid), 'positive agreed price');
  end;
end $$;

-- privileges: backend-only
select pg_temp.chk('anon cannot execute any RPC', not exists(
  select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and p.proname in ('place_commerce_order','update_commerce_order','cancel_commerce_order','consume_order_inventory','convert_custom_request','receive_material','produce_component','subscribe_newsletter')
  and (has_function_privilege('anon',p.oid,'EXECUTE') or has_function_privilege('authenticated',p.oid,'EXECUTE'))));
select pg_temp.chk('exactly one convert_custom_request overload', (select count(*) from pg_proc where proname='convert_custom_request')=1);

select name, detail as problem from res where not pass order by name;
select case when count(*) filter (where not pass)=0 then 'ALL '||count(*)||' CHECKS PASSED' else count(*) filter (where not pass)||' of '||count(*)||' CHECKS FAILED' end as summary from res;
rollback;
