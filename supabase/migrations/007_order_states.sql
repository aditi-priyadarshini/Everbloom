begin;
-- Legacy status remains a compatibility field for existing screens/emails.
create or replace function sync_order_states() returns trigger language plpgsql as $$
begin
 if tg_op='INSERT' or new.status is distinct from old.status then
  if new.status in ('advance_requested','advance_paid','advance_confirmed') then
   new.payment_status=case new.status when 'advance_requested' then 'advance_requested' when 'advance_paid' then 'advance_submitted' else 'advance_verified' end;
  end if;
  if new.status in ('crafting','quality_check','shipped','delivered','cancelled') then new.fulfilment_status=new.status;
  elsif new.status='advance_confirmed' then new.fulfilment_status='confirmed';end if;
 elsif new.fulfilment_status is distinct from old.fulfilment_status then
  if new.fulfilment_status in ('crafting','quality_check','shipped','delivered','cancelled') then new.status=new.fulfilment_status;end if;
 end if;
 return new;
end $$;
create trigger orders_state_compatibility before insert or update on orders for each row execute function sync_order_states();
update orders set payment_status=case status when 'advance_requested' then 'advance_requested' when 'advance_paid' then 'advance_submitted' when 'advance_confirmed' then 'advance_verified' else payment_status end,
fulfilment_status=case when status in ('crafting','quality_check','shipped','delivered','cancelled') then status when status='advance_confirmed' then 'confirmed' else fulfilment_status end;
commit;
