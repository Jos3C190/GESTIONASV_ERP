<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import { fleetApi } from '$lib/features/fleet/api';
  import { permissions } from '$lib/stores/permissions.svelte';

  let form = $state({
    block_overdue_maintenance: false,
    require_inspection: false,
    block_overweight: false,
    inspection_valid_hours: 24 as number | string,
    document_warning_days: 30 as number | string,
    maintenance_warning_km: 500 as number | string,
    maintenance_warning_days: 7 as number | string
  });
  let loaded = $state(false);
  let error = $state<string | null>(null);
  let saveError = $state<string | null>(null);
  let success = $state<string | null>(null);
  let saving = $state(false);
  let attempted = $state(false);

  const canSave = $derived(permissions.hasPermission('fleet:settings'));
  const canRead = $derived(permissions.hasPermission('fleet:read'));

  function range(value: unknown, min: number, max: number, text: string): string | undefined {
    const number = Number(value);
    return value !== '' &&
      value !== null &&
      Number.isInteger(number) &&
      number >= min &&
      number <= max
      ? undefined
      : text;
  }

  // Apagada la inspección, sus horas no se usan y no deben impedir guardar lo demás.
  const hoursError = $derived(
    form.require_inspection
      ? range(form.inspection_valid_hours, 1, 720, 'Entre 1 y 720 horas, sin decimales.')
      : undefined
  );
  const documentError = $derived(
    range(form.document_warning_days, 0, 365, 'Entre 0 y 365 días, sin decimales.')
  );
  const kmError = $derived(
    range(form.maintenance_warning_km, 0, 100000, 'Entre 0 y 100,000, sin decimales.')
  );
  const daysError = $derived(
    range(form.maintenance_warning_days, 0, 365, 'Entre 0 y 365 días, sin decimales.')
  );

  async function load() {
    error = null;
    try {
      form = await fleetApi.settings();
      loaded = true;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cargar la configuración.';
    }
  }

  onMount(() => {
    if (canRead) void load();
  });

  async function save(event: SubmitEvent) {
    event.preventDefault();
    attempted = true;
    success = null;
    const first = hoursError
      ? 'hours'
      : documentError
        ? 'documents'
        : kmError
          ? 'maintenance-km'
          : daysError
            ? 'maintenance-days'
            : null;
    if (first) {
      await tick();
      document.getElementById(first)?.focus();
      return;
    }
    saving = true;
    saveError = null;
    try {
      form = await fleetApi.saveSettings({
        block_overdue_maintenance: form.block_overdue_maintenance,
        require_inspection: form.require_inspection,
        block_overweight: form.block_overweight,
        inspection_valid_hours:
          range(form.inspection_valid_hours, 1, 720, 'x') === undefined
            ? Number(form.inspection_valid_hours)
            : 24,
        document_warning_days: Number(form.document_warning_days),
        maintenance_warning_km: Number(form.maintenance_warning_km),
        maintenance_warning_days: Number(form.maintenance_warning_days)
      });
      success = 'Se guardó la configuración.';
    } catch (err) {
      saveError = err instanceof HttpError ? err.message : 'No se pudo guardar la configuración.';
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>Reglas de flota | GestionaSV</title>
</svelte:head>

{#if !canRead}
  <div
    class="m-4 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
    role="alert"
  >
    No tienes permiso para ver la flota.
  </div>
{:else}
  <div class="space-y-5 p-4 sm:p-6 md:p-8">
    <a href="/fleet" class="back">← Flota</a>
    <header>
      <h1 class="text-2xl font-bold tracking-tight text-foreground">Reglas de flota</h1>
      <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
        Lo que se exige antes de despachar en esta empresa. Quien tenga el permiso de excepciones
        puede autorizar la salida indicando el motivo.
      </p>
    </header>

    {#if error}
      <div class="failure" role="alert">
        <p>{error}</p>
        <Button size="lg" variant="secondary" onclick={load}>Reintentar</Button>
      </div>
    {:else if !loaded}
      <p class="muted" role="status">Cargando…</p>
    {:else}
      <form class="form" onsubmit={save} novalidate>
        <fieldset class="card" disabled={!canSave}>
          <legend>Antes de despachar</legend>
          <label class="check">
            <input type="checkbox" bind:checked={form.block_overdue_maintenance} />
            <span>
              <strong>Frenar si hay mantenimiento vencido</strong>
              <small>Si está apagado, el mantenimiento vencido solo avisa.</small>
            </span>
          </label>
          <label class="check">
            <input type="checkbox" bind:checked={form.block_overweight} />
            <span>
              <strong>Frenar si la carga supera la capacidad</strong>
              <small>
                Si está apagado, solo avisa. Encendido, avisa también de los productos sin peso.
              </small>
            </span>
          </label>
          <label class="check">
            <input type="checkbox" bind:checked={form.require_inspection} />
            <span>
              <strong>Exigir inspección reciente</strong>
              <small>Sin una inspección dentro del plazo, el despacho pide autorización.</small>
            </span>
          </label>
          {#if form.require_inspection}
            <FormField
              id="hours"
              label="La inspección vale (horas)"
              type="number"
              min="1"
              max="720"
              step="1"
              bind:value={form.inspection_valid_hours}
              error={attempted ? hoursError : undefined}
            />
          {/if}
        </fieldset>

        <fieldset class="card" disabled={!canSave}>
          <legend>Cuándo avisar</legend>
          <FormField
            id="documents"
            label="Documentos y contratos por vencer (días antes)"
            type="number"
            min="0"
            max="365"
            step="1"
            bind:value={form.document_warning_days}
            error={attempted ? documentError : undefined}
          />
          <div class="pair">
            <FormField
              id="maintenance-km"
              label="Mantenimiento próximo (km u horas antes)"
              type="number"
              min="0"
              max="100000"
              step="1"
              bind:value={form.maintenance_warning_km}
              error={attempted ? kmError : undefined}
            />
            <FormField
              id="maintenance-days"
              label="Mantenimiento próximo (días antes)"
              type="number"
              min="0"
              max="365"
              step="1"
              bind:value={form.maintenance_warning_days}
              error={attempted ? daysError : undefined}
            />
          </div>
        </fieldset>

        <p class="muted">
          Siempre se revisa, sin importar estas reglas, que el conductor no esté en otro viaje. Eso
          no admite excepción.
        </p>
        <div role="status">
          {#if success}<p class="success">{success}</p>{/if}
        </div>
        {#if saveError}<p class="error" role="alert">{saveError}</p>{/if}
        {#if canSave}
          <div class="actions">
            <Button size="lg" type="submit" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </Button>
          </div>
        {:else}
          <p class="muted">Solo quien tenga el permiso de configurar flota puede cambiar esto.</p>
        {/if}
      </form>
    {/if}
  </div>
{/if}

<style>
  .back {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  small,
  .muted {
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  small {
    display: block;
    font-weight: 400;
  }
  .form {
    display: grid;
    gap: 16px;
    max-width: 720px;
  }
  .card {
    display: grid;
    gap: 14px;
    min-width: 0;
    padding: 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  legend {
    float: left;
    width: 100%;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 600;
  }
  .check {
    clear: both;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    min-height: 44px;
    color: rgb(var(--foreground));
    font-size: 14px;
  }
  .check strong {
    font-weight: 500;
  }
  .check input {
    width: 20px;
    height: 20px;
    margin-top: 1px;
    flex: none;
  }
  .pair {
    display: grid;
    gap: 14px;
  }
  .form :global(input:not([type='checkbox'])) {
    border-color: rgb(var(--control-border));
    font-size: 16px;
  }
  .success,
  .failure {
    padding: 12px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    font-size: 13px;
  }
  .success {
    border-color: rgb(var(--success) / 0.3);
    background: rgb(var(--success) / 0.1);
    color: rgb(var(--success));
  }
  .failure {
    display: grid;
    gap: 10px;
    justify-items: start;
    border-color: rgb(var(--danger) / 0.3);
    color: rgb(var(--danger));
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
  }
  @media (min-width: 640px) {
    .pair {
      grid-template-columns: 1fr 1fr;
    }
  }
  @media (min-width: 768px) {
    .form :global(input:not([type='checkbox'])) {
      font-size: 13px;
    }
  }
</style>
