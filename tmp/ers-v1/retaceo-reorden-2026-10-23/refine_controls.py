from pathlib import Path
import re

root = Path('frontend/src/lib/features')
paths = [
    root / 'inventory/components/InventoryWorkspace.svelte',
    root / 'inventory/components/WarehouseReceiptQueue.svelte',
    root / 'locations/components/LocationGridPicker.svelte',
    root / 'purchases/components/PurchaseWorkflowActions.svelte',
    *[root / f'retaceos/components/{name}.svelte' for name in (
        'RetaceoCreateEditor', 'RetaceoDraftEditor', 'RetaceoDetail',
        'RetaceoCostEditor', 'RetaceoImportFields', 'RetaceoWorkflowActions',
        'RetaceoAveragePanel', 'RetaceoPlannedExpenses',
    )],
]
for path in paths:
    source = path.read_text(encoding='utf-8')
    source = source.replace('text-danger', 'text-foreground').replace('text-warning', 'text-foreground')
    source = re.sub(
        r'<(?:input|select|textarea)\b[\s\S]*?(?=/?>\s*<|/>)',
        lambda match: match[0].replace('border-border', 'border-border-control'),
        source,
        flags=re.DOTALL,
    )
    source = source.replace(
        "'h-10 w-full rounded-lg border border-border bg-surface",
        "'h-10 w-full rounded-lg border border-border-control bg-surface",
    )
    path.write_text(source, encoding='utf-8', newline='\n')
