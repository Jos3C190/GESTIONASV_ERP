<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { HttpError } from '$lib/api/client';
  import { updateLocationCodeScheme } from '../services';
  import type { LocationCodeScheme, LocationCodeSegment } from '../types';

  interface Props {
    open: boolean;
    warehouseId: string;
    scheme: LocationCodeScheme | null;
    onclose: () => void;
    onsaved: (scheme: LocationCodeScheme) => void;
  }

  let { open, warehouseId, scheme, onclose, onsaved }: Props = $props();
  let name = $state('');
  let separator = $state('-');
  let segments = $state<LocationCodeSegment[]>([]);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let contextKey = $state('');

  const INITIAL_SEGMENTS: LocationCodeSegment[] = [
    { key: 'aisle', label: 'Pasillo', prefix: 'A', width: 2, pad_char: '0', required: true },
    { key: 'rack', label: 'Rack', prefix: 'R', width: 2, pad_char: '0', required: true },
    { key: 'level', label: 'Nivel', prefix: 'N', width: 2, pad_char: '0', required: true },
    { key: 'position', label: 'Posición', prefix: 'P', width: 2, pad_char: '0', required: true }
  ];

  const SEGMENT_EXAMPLES: Record<string, string> = {
    area: 'PICK',
    aisle: '1',
    rack: '1',
    level: '1',
    position: '1'
  };

  function segmentPreview(segment: LocationCodeSegment): string {
    const sample = SEGMENT_EXAMPLES[segment.key] ?? segment.key.toLocaleUpperCase('es');
    const width =
      Number.isInteger(segment.width) && segment.width > 0 ? Math.min(segment.width, 32) : 0;
    const value = width === 0 ? sample : sample.padStart(width, segment.pad_char || '0');
    return `${segment.prefix}${value}`;
  }

  let preview = $derived(segments.map(segmentPreview).join(separator));
  let valid = $derived(
    name.trim().length >= 2 &&
      separator.length >= 1 &&
      separator.length <= 3 &&
      segments.length > 0 &&
      segments.every(
        (segment) =>
          Number.isInteger(segment.width) &&
          segment.width >= 0 &&
          segment.width <= 32 &&
          segment.pad_char.length === 1
      )
  );

  $effect(() => {
    const next = open ? (scheme ? `${scheme.id}:${scheme.version}` : 'initial') : '';
    if (open && next !== contextKey) {
      contextKey = next;
      name = scheme?.name ?? 'Ruta física general';
      separator = scheme?.separator ?? '-';
      segments = scheme
        ? scheme.segments.map((segment) => ({ ...segment }))
        : INITIAL_SEGMENTS.map((segment) => ({ ...segment }));
      error = null;
    }
    if (!open) contextKey = '';
  });

  function updateSegment(index: number, patch: Partial<LocationCodeSegment>) {
    segments = segments.map((segment, current) =>
      current === index ? { ...segment, ...patch } : segment
    );
  }

  async function save() {
    if (!valid) return;
    saving = true;
    error = null;
    try {
      const result = await updateLocationCodeScheme(warehouseId, {
        name: name.trim(),
        separator,
        segments
      });
      onsaved(result);
      onclose();
    } catch (cause) {
      error =
        cause instanceof HttpError
          ? cause.message
          : scheme
            ? 'No se pudo versionar el esquema.'
            : 'No se pudo crear el esquema inicial.';
    } finally {
      saving = false;
    }
  }
</script>

<Modal
  {open}
  size="lg"
  title={scheme ? 'Versionar esquema de códigos' : 'Configurar esquema inicial'}
  {onclose}
>
  <div class="space-y-5">
    {#if scheme}
      <div class="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
        Los códigos ya emitidos no se reescriben. Al guardar se creará la versión {scheme.version +
          1}; las nuevas rutas usarán esa versión.
      </div>
    {:else}
      <div
        class="rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm text-foreground-muted"
      >
        Este almacén aún no tiene un formato de códigos. Se propone una ruta sencilla de pasillo,
        rack, nivel y posición; podrás ajustarla antes de crearla.
      </div>
    {/if}
    {#if error}<div
        class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {error}
      </div>{/if}

    <div class="grid gap-4 sm:grid-cols-[1fr_150px]">
      <FormField id="scheme-name" label="Nombre del esquema" bind:value={name} required />
      <FormField id="scheme-separator" label="Separador" bind:value={separator} required />
    </div>

    <div>
      <h3 class="text-sm font-semibold text-foreground">Segmentos de la ruta</h3>
      <p class="mt-1 text-xs text-foreground-muted">
        El orden es estable y representa la ruta de izquierda a derecha.
      </p>
      <p class="mt-1 text-xs text-foreground-subtle">
        Ancho 0 conserva el valor sin relleno. Para pasillos alfabéticos (A, B, C…), use ancho 0 y
        prefijo vacío; un ancho mayor completa el valor con el carácter de relleno hasta ese mínimo.
      </p>
      <div class="mt-3 space-y-2">
        {#each segments as segment, index (segment.key)}
          <div
            class="grid gap-2 rounded-xl border border-border bg-surface-muted/30 p-3 sm:grid-cols-[minmax(130px,1fr)_100px_100px_90px_auto] sm:items-end"
          >
            <div>
              <p class="text-sm font-medium text-foreground">{segment.label}</p>
            </div>
            <FormField
              id={`scheme-prefix-${segment.key}`}
              label={`${segment.label}: Prefijo`}
              value={segment.prefix}
              oninput={(event) =>
                updateSegment(index, { prefix: (event.currentTarget as HTMLInputElement).value })}
            />
            <FormField
              id={`scheme-width-${segment.key}`}
              label={`${segment.label}: Ancho`}
              type="number"
              min="0"
              max="32"
              step="1"
              value={segment.width}
              oninput={(event) =>
                updateSegment(index, {
                  width: Number((event.currentTarget as HTMLInputElement).value)
                })}
            />
            <FormField
              id={`scheme-pad-${segment.key}`}
              label={`${segment.label}: Carácter de relleno`}
              value={segment.pad_char}
              oninput={(event) =>
                updateSegment(index, {
                  pad_char: (event.currentTarget as HTMLInputElement).value.slice(0, 1)
                })}
            />
            <label class="flex h-[42px] items-center gap-2 text-xs text-foreground-muted">
              <input
                type="checkbox"
                checked={segment.required}
                aria-label={`${segment.label}: Obligatorio`}
                onchange={(event) =>
                  updateSegment(index, { required: event.currentTarget.checked })}
                class="h-4 w-4 rounded border-border accent-primary"
              />
              Obligatorio
            </label>
          </div>
        {/each}
      </div>
    </div>

    <div class="rounded-xl border border-border bg-surface-muted/50 p-4">
      <p class="text-xs uppercase tracking-wide text-foreground-muted">Ejemplo estructural</p>
      <p
        class="mt-2 break-all font-mono text-base font-semibold text-foreground"
        aria-live="polite"
        aria-atomic="true"
      >
        {preview || 'Sin segmentos'}
      </p>
      <p class="mt-1 text-xs text-foreground-subtle">
        El servidor sigue siendo la autoridad del código final y de su normalización.
      </p>
    </div>

    <div class="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
      <Button variant="ghost" onclick={onclose} disabled={saving}>Cancelar</Button>
      <Button onclick={() => void save()} disabled={!valid || saving}
        >{saving
          ? scheme
            ? 'Versionando…'
            : 'Configurando…'
          : scheme
            ? `Crear versión ${scheme.version + 1}`
            : 'Crear esquema inicial'}</Button
      >
    </div>
  </div>
</Modal>
