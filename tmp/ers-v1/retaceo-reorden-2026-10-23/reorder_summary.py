from pathlib import Path

path = Path('frontend/src/lib/features/retaceos/components/RetaceoDetail.svelte')
source = path.read_text(encoding='utf-8')
start = source.index('    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">', source.index('    <RetaceoWorkflowActions'))
end = source.index('    {#if costs.length > 0}', start)
summary = source[start:end]
source = source[:start] + source[end:]
insert = source.index('    {#if item.origin_country', source.index('    <RetaceoWorkflowActions'))
source = source[:insert] + summary + source[insert:]
path.write_text(source, encoding='utf-8', newline='\n')
