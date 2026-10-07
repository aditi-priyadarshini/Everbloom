begin;
alter table raw_materials add column if not exists sku text;
alter table raw_materials add column if not exists supplier_sku text;
alter table raw_materials add column if not exists storage_location text;
alter table raw_materials add column if not exists active boolean not null default true;
alter table components add column if not exists active boolean not null default true;
alter table components add column if not exists notes text;
alter table expenditures add column if not exists note text;
alter table expenditures add column if not exists reference text;
alter table product_costs add column if not exists notes text;
alter table custom_requests add column if not exists quoted_days integer;
alter table custom_requests add column if not exists quote_message text;
alter table custom_requests add column if not exists quote_sent_at timestamptz;
create or replace function receive_material(p_data jsonb) returns jsonb language plpgsql security definer set search_path=public as $$
declare result expenditures%rowtype; qty numeric; cpu numeric;
begin
 qty=(p_data->>'quantity')::numeric; cpu=(p_data->>'cost_per_unit')::numeric;
 if qty<=0 or cpu<0 then raise exception 'Invalid purchase'; end if;
 update raw_materials set current_stock=current_stock+qty,cost_per_unit=cpu where id=(p_data->>'material_id')::bigint;
 if not found then raise exception 'Material not found'; end if;
 insert into expenditures(material_id,quantity,cost_per_unit,total_cost,supplier,note,reference) values((p_data->>'material_id')::bigint,qty,cpu,qty*cpu,p_data->>'supplier',p_data->>'note',p_data->>'reference') returning * into result;
 return to_jsonb(result);
end $$;
create or replace function produce_component(p_component_id bigint,p_quantity numeric,p_wastage numeric,p_notes text) returns boolean language plpgsql security definer set search_path=public as $$
declare r record; need numeric; available numeric; waste_cost numeric=0;
begin
 if p_quantity<=0 or p_wastage<0 or p_wastage>100 then raise exception 'Invalid production quantity'; end if;
 perform 1 from components where id=p_component_id for update;
 if not found then raise exception 'Unknown component'; end if;
 if not exists(select 1 from component_bom where component_id=p_component_id) then raise exception 'Define a component recipe first'; end if;
 for r in select b.material_id,sum(b.quantity_used) qty from component_bom b where component_id=p_component_id group by b.material_id order by b.material_id loop
  need=r.qty*p_quantity*(1+p_wastage/100);
  select current_stock into available from raw_materials where id=r.material_id for update;
  if available is null or available<need then raise exception 'Insufficient material'; end if;
  update raw_materials set current_stock=current_stock-need where id=r.material_id;
  waste_cost=waste_cost+coalesce((select cost_per_unit from raw_materials where id=r.material_id),0)*r.qty*p_quantity*p_wastage/100;
 end loop;
 update components set current_stock=current_stock+p_quantity where id=p_component_id;
 insert into manufacture_log(component_id,quantity_made,wastage_percent,waste_cost,notes) values(p_component_id,p_quantity,p_wastage,waste_cost,p_notes);
 return true;
end $$;
-- Capture all stock edits, including legacy adjustment screens. Explicit order
-- movements retain order context; this trigger is a complete quantity audit.
create or replace function record_stock_change() returns trigger language plpgsql set search_path=public as $$
begin
 if new.current_stock is distinct from old.current_stock then
  if new.current_stock<0 then raise exception 'Inventory cannot be negative'; end if;
  insert into inventory_movements(item_type,item_id,quantity,previous_quantity,resulting_quantity,movement_type) values(case when tg_table_name='components' then 'component' else 'material' end,new.id::text,new.current_stock-old.current_stock,old.current_stock,new.current_stock,'balance_change');
 end if;
 return new;
end $$;
create trigger raw_material_balance_audit after update of current_stock on raw_materials for each row execute function record_stock_change();
create trigger component_balance_audit after update of current_stock on components for each row execute function record_stock_change();
revoke all on function receive_material(jsonb),produce_component(bigint,numeric,numeric,text) from public,anon,authenticated;
grant execute on function receive_material(jsonb),produce_component(bigint,numeric,numeric,text) to service_role;
commit;
