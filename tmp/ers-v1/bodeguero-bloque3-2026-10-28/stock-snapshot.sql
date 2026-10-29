SELECT 'balances', count(*), COALESCE(sum(quantity_base),0)::text FROM inventory_balances;
SELECT 'movements', count(*) FROM inventory_movements;
SELECT 'valuation', count(*), COALESCE(sum(inventory_delta),0)::text FROM inventory_valuation_entries;
SELECT 'units', count(*), COALESCE(sum(quantity_base),0)::text FROM inventory_handling_units;
