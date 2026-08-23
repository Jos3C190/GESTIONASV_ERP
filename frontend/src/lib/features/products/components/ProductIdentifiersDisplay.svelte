<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import BarcodeDisplay from '$lib/features/products/components/BarcodeDisplay.svelte';
  import {
    barcodeFormat,
    identifierFormat,
    identifierFormatHint
  } from '$lib/features/products/identifiers';
  import type { ProductIdentifier } from '$lib/types/catalog';

  interface Props {
    identifiers: ProductIdentifier[];
    title?: string;
    description?: string;
  }

  let {
    identifiers,
    title = 'Identificadores',
    description = 'Códigos de escaneo y referencias propias.'
  }: Props = $props();
  let copiedId = $state<string | null>(null);

  async function copy(identifier: ProductIdentifier) {
    try {
      await navigator.clipboard.writeText(identifier.value);
    } catch {
      const input = document.createElement('textarea');
      input.value = identifier.value;
      input.style.position = 'fixed';
      input.style.opacity = '0';
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      input.remove();
    }
    copiedId = identifier.id;
    window.setTimeout(() => {
      if (copiedId === identifier.id) copiedId = null;
    }, 1600);
  }
</script>

<div>
  <div class="mb-5">
    <h2 class="text-base font-semibold text-foreground">{title}</h2>
    <p class="mt-1 text-sm text-foreground-muted">{description}</p>
  </div>
  {#if identifiers.length}
    <div class="grid gap-3 md:grid-cols-2">
      {#each identifiers as identifier (identifier.id)}
        <article class="rounded-xl border border-border bg-surface-muted/10 p-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div class="flex flex-wrap items-center gap-2">
              <span
                class="rounded-full border border-primary/30 bg-primary/5 px-2 py-0.5 text-xs font-semibold text-primary"
              >
                {identifierFormat(identifier.identifier_type, identifier.value)}
              </span>
              {#if identifier.is_primary}<Badge variant="primary">Principal</Badge>{/if}
              <Badge variant={identifier.is_active ? 'success' : 'neutral'}
                >{identifier.is_active ? 'Activo' : 'Inactivo'}</Badge
              >
            </div>
            <button
              type="button"
              class="rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-surface-hover"
              onclick={() => copy(identifier)}
              aria-label={`Copiar ${identifier.value}`}
              aria-live="polite"
            >
              {copiedId === identifier.id ? 'Copiado' : 'Copiar código'}
            </button>
          </div>
          {#if barcodeFormat(identifier.identifier_type, identifier.value)}
            <BarcodeDisplay
              identifierType={identifier.identifier_type}
              value={identifier.value}
              label={identifierFormat(identifier.identifier_type, identifier.value)}
            />
          {:else}
            <div
              class="rounded-lg border border-dashed border-border bg-surface px-3 py-4 text-center text-xs text-foreground-muted"
            >
              Este identificador se consulta como texto.
            </div>
          {/if}
          <p class="mt-3 break-all font-mono text-sm font-semibold tracking-wide text-foreground">
            {identifier.value}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">
            Formato: {identifierFormat(identifier.identifier_type, identifier.value)}
          </p>
          {#if identifierFormatHint(identifier.identifier_type, identifier.value)}
            <p class="mt-2 text-xs text-warning">
              {identifierFormatHint(identifier.identifier_type, identifier.value)}
            </p>
          {/if}
        </article>
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
