-- Run against a disposable migrated database with psql -v ON_ERROR_STOP=1.
begin;
do $$
declare pid uuid; made uuid; oid uuid; rid uuid; mat bigint; answer jsonb; again jsonb; before_count integer;
begin
 insert into products(title,price,stock,availability_mode,is_listed,crafting_days) values('Transaction test',100,2,'READY_TO_SHIP',true,0) returning id into pid;
 answer=place_commerce_order(jsonb_build_object('name','Test','email','test@example.com','phone','1234567890','address','Test address','delivery_type','delivery','tracking_token','test-token','idempotency_key','test-key'),jsonb_build_array(jsonb_build_object('product_id',pid,'quantity',1)));
 oid=(answer->>'id')::uuid;
 assert (select stock from products where id=pid)=1,'Finished goods must decrement';
 assert (answer->>'total')::numeric=100,'Total must be recalculated';
 assert answer->>'payment_status'='unpaid','Payment state must be separate';
 assert answer->>'fulfilment_status'='order_received','Fulfilment state must be separate';
 again=place_commerce_order(jsonb_build_object('idempotency_key','test-key'),jsonb_build_array(jsonb_build_object('product_id',pid,'quantity',1)));
 assert answer->>'id'=again->>'id','Repeat checkout must return same order';
 assert (select stock from products where id=pid)=1,'Repeat checkout must not decrement';
 perform cancel_commerce_order(oid); perform cancel_commerce_order(oid);
 assert (select stock from products where id=pid)=2,'Cancellation restock must run once';
 assert exists(select 1 from orders where id=oid),'Cancellation must preserve history';
 begin
  perform place_commerce_order(jsonb_build_object('idempotency_key','oversell'),jsonb_build_array(jsonb_build_object('product_id',pid,'quantity',3)));
  raise exception 'Oversell incorrectly succeeded';
 exception when others then
  if sqlerrm='Oversell incorrectly succeeded' then raise; end if;
 end;
 assert (select stock from products where id=pid)=2,'Failed transaction must roll back';
 insert into raw_materials(name,current_stock,unit) values('Ribbon test',10,'m') returning id into mat;
 insert into products(title,price,stock,availability_mode,is_listed,crafting_days) values('Made test',200,0,'MADE_TO_ORDER',true,0) returning id into made;
 insert into product_bom(product_id,item_type,material_id,quantity_used) values(made,'material',mat,2);
 answer=place_commerce_order(jsonb_build_object('name','Test','email','test@example.com','idempotency_key','made-test','tracking_token','made-token'),jsonb_build_array(jsonb_build_object('product_id',made,'quantity',2)));
 rid=(answer->>'id')::uuid;
 assert (select stock from products where id=made)=0,'MTO must not use finished stock';
 perform consume_order_inventory(rid); perform consume_order_inventory(rid);
 assert (select current_stock from raw_materials where id=mat)=6,'Material deduction must run once';
 perform cancel_commerce_order(rid);
 assert (select current_stock from raw_materials where id=mat)=6,'Consumed materials must not be assumed recovered';
 raise notice 'Transaction regression tests passed';
end $$;
rollback;

begin;
do $$
declare pid uuid; oid uuid; rid uuid; mat bigint; v1 bigint; result jsonb; repeat_result jsonb;
begin
 insert into products(title,price,stock,availability_mode,is_listed,crafting_days) values('Options test',100,10,'READY_TO_SHIP',true,0) returning id into pid;
 insert into variants(product_id,name,value,price_modifier) values(pid,'Size','Grand',25) returning id into v1;
 insert into coupons(code,discount_percent,usage_limit) values('TEST-LIMIT',10,1);
 insert into gift_cards(code,amount,balance) values('TEST-GIFT',50,50);
 result=place_commerce_order(jsonb_build_object('idempotency_key','option-test','tracking_token','option-token','coupon_code','TEST-LIMIT','gift_card_code','TEST-GIFT'),jsonb_build_array(jsonb_build_object('product_id',pid,'quantity',2,'variant_ids',jsonb_build_array(v1),'personalization',jsonb_build_object('recipient','Ada'))));
 oid=(result->>'id')::uuid;
 assert (result->>'total')::numeric=175,'Options, coupon and gift card must affect total';
 assert (select balance from gift_cards where code='TEST-GIFT')=0,'Gift redemption must persist';
 assert (select selected_options->0->>'value' from order_items where order_id=oid)='Grand','Variant snapshot missing';
 assert (select personalization->>'recipient' from order_items where order_id=oid)='Ada','Personalization missing';
 begin
  perform place_commerce_order(jsonb_build_object('idempotency_key','coupon-reuse','coupon_code','TEST-LIMIT'),jsonb_build_array(jsonb_build_object('product_id',pid,'quantity',1,'variant_ids',jsonb_build_array(v1))));
  raise exception 'Coupon reuse incorrectly succeeded';
 exception when others then if sqlerrm='Coupon reuse incorrectly succeeded' then raise;end if;end;
 assert (select stock from products where id=pid)=8,'Failed coupon must roll back stock';
 insert into custom_requests(name,email,description,status,tracking_token) values('Test','test@example.com','Custom bouquet request','quoted','request-token') returning id into rid;
 result=convert_custom_request(rid,500,'Private note');repeat_result=convert_custom_request(rid,500,'Repeat');
 assert result->>'id'=repeat_result->>'id','Custom conversion must be repeat safe';
 assert (select count(*) from order_items where order_id=(result->>'id')::uuid)=1,'Custom order item must exist once';
 assert not exists(select 1 from tracking where order_id=(result->>'id')::uuid and note like '%Private note%'),'Internal notes leaked';
 insert into raw_materials(name,current_stock) values('State test',10) returning id into mat;
 insert into products(title,price,stock,availability_mode,is_listed,crafting_days) values('State test',100,0,'MADE_TO_ORDER',true,0) returning id into pid;
 insert into product_bom(product_id,item_type,material_id,quantity_used) values(pid,'material',mat,2);
 result=place_commerce_order(jsonb_build_object('idempotency_key','state-test','tracking_token','state-token'),jsonb_build_array(jsonb_build_object('product_id',pid,'quantity',1)));
 oid=(result->>'id')::uuid;
 begin
  perform update_commerce_order(oid,'{"fulfilment_status":"crafting"}'::jsonb);
  raise exception 'Invalid transition incorrectly succeeded';
 exception when others then if sqlerrm='Invalid transition incorrectly succeeded' then raise;end if;end;
 assert (select current_stock from raw_materials where id=mat)=10,'Invalid state must roll back consumption';
 perform update_commerce_order(oid,'{"fulfilment_status":"confirmed"}'::jsonb);
 perform update_commerce_order(oid,'{"fulfilment_status":"crafting"}'::jsonb);
 perform update_commerce_order(oid,'{"fulfilment_status":"crafting"}'::jsonb);
 assert (select current_stock from raw_materials where id=mat)=8,'Crafting allocation must run once';
 assert (select payment_status from orders where id=oid)='unpaid','Crafting must not imply paid';
 raise notice 'Options, promotions, custom conversion and state regression tests passed';
end $$;
rollback;
