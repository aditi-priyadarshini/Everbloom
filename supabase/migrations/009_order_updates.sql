begin;
create or replace function update_commerce_order(p_order_id uuid,p_data jsonb) returns jsonb language plpgsql security definer set search_path=public as $$
declare current_order orders%rowtype; desired orders%rowtype;
begin
 select * into current_order from orders where id=p_order_id for update;
 if not found then raise exception 'Unknown order';end if;
 select * into desired from jsonb_populate_record(current_order,p_data);
 if desired.fulfilment_status='cancelled' or desired.status='cancelled' then
  perform cancel_commerce_order(p_order_id);
  select * into current_order from orders where id=p_order_id;
  return to_jsonb(current_order);
 end if;
 if desired.fulfilment_status='crafting' or desired.status='crafting' then perform consume_order_inventory(p_order_id);end if;
 if desired.total<0 or desired.shipping_charge<0 or desired.advance_amount<0 or desired.advance_amount>desired.total then raise exception 'Invalid order amount';end if;
 update orders set status=desired.status,payment_status=desired.payment_status,fulfilment_status=desired.fulfilment_status,total=desired.total,shipping_charge=desired.shipping_charge,advance_amount=desired.advance_amount,payment_screenshot_url=desired.payment_screenshot_url,internal_notes=desired.internal_notes where id=p_order_id returning * into current_order;
 return to_jsonb(current_order);
end $$;
revoke all on function update_commerce_order(uuid,jsonb) from public,anon,authenticated;
grant execute on function update_commerce_order(uuid,jsonb) to service_role;
commit;
