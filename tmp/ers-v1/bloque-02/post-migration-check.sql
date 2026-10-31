SELECT jsonb_pretty(jsonb_build_object(
  'schema_revision', (SELECT version_num FROM alembic_version),
  'lot_details', (SELECT jsonb_build_object('rows', count(*), 'coded_rows', count(*) FILTER (WHERE code IS NOT NULL), 'unique_codes', count(DISTINCT company_id || ':' || code)) FROM inventory_lot_details),
  'movement_lines', (SELECT jsonb_build_object('rows', count(*), 'new_direct_links', count(*) FILTER (WHERE line.inventory_lot_detail_id IS NOT NULL), 'legacy_lines_resolvable_through_exact_handling_unit', count(*) FILTER (WHERE hu.inventory_lot_detail_id IS NOT NULL), 'unattributed_legacy_lines', count(*) FILTER (WHERE hu.inventory_lot_detail_id IS NULL)) FROM inventory_movement_lines AS line LEFT JOIN inventory_handling_units AS hu ON hu.company_id = line.company_id AND hu.id = line.handling_unit_id),
  'immutable_movement_trigger', (SELECT count(*) FROM pg_trigger WHERE tgrelid = 'inventory_movement_lines'::regclass AND tgname = 'trg_inventory_movement_lines_immutable' AND NOT tgisinternal),
  'label_print_rows', (SELECT count(*) FROM inventory_label_prints),
  'average_rows', (SELECT count(*) FROM inventory_cost_averages),
  'average_quantity', (SELECT coalesce(sum(quantity_base), 0) FROM inventory_cost_averages),
  'average_value', (SELECT coalesce(sum(inventory_value), 0) FROM inventory_cost_averages),
  'valuation_entry_rows', (SELECT count(*) FROM inventory_valuation_entries),
  'valuation_entry_value', (SELECT coalesce(sum(source_value), 0) FROM inventory_valuation_entries),
  'physical_balance_rows', (SELECT count(*) FROM inventory_balances),
  'physical_quantity', (SELECT coalesce(sum(quantity_base), 0) FROM inventory_balances)
));
