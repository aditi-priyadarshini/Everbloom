-- Everbloom: harden receive_material (stock purchases).
--
-- Bug: when "cost_per_unit" (or "quantity") was missing, the old checks
-- (qty<=0 or cpu<0) evaluated to NULL instead of true, so validation was skipped.
-- A missing cost silently overwrote the material's cost_per_unit with NULL (which
-- also zeroed later wastage/costing), and a missing quantity failed with a cryptic
-- NOT NULL violation. Now all inputs are validated up front with a clear message.
-- Same signature (jsonb) and grants, so no app change is needed. Safe to re-run.
BEGIN;

CREATE OR REPLACE FUNCTION public.receive_material(p_data jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  result expenditures%ROWTYPE;
  qty numeric;
  cpu numeric;
  mid bigint;
BEGIN
  IF p_data IS NULL OR jsonb_typeof(p_data) <> 'object' THEN
    RAISE EXCEPTION 'Invalid purchase';
  END IF;
  BEGIN
    qty := nullif(btrim(p_data->>'quantity'), '')::numeric;
    cpu := nullif(btrim(p_data->>'cost_per_unit'), '')::numeric;
    mid := nullif(btrim(p_data->>'material_id'), '')::bigint;
  EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN
    RAISE EXCEPTION 'Invalid purchase';
  END;
  IF mid IS NULL THEN
    RAISE EXCEPTION 'Material not found';
  END IF;
  -- NULL-safe: a missing value must be rejected, not slip past a NULL comparison.
  IF qty IS NULL OR cpu IS NULL OR qty <= 0 OR cpu < 0 THEN
    RAISE EXCEPTION 'Invalid purchase';
  END IF;

  UPDATE raw_materials SET current_stock = current_stock + qty, cost_per_unit = cpu WHERE id = mid;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Material not found';
  END IF;
  INSERT INTO expenditures(material_id, quantity, cost_per_unit, total_cost, supplier, note, reference)
  VALUES (mid, qty, cpu, qty * cpu, p_data->>'supplier', p_data->>'note', p_data->>'reference')
  RETURNING * INTO result;
  RETURN to_jsonb(result);
END $$;

REVOKE ALL ON FUNCTION public.receive_material(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.receive_material(jsonb) TO service_role;
COMMIT;

NOTIFY pgrst, 'reload schema';
