<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import {
    IDENTIFIER_TYPE_OPTIONS,
    identifierFormatHint,
    identifierFormat
  } from '$lib/features/products/identifiers';
  import type { ProductIdentifierDraft, ProductIdentifierType } from '$lib/types/catalog';

  export type IdentifierEditorDraft = ProductIdentifierDraft & { _key?: string };

  interface Props {
    identifiers: IdentifierEditorDraft[];
    editable?: boolean;
    max?: number;
  }

  let { identifiers = $bindable(), editable = true, max = 20 }: Props = $props();
  let keySequence = 0;

  function key() {
    keySequence += 1;
    return `identifier-${keySequence}`;
  }

  function update(index: number, patch: Partial<IdentifierEditorDraft>) {
    if (!editable) return;
    let next = identifiers.map((item, itemIndex) =>
      itemIndex === index ? { ...item, ...patch } : item
    );
    if (patch.is_primary) {
      const type = patch.identifier_type ?? identifiers[index]?.identifier_type;
      next = next.map((item, itemIndex) => itemItemType(item, type, itemIndex, index));
    }
    identifiers = next;
  }

  function itemItemType(
    item: IdentifierEditorDraft,
    type: ProductIdentifierType | undefined,
    itemIndex: number,
    changedIndex: number
  ) {
    return item.identifier_type === type && itemIndex !== changedIndex
      ? { ...item, is_primary: false }
      : item;
  }

  function add() {
    if (!editable || identifiers.length >= max) return;
    identifiers = [
      ...identifiers,
      { _key: key(), identifier_type: 'internal', value: '', is_primary: false, is_active: true }
    ];
  }

  function remove(index: number) {
    if (!editable) return;
    if (!window.confirm('¿Eliminar este identificador? Esta acción se aplicará al guardar.'))
      return;
    identifiers = identifiers.filter((_, itemIndex) => itemIndex !== index);
  }
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div>
      <h3 class="text-sm font-semibold text-foreground">Identificadores de escaneo</h3>
      <p class="mt-1 text-xs text-foreground-muted">
        EAN, UPC, GTIN, ISBN y referencias internas. No son el SKU.
      </p>
    </div>
    {#if editable}<Button
        size="sm"
        variant="secondary"
        onclick={add}
        disabled={identifiers.length >= max}>Agregar identificador</Button
      >{/if}
  </div>
  {#if identifiers.length}
    <div class="space-y-3">
      {#each identifiers as identifier, index (identifier.id ?? `${identifier.identifier_type}-${index}`)}
        <div class="rounded-xl border border-border bg-surface-muted/10 p-4">
          <div class="grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)_auto_auto_auto] lg:items-end">
            <label class="text-xs font-medium text-foreground-muted"
              >Tipo
              <select
                class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground"
                value={identifier.identifier_type}
                disabled={!editable}
                onchange={(event) =>
                  update(index, {
                    identifier_type: (event.currentTarget as HTMLSelectElement)
                      .value as ProductIdentifierType
                  })}
              >
                {#each IDENTIFIER_TYPE_OPTIONS as option (option.value)}<option value={option.value}
                    >{option.label}</option
                  >{/each}
              </select>
            </label>
            <FormField
              id={`identifier-${index}-value`}
              label="Código"
              value={identifier.value}
              disabled={!editable}
              placeholder="Ingrese el valor"
              oninput={(event) =>
                update(index, { value: (event.currentTarget as HTMLInputElement).value })}
            />
            <label class="flex items-center gap-2 pb-2 text-xs text-foreground"
              ><input
                type="checkbox"
                checked={identifier.is_primary}
                disabled={!editable}
                onchange={(event) =>
                  update(index, { is_primary: (event.currentTarget as HTMLInputElement).checked })}
              /> Principal</label
            >
            <label class="flex items-center gap-2 pb-2 text-xs text-foreground"
              ><input
                type="checkbox"
                checked={identifier.is_active}
                disabled={!editable}
                onchange={(event) =>
                  update(index, { is_active: (event.currentTarget as HTMLInputElement).checked })}
              /> Activo</label
            >
            {#if editable}<button
                type="button"
                class="pb-2 text-xs font-medium text-danger hover:underline"
                onclick={() => remove(index)}>Eliminar</button
              >{/if}
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-foreground-muted">
            <span
              class="rounded-full border border-primary/30 bg-primary/5 px-2 py-0.5 text-primary"
              >{identifierFormat(identifier.identifier_type, identifier.value)}</span
            >
            {#if identifierFormatHint(identifier.identifier_type, identifier.value)}<span
                class="text-warning"
                >{identifierFormatHint(identifier.identifier_type, identifier.value)}</span
              >{/if}
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div
      class="rounded-xl border border-dashed border-border p-6 text-center text-sm text-foreground-muted"
    >
      No hay identificadores registrados.
    </div>
  {/if}
</div>
