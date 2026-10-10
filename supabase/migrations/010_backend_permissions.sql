begin;
-- BYPASSRLS does not imply table privileges. Grant only application tables.
do $$ declare t text; begin
 foreach t in array array['users','products','categories','coupons','variants','orders','order_items','tracking','notifications','reviews','wishlists','settings','custom_requests','raw_materials','components','component_bom','product_bom','product_materials','product_costs','expenditures','manufacture_log','order_requirements','auth_tokens','gift_cards','returns','faqs','broadcasts','back_in_stock_alerts','email_templates','email_log','artisans','newsletter_subscribers','inventory_movements','audit_log','collections','occasions','collection_products','product_occasions','testimonials'] loop
 execute format('grant select,insert,update,delete on public.%I to service_role',t);
 end loop;
end $$;
grant usage,select on all sequences in schema public to service_role;
commit;
