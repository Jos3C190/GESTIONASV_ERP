<script lang="ts">
  import type { InventoryLabelLayout } from '../types';
  import {
    LABEL_CONTENT_NAMES,
    LABEL_SIZES,
    MINIMUM_LABEL_SIZES,
    labelCopiesIssue,
    labelDimensionIssue
  } from '../label-printing';

  let {
    layout,
    copies,
    disabled = false,
    onlayout,
    oncopies
  }: {
    layout: InventoryLabelLayout;
    copies: string | number;
    disabled?: boolean;
    onlayout: (layout: InventoryLabelLayout) => void;
    oncopies: (copies: string) => void;
  } = $props();
  let forceCustomSize = $state(false);
  let copiesIssue = $derived(labelCopiesIssue(copies));
  let widthIssue = $derived(labelDimensionIssue(layout, 'width_mm'));
  let heightIssue = $derived(labelDimensionIssue(layout, 'height_mm'));
  let customSize = $derived(
    forceCustomSize ||
      !LABEL_SIZES[layout.content].some(
        ([width, height]) => width === layout.width_mm && height === layout.height_mm
      )
  );
  const inputClass =
    'mt-1 h-11 w-full rounded-lg border border-border-control bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50';
  function changeContent(content: InventoryLabelLayout['content']) {
    forceCustomSize = false;
    const size = content === 'full' ? [100, 125] : LABEL_SIZES[content][0];
    onlayout({ content, width_mm: size[0]!, height_mm: size[1]! });
  }
</script>

<fieldset class="mt-4 space-y-3" {disabled}>
  <legend class="text-sm font-semibold text-foreground">Configuración de impresión</legend>
  <div class="grid gap-3 sm:grid-cols-2">
    <label class="text-xs font-medium text-foreground-muted" for="hu-label-content">
      Contenido
      <select
        id="hu-label-content"
        class={inputClass}
        value={layout.content}
        onchange={(event) =>
          changeContent(event.currentTarget.value as InventoryLabelLayout['content'])}
      >
        {#each Object.entries(LABEL_CONTENT_NAMES) as [value, name]}<option {value}>{name}</option
          >{/each}
      </select>
    </label>
    <label class="text-xs font-medium text-foreground-muted" for="hu-label-size">
      Tamaño · ancho × alto
      <select
        id="hu-label-size"
        class={inputClass}
        value={customSize ? 'custom' : `${layout.width_mm}x${layout.height_mm}`}
        onchange={(event) => {
          forceCustomSize = event.currentTarget.value === 'custom';
          if (!forceCustomSize) {
            const [width, height] = event.currentTarget.value.split('x').map(Number);
            onlayout({ ...layout, width_mm: width!, height_mm: height! });
          }
        }}
      >
        {#each LABEL_SIZES[layout.content] as [width, height]}<option value={`${width}x${height}`}
            >{width} × {height} mm</option
          >{/each}
        <option value="custom">Medidas personalizadas</option>
      </select>
    </label>
    {#if customSize}
      <label class="text-xs font-medium text-foreground-muted" for="hu-label-width"
        >Ancho (mm)
        <input
          id="hu-label-width"
          class={inputClass}
          type="number"
          min={MINIMUM_LABEL_SIZES[layout.content][0]}
          max="200"
          step="1"
          inputmode="numeric"
          value={layout.width_mm}
          aria-invalid={Boolean(widthIssue)}
          aria-describedby={widthIssue ? 'hu-label-width-issue' : undefined}
          oninput={(event) => onlayout({ ...layout, width_mm: event.currentTarget.valueAsNumber })}
        />
        {#if widthIssue}<span
            id="hu-label-width-issue"
            class="mt-1 block text-xs text-danger"
            role="alert">{widthIssue}</span
          >{/if}
      </label>
      <label class="text-xs font-medium text-foreground-muted" for="hu-label-height"
        >Alto (mm)
        <input
          id="hu-label-height"
          class={inputClass}
          type="number"
          min={MINIMUM_LABEL_SIZES[layout.content][1]}
          max="200"
          step="1"
          inputmode="numeric"
          value={layout.height_mm}
          aria-invalid={Boolean(heightIssue)}
          aria-describedby={heightIssue ? 'hu-label-height-issue' : undefined}
          oninput={(event) => onlayout({ ...layout, height_mm: event.currentTarget.valueAsNumber })}
        />
        {#if heightIssue}<span
            id="hu-label-height-issue"
            class="mt-1 block text-xs text-danger"
            role="alert">{heightIssue}</span
          >{/if}
      </label>
    {/if}
    <label class="text-xs font-medium text-foreground-muted" for="handling-unit-label-copies"
      >Copias (1–100)
      <input
        id="handling-unit-label-copies"
        class={inputClass}
        type="number"
        min="1"
        max="100"
        step="1"
        inputmode="numeric"
        value={copies}
        aria-invalid={Boolean(copiesIssue)}
        aria-describedby={copiesIssue ? 'hu-label-copies-issue' : undefined}
        oninput={(event) => oncopies(event.currentTarget.value)}
      />
      {#if copiesIssue}
        <span id="hu-label-copies-issue" class="mt-1 block text-xs text-danger" role="alert">
          {copiesIssue}
        </span>
      {/if}
    </label>
    <p class="self-end pb-2 text-xs leading-5 text-foreground-muted">
      En la impresora, usa el mismo papel y escala <strong class="text-foreground"
        >100 % · tamaño real</strong
      >.
    </p>
  </div>
  <p class="text-xs leading-5 text-foreground-muted">
    {#if layout.content === 'qr'}QR de esta unidad, producto, código interno, lote y fechas
      visibles.
    {:else if layout.content === 'barcode'}Code 128 del producto, nombre, lote y fechas visibles.
    {:else}Producto, cantidad, lotes, fecha, presentación, Code 128 y QR.{/if}
  </p>
  <p class="text-xs leading-5 text-foreground-muted">
    Las copias repiten esta etiqueta; no crean otro lote ni cambian las existencias. Elige una
    medida mayor si la vista previa indica que el contenido no cabe.
  </p>
</fieldset>
