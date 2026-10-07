begin;
create or replace function convert_custom_request(p_request_id uuid,p_price numeric,p_note text default '') returns jsonb language plpgsql security definer set search_path=public as $$
declare r custom_requests%rowtype; o orders%rowtype; p products%rowtype;
begin
 if p_price<=0 then raise exception 'Quote must be positive'; end if;
 select * into r from custom_requests where id=p_request_id for update;
 if not found then raise exception 'Unknown request'; end if;
 if r.converted_order_id is not null then select * into o from orders where id=r.converted_order_id;return to_jsonb(o);end if;
 if r.status in ('closed','rejected') then raise exception 'Request is closed';end if;
 if r.linked_product_id is not null then select * into p from products where id=r.linked_product_id;end if;
 insert into orders(user_id,name,email,phone,address,total,status,is_custom_order,custom_request_id,custom_notes,tracking_token,preferred_delivery_date,internal_notes)
 values(r.user_id,r.name,r.email,r.phone,'To be confirmed',p_price,'placed',true,r.id,r.description,encode(gen_random_bytes(32),'hex'),r.preferred_delivery_date,p_note) returning * into o;
 insert into order_items(order_id,product_id,title,price,quantity,image_url,is_custom,availability_mode,personalization)
 values(o.id,r.linked_product_id,coalesce(p.title,r.craft_type,'Custom creation'),p_price,1,coalesce(p.images->>0,r.reference_image_url,''),true,'MADE_TO_ORDER',jsonb_build_object('request',r.description,'colours',r.colour_preference,'occasion',r.occasion));
 update custom_requests set status='converted',converted_order_id=o.id,quoted_price=p_price where id=r.id;
 insert into tracking(order_id,status,note) values(o.id,'placed','Your custom creation has been confirmed. We will share the next steps.');
 return to_jsonb(o);
end $$;
revoke all on function convert_custom_request(uuid,numeric,text) from public,anon,authenticated;
grant execute on function convert_custom_request(uuid,numeric,text) to service_role;
commit;
