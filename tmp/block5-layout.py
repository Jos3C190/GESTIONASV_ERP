from pathlib import Path

path = Path("frontend/src/routes/(app)/inventory/kardex/+page.svelte")
source = path.read_text(encoding="utf-8")
source = source.replace("text-sm text-danger", "text-sm text-foreground")
for kind, summary_end in (("physicalData", "            </section>"), ("reconciliation", "          </dl>"), ("valuationData", "          </div>\n          {#if valuationData.entries")):
    start = source.index("<KardexStatementTools\n", source.index(f"{{:else if {kind}")) if kind != "physicalData" else source.index("<KardexStatementTools\n")
    end = source.index("\n", source.index("/>", start))
    block = source[start:end]
    source = source[:start] + source[end:]
    marker_start = source.index(summary_end, start)
    insert_at = marker_start + (len("          </div>") if kind == "valuationData" else len(summary_end))
    source = source[:insert_at] + "\n          " + block + source[insert_at:]
path.write_text(source, encoding="utf-8")
