# Launch verification and remaining scope

This implementation is a substantial in-place rebuild, **not a claim that every requested production feature is complete**.

## Verify with actual services before launch

- Restore a production backup into staging and compare identifier types/legacy columns with the baseline before running migrations.
- Test Supabase REST/RPC permissions with the configured service-role key, public image upload, private receipt upload and signed admin receipt viewing.
- Test Google OAuth and verification/reset/transactional SMTP delivery. Failed email currently logs but has no durable retry queue.
- Migrate historical public payment screenshots into the private bucket and delete the public copies.
- Replace default content with actual brand photography, business details, approved testimonials and legal policies.
- Configure shared Redis rate limiting, verify HTTPS cookies and run complete guest/registered/custom/admin journeys.

## Scope still needing a dedicated follow-up

- Full purchasable SKU combinations with independent variant inventory/images and BOM overrides. Current legacy option groups are validated and preserved throughout cart/order/email; finished inventory and recipes remain product-level.
- Visual personalisation-field builder (current editor is validated JSON), image alt-text metadata and drag ordering.
- Product detail dimensions/materials/care content, recently viewed products, full multi-image mobile lightbox.
- Comprehensive date-range analytics, popularity ranking, shipping-zone pricing, blocked delivery dates, configurable payment-method switches and persisted address book.
- Per-customer/category/product coupon targeting. Current fixed/percentage discounts, dates, minimum, maximum and total usage limits are implemented; redemption and gift-card balance changes are atomic.
- Full editing/archive management for merchandising entries; current screens create/list categories, collections, occasions and approved testimonials and assign memberships.
- Durable email retries and email delivery state; customer-safe creation photos; automated customer return notifications/refund execution.
- Audit entries currently record admin POST attempts that completed without HTTP errors; they do not prove the underlying mutation succeeded. Inventory balance triggers provide the authoritative quantity history; actor attribution on individual balance changes remains incomplete.
- Some legacy admin pages retain inline CSS and browser confirmation dialogs. These need further component extraction and interactive mobile QA.

The SQL transaction regression suite validates the local fresh baseline. It does not simulate a real deployed Supabase schema or all concurrent production traffic.
