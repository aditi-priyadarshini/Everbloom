begin;
alter table orders add constraint orders_payment_status_check check(payment_status in ('unpaid','advance_requested','advance_submitted','advance_verified','partially_paid','paid','COD_due','refunded','partially_refunded','failed','cancelled'));
alter table orders add constraint orders_fulfilment_status_check check(fulfilment_status in ('order_received','awaiting_confirmation','confirmed','crafting','quality_check','ready_to_dispatch','shipped','out_for_delivery','ready_for_pickup','delivered','cancelled'));
create or replace function validate_fulfilment_transition() returns trigger language plpgsql as $$
declare allowed text[];
begin
 if new.fulfilment_status=old.fulfilment_status then return new;end if;
 allowed=case old.fulfilment_status
  when 'order_received' then array['awaiting_confirmation','confirmed','cancelled']
  when 'awaiting_confirmation' then array['confirmed','cancelled']
  when 'confirmed' then array['crafting','cancelled']
  when 'crafting' then array['quality_check','cancelled']
  when 'quality_check' then array['ready_to_dispatch','ready_for_pickup','shipped','cancelled']
  when 'ready_to_dispatch' then array['shipped','cancelled']
  when 'shipped' then array['out_for_delivery','delivered']
  when 'out_for_delivery' then array['delivered']
  when 'ready_for_pickup' then array['delivered','cancelled']
  else array[]::text[] end;
 if not new.fulfilment_status=any(allowed) then raise exception 'Invalid fulfilment transition';end if;
 return new;
end $$;
create trigger z_orders_validate_fulfilment before update on orders for each row execute function validate_fulfilment_transition();
commit;
