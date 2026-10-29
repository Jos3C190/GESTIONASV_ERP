SELECT jsonb_pretty(jsonb_build_object(
  'schema_revision', (SELECT version_num FROM alembic_version),
  'companies', (SELECT count(*) FROM companies),
  'branches', (SELECT count(*) FROM branches),
  'warehouses', (SELECT count(*) FROM warehouses),
  'inventory_lots', (SELECT jsonb_build_object('rows', count(*), 'label_confirmation_required', count(*) FILTER (WHERE label_confirmation_required)) FROM inventory_lots),
  'inventory_lot_details', (SELECT jsonb_build_object('rows', count(*), 'accepted_quantity_base', coalesce(sum(accepted_quantity_base), 0)) FROM inventory_lot_details),
  'handling_units', (SELECT jsonb_build_object('rows', count(*), 'open_rows', count(*) FILTER (WHERE closed_at IS NULL), 'open_quantity', coalesce(sum(quantity_base) FILTER (WHERE closed_at IS NULL), 0)) FROM inventory_handling_units),
  'inventory_balances', (SELECT jsonb_build_object('rows', count(*), 'quantity', coalesce(sum(quantity_base), 0)) FROM inventory_balances),
  'inventory_movements', (SELECT count(*) FROM inventory_movements),
  'inventory_movement_lines', (SELECT jsonb_build_object('rows', count(*), 'quantity', coalesce(sum(quantity_base), 0)) FROM inventory_movement_lines),
  'inventory_label_prints', (SELECT count(*) FROM inventory_label_prints),
  'inventory_valuation_settings', (SELECT count(*) FROM inventory_valuation_settings),
  'inventory_cost_averages', (SELECT jsonb_build_object('rows', count(*), 'quantity', coalesce(sum(quantity_base), 0), 'value', coalesce(sum(inventory_value), 0)) FROM inventory_cost_averages),
  'inventory_valuation_entries', (SELECT jsonb_build_object('rows', count(*), 'quantity', coalesce(sum(quantity_base), 0), 'source_value', coalesce(sum(source_value), 0), 'inventory_delta', coalesce(sum(inventory_delta), 0)) FROM inventory_valuation_entries),
  'inventory_retaceo_applications', (SELECT count(*) FROM inventory_retaceo_applications),
  'purchases', (SELECT count(*) FROM purchases)
));