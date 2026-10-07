begin;
create or replace function place_commerce_order(p_order jsonb,p_lines jsonb) returns jsonb language plpgsql security definer set search_path=public as $$
declare o orders%rowtype; p products%rowtype; v variants%rowtype; c coupons%rowtype; g gift_cards%rowtype; gift_discount numeric=0; l jsonb; vid jsonb; opts jsonb; prepared jsonb='[]'; unit_price numeric; subtotal numeric=0; discount numeric=0; qty integer; entry jsonb; mode text; max_days integer=0;
begin
 if jsonb_array_length(p_lines)<1 or jsonb_array_length(p_lines)>100 then raise exception 'Invalid cart'; end if;
 perform pg_advisory_xact_lock(hashtextextended(p_order->>'idempotency_key',0));
 select * into o from orders where idempotency_key=p_order->>'idempotency_key';
 if found then return to_jsonb(o); end if;
 -- Stable lock order prevents two carts with reversed product order from deadlocking.
 perform 1 from products where id::text in (select value->>'product_id' from jsonb_array_elements(p_lines)) order by id for update;
 for l in select value from jsonb_array_elements(p_lines) loop
  select * into p from products where id::text=l->>'product_id';
  mode=p.availability_mode; qty=(l->>'quantity')::integer;
  if not found or not coalesce(p.is_listed,true) or not p.accepting_orders or mode not in ('READY_TO_SHIP','MADE_TO_ORDER','PREORDER','ONE_OF_ONE') then raise exception 'Product unavailable'; end if;
  if qty<1 or qty>least(coalesce(p.max_order_quantity,99),99) then raise exception 'Invalid quantity'; end if;
  if mode='PREORDER' and ((p.preorder_opens is not null and current_date<p.preorder_opens) or (p.preorder_closes is not null and current_date>p.preorder_closes)) then raise exception 'Preorder closed'; end if;
  if mode in ('READY_TO_SHIP','ONE_OF_ONE') then
   update products set stock=stock-qty where id=p.id and stock>=qty;
   if not found then raise exception 'Insufficient finished goods'; end if;
  end if;
  unit_price=coalesce(p.sale_price,round(p.price*(1-least(100,greatest(0,coalesce(p.discount_percent,0)))::numeric/100),2));
  opts='[]';
  for vid in select value from jsonb_array_elements(coalesce(l->'variant_ids','[]')) loop
   select * into v from variants where id::text=vid#>>'{}' and product_id=p.id;
   if not found then raise exception 'Invalid variant'; end if;
   if exists(select 1 from jsonb_array_elements(opts) x where x->>'name'=v.name) then raise exception 'Duplicate variant group'; end if;
   unit_price=unit_price+coalesce(v.price_modifier,0);
   opts=opts||jsonb_build_array(jsonb_build_object('id',v.id,'name',v.name,'value',v.value));
  end loop;
  if (select count(distinct name) from variants where product_id=p.id)<>jsonb_array_length(opts) then raise exception 'Missing variant'; end if;
  for entry in select value from jsonb_array_elements(p.personalization_fields) loop
   if coalesce((entry->>'required')::boolean,false) and coalesce(l->'personalization'->>(entry->>'name'),'')='' then raise exception 'Missing personalization'; end if;
  end loop;
  unit_price=greatest(0,round(unit_price,2)); subtotal=subtotal+unit_price*qty;
  max_days=greatest(max_days,coalesce(p.lead_time_max,p.crafting_days,0));
  prepared=prepared||jsonb_build_array(jsonb_build_object('product_id',p.id,'title',p.title,'price',unit_price,'quantity',qty,'image_url',coalesce(p.images->>0,''),'variant_ids',coalesce(l->'variant_ids','[]'),'selected_options',opts,'personalization',coalesce(l->'personalization','{}'),'availability_mode',mode));
 end loop;
 if nullif(p_order->>'preferred_delivery_date','') is not null and (p_order->>'preferred_delivery_date')::date<current_date+max_days+coalesce((select nullif(value,'')::integer from settings where key='processing_buffer'),0) then raise exception 'Delivery date too early'; end if;
 if nullif(p_order->>'coupon_code','') is not null then
  select * into c from coupons where code=upper(p_order->>'coupon_code') for update;
  if not found or not c.active or (c.expires_at is not null and c.expires_at<now()) or (c.starts_at is not null and c.starts_at>now()) or subtotal<coalesce(c.minimum_order_value,0) or (c.usage_limit is not null and coalesce(c.used_count,0)>=c.usage_limit) then raise exception 'Coupon invalid'; end if;
  discount=case when c.discount_type='fixed' then coalesce(c.discount_value,0) else round(subtotal*coalesce(c.discount_percent,0)/100,2) end;
  discount=greatest(0,least(subtotal,discount,coalesce(c.maximum_discount,subtotal)));
  update coupons set used_count=coalesce(used_count,0)+1 where id=c.id;
 end if;
 if nullif(p_order->>'gift_card_code','') is not null then
  select * into g from gift_cards where code=upper(p_order->>'gift_card_code') for update;
  if not found or not g.active or g.balance<=0 or (g.expires_at is not null and g.expires_at<now()) then raise exception 'Gift card invalid'; end if;
  gift_discount=least(g.balance,subtotal-discount);
  update gift_cards set balance=balance-gift_discount,active=(balance-gift_discount)>0 where id=g.id;
 end if;
 insert into orders(user_id,name,email,phone,address,total,status,coupon_code,discount_amount,delivery_type,preferred_delivery_date,tracking_token,idempotency_key,gift_message,order_notes,gift_card_code,gift_card_discount)
 values(nullif(p_order->>'user_id','')::uuid,p_order->>'name',p_order->>'email',p_order->>'phone',p_order->>'address',subtotal-discount-gift_discount,'placed',p_order->>'coupon_code',discount,p_order->>'delivery_type',nullif(p_order->>'preferred_delivery_date','')::date,p_order->>'tracking_token',p_order->>'idempotency_key',p_order->>'gift_message',p_order->>'order_notes',p_order->>'gift_card_code',gift_discount) returning * into o;
 for l in select value from jsonb_array_elements(prepared) loop
  insert into order_items(order_id,product_id,title,price,quantity,image_url,variant_ids,selected_options,personalization,availability_mode) values(o.id,(l->>'product_id')::uuid,l->>'title',(l->>'price')::numeric,(l->>'quantity')::integer,l->>'image_url',l->'variant_ids',l->'selected_options',l->'personalization',l->>'availability_mode');
  if l->>'availability_mode' in ('READY_TO_SHIP','ONE_OF_ONE') then
   insert into inventory_movements(item_type,item_id,quantity,movement_type,order_id,note) values('finished',l->>'product_id',-(l->>'quantity')::numeric,'order_reservation',o.id,'Finished piece allocated to order');
  end if;
 end loop;
 insert into tracking(order_id,status,note) values(o.id,'placed','Your order has been received. We will confirm preparation and payment details.');
 return to_jsonb(o);
end $$;

create or replace function consume_order_inventory(p_order_id uuid) returns boolean language plpgsql security definer set search_path=public as $$
declare o orders%rowtype; r record; before_qty numeric; after_qty numeric;
begin
 select * into o from orders where id=p_order_id for update;
 if not found or o.status='cancelled' then raise exception 'Order unavailable'; end if;
 if o.inventory_consumed then return true; end if;
 for r in select b.item_type,b.material_id,b.component_id,sum(b.quantity_used*i.quantity) needed from order_items i join product_bom b on b.product_id=i.product_id where i.order_id=p_order_id and coalesce(i.availability_mode,'MADE_TO_ORDER') in ('MADE_TO_ORDER','PREORDER','CUSTOM_ONLY') group by b.item_type,b.material_id,b.component_id order by b.item_type,b.material_id,b.component_id loop
  if r.item_type='material' then
   select current_stock into before_qty from raw_materials where id=r.material_id for update;
   if before_qty is null or before_qty<r.needed then raise exception 'Insufficient material'; end if;
   after_qty=before_qty-r.needed; update raw_materials set current_stock=after_qty where id=r.material_id;
  else
   select current_stock into before_qty from components where id=r.component_id for update;
   if before_qty is null or before_qty<r.needed then raise exception 'Insufficient component'; end if;
   after_qty=before_qty-r.needed; update components set current_stock=after_qty where id=r.component_id;
  end if;
  insert into inventory_movements(item_type,item_id,quantity,previous_quantity,resulting_quantity,movement_type,order_id) values(r.item_type,coalesce(r.material_id,r.component_id)::text,-r.needed,before_qty,after_qty,'order_consumption',p_order_id);
 end loop;
 update orders set inventory_consumed=true where id=p_order_id;
 return true;
end $$;

create or replace function cancel_commerce_order(p_order_id uuid) returns boolean language plpgsql security definer set search_path=public as $$
declare o orders%rowtype; r record;
begin
 select * into o from orders where id=p_order_id for update;
 if not found then raise exception 'Unknown order'; end if;
 if o.inventory_restored then return true; end if;
 if o.status in ('shipped','delivered') then raise exception 'Use return workflow for dispatched orders'; end if;
 -- Finished pieces can be returned to availability. Consumed craft materials cannot
 -- be assumed reusable; their disposition requires an explicit audited adjustment.
 for r in select * from inventory_movements where order_id=p_order_id and movement_type='order_reservation' order by item_id loop
  update products set stock=stock-r.quantity where id::text=r.item_id;
  insert into inventory_movements(item_type,item_id,quantity,movement_type,order_id) values('finished',r.item_id,-r.quantity,'cancellation_restock',p_order_id);
 end loop;
 update orders set status='cancelled',fulfilment_status='cancelled',inventory_restored=true where id=p_order_id;
 insert into tracking(order_id,status,note) values(p_order_id,'cancelled','Order cancelled. Any payment refund will be confirmed separately.');
 return true;
end $$;
create or replace function subscribe_newsletter(p_email text) returns boolean language plpgsql security definer set search_path=public as $$ begin insert into newsletter_subscribers(email) values(lower(p_email)) on conflict(email) do update set active=true; return true; end $$;
revoke all on function place_commerce_order(jsonb,jsonb),consume_order_inventory(uuid),cancel_commerce_order(uuid),subscribe_newsletter(text) from public,anon,authenticated;
grant execute on function place_commerce_order(jsonb,jsonb),consume_order_inventory(uuid),cancel_commerce_order(uuid),subscribe_newsletter(text) to service_role;
commit;
