<script lang="ts">
  import { tick } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import ImageUpload from '$lib/components/ui/ImageUpload.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    fleetApi,
    type FleetInspection,
    type FleetVehicle,
    type InspectionItem,
    type InspectionResult
  } from './api';
  import { formatDateTime } from './catalog';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();
  let panel = $state<HTMLElement | null>(null);

  type Answer = { passed: boolean | null; notes: string; photo: string };

  let inspections = $state<FleetInspection[]>([]);
  let items = $state<InspectionItem[]>([]);
  let answers = $state<Record<string, Answer>>({});
  let notes = $state('');
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let blockedNotice = $state(false);
  let open = $state(false);
  let starting = $state(false);
  let saving = $state(false);
  let attempted = $state(false);
  let formError = $state<string | null>(null);
  let expanded = $state<string | null>(null);

  const canInspect = $derived(
    permissions.hasPermission('fleet:inspections') && vehicle.status !== 'retired'
  );
  const pending = $derived(
    inspections.flatMap((inspection) =>
      inspection.results
        .filter((result) => result.is_critical && !result.passed && !result.resolved_at)
        .map((result) => ({ result, inspectedAt: inspection.inspected_at }))
    )
  );
  const answered = $derived(Object.values(answers).filter((item) => item.passed !== null).length);
  const criticalFails = $derived(
    items.filter((item) => item.is_critical && answers[item.id]?.passed === false)
  );
  const firstInvalid = $derived(
    items.find(
      (item) =>
        answers[item.id]?.passed === null ||
        (item.is_critical &&
          answers[item.id]?.passed === false &&
          !(answers[item.id] as Answer).notes.trim())
    ) ?? null
  );

  function closeForm() {
    if (answered === 0 && !notes.trim()) {
      open = false;
      return;
    }
    confirmation.request({
      kind: 'revoke',
      title: 'Descartar inspección',
      description: `Se perderá lo revisado: ${answered} de ${items.length} puntos.`,
      confirmLabel: 'Descartar',
      execute: async () => {
        open = false;
      }
    });
  }

  function message(err: unknown, fallback: string): string {
    return err instanceof HttpError ? err.message : fallback;
  }

  async function load() {
    loading = true;
    error = null;
    try {
      inspections = await fleetApi.inspections(vehicle.id);
    } catch (err) {
      error = message(err, 'No se pudieron cargar las inspecciones.');
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void vehicle.id;
    void load();
  });

  async function start() {
    starting = true;
    success = null;
    error = null;
    try {
      items = await fleetApi.inspectionItems();
      if (items.length === 0) {
        error =
          'La empresa no tiene puntos de inspección activos. Agrégalos en Puntos de inspección.';
        return;
      }
      answers = Object.fromEntries(
        items.map((item) => [item.id, { passed: null, notes: '', photo: '' }])
      );
      notes = '';
      attempted = false;
      formError = null;
      open = true;
    } catch (err) {
      error = message(err, 'No se pudo cargar la lista de inspección.');
    } finally {
      starting = false;
    }
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    attempted = true;
    if (firstInvalid) {
      await tick();
      document.getElementById(`point-${firstInvalid.id}`)?.scrollIntoView?.({ block: 'center' });
      // Una falla sin describir pide la nota; enfocar "Bien" invitaría a cambiar la respuesta.
      const missingNote = (answers[firstInvalid.id] as Answer).passed === false;
      document.getElementById(`${missingNote ? 'note' : 'pass'}-${firstInvalid.id}`)?.focus();
      return;
    }
    saving = true;
    formError = null;
    try {
      await fleetApi.addInspection(vehicle.id, {
        driver_id: vehicle.driver?.driver_id ?? null,
        notes: notes.trim() || null,
        results: items.map((item) => ({
          item_id: item.id,
          passed: (answers[item.id] as Answer).passed === true,
          // Si se corrigió a "Bien", la nota y la foto de la falla ya no aplican.
          notes:
            (answers[item.id] as Answer).passed === false
              ? (answers[item.id] as Answer).notes.trim() || null
              : null,
          photo_url:
            (answers[item.id] as Answer).passed === false
              ? (answers[item.id] as Answer).photo || null
              : null
        }))
      });
      open = false;
      await load();
      // El resultado sale de lo que queda pendiente, no solo de esta inspección.
      blockedNotice = pending.length > 0;
      success = pending.length
        ? `Inspección registrada. Hay ${pending.length === 1 ? '1 falla crítica' : `${pending.length} fallas críticas`} sin resolver: el despacho pedirá autorización.`
        : 'Inspección registrada sin fallas críticas.';
      onchanged();
      await tick();
      panel?.scrollIntoView?.({ block: 'start' });
    } catch (err) {
      formError = message(err, 'No se pudo registrar la inspección.');
      await tick();
      document.getElementById('inspection-form-error')?.scrollIntoView?.({ block: 'center' });
    } finally {
      saving = false;
    }
  }

  function askResolve(result: InspectionResult) {
    success = null;
    confirmation.request({
      kind: 'restore',
      title: 'Resolver falla',
      description:
        'Queda registrado quién la resolvió y cómo. Si no quedan otras, el despacho dejará de pedir autorización por esto.',
      resourceName: result.item_name,
      confirmLabel: 'Marcar como resuelta',
      requireReason: true,
      reasonLabel: '¿Cómo se resolvió?',
      execute: async (why) => {
        await fleetApi.resolveInspectionResult(vehicle.id, result.id, why ?? '');
        blockedNotice = false;
        success = 'Falla resuelta.';
        await load();
        onchanged();
      }
    });
  }

  const failures = (inspection: FleetInspection) =>
    inspection.results.filter((result) => !result.passed).length;
</script>

<div class="panel" bind:this={panel}>
  <div class="toolbar">
    <div>
      <h2>Inspección antes de salir</h2>
      <p class="muted">
        Una falla crítica sin resolver frena el despacho; solo sale con la autorización de quien
        tenga ese permiso.
      </p>
    </div>
    {#if canInspect}
      <Button size="lg" class="record" disabled={starting} onclick={start}>
        {starting ? 'Preparando…' : 'Nueva inspección'}
      </Button>
    {/if}
  </div>

  <div role="status">
    {#if success}<p class="success" class:blocked={blockedNotice}>{success}</p>{/if}
  </div>

  {#if pending.length}
    <section class="pending" aria-label="Fallas críticas sin resolver">
      <h3>
        {pending.length === 1 ? '1 falla crítica' : `${pending.length} fallas críticas`} sin resolver
      </h3>
      <ul>
        {#each pending as { result, inspectedAt } (result.id)}
          <li>
            <div>
              <strong>{result.item_name}</strong>
              <small>{formatDateTime(inspectedAt)}{result.notes ? ` · ${result.notes}` : ''}</small>
              {#if result.photo_url}
                <a href={result.photo_url} target="_blank" rel="noopener noreferrer">Ver foto</a>
              {/if}
            </div>
            {#if canInspect}
              <Button size="lg" variant="secondary" onclick={() => askResolve(result)}>
                Resolver
              </Button>
            {/if}
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  {#if error}
    <div class="failure" role="alert">
      <p>{error}</p>
      <Button size="lg" variant="secondary" onclick={load}>Reintentar</Button>
    </div>
  {:else if loading && inspections.length === 0}
    <p class="muted" role="status">Cargando…</p>
  {:else if inspections.length === 0}
    <p class="empty">Este vehículo aún no tiene inspecciones.</p>
  {:else}
    <ul class="history" aria-label="Inspecciones anteriores">
      {#each inspections as inspection (inspection.id)}
        <li>
          <button
            type="button"
            class="summary"
            aria-expanded={expanded === inspection.id}
            onclick={() => (expanded = expanded === inspection.id ? null : inspection.id)}
          >
            <span>
              <strong>{formatDateTime(inspection.inspected_at)}</strong>
              <small>
                {inspection.inspected_by_name ?? '—'} · {failures(inspection) === 0
                  ? 'Sin fallas'
                  : failures(inspection) === 1
                    ? '1 falla'
                    : `${failures(inspection)} fallas`}
              </small>
            </span>
            <span class={`badge ${inspection.passed ? 'pass' : 'fail'}`}>
              {inspection.passed ? 'Apta' : 'No apta'}
            </span>
          </button>
          {#if expanded === inspection.id}
            <ul class="results">
              {#each inspection.results as result (result.id)}
                <li>
                  <span class={result.passed ? 'ok' : 'bad'}
                    >{result.passed ? 'Bien' : 'Falla'}</span
                  >
                  <span>
                    {result.item_name}{result.is_critical ? ' (crítico)' : ''}
                    {#if result.notes}<small>{result.notes}</small>{/if}
                    {#if result.photo_url}
                      <a href={result.photo_url} target="_blank" rel="noopener noreferrer"
                        >Ver foto</a
                      >
                    {/if}
                    {#if result.resolved_at}
                      <small
                        >Resuelta por {result.resolved_by_name ?? '—'}: {result.resolution}</small
                      >
                    {/if}
                  </span>
                </li>
              {/each}
            </ul>
            {#if inspection.notes}<p class="muted notes">{inspection.notes}</p>{/if}
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<Modal {open} title="Nueva inspección" mobileFullScreen preventClose={saving} onclose={closeForm}>
  <form id="inspection-form" class="form" onsubmit={submit} novalidate>
    {#each items as item (item.id)}
      {@const answer = answers[item.id] as Answer}
      {@const unanswered = attempted && answer.passed === null}
      {@const noteMissing =
        attempted && item.is_critical && answer.passed === false && !answer.notes.trim()}
      <fieldset id={`point-${item.id}`} class="point" class:invalid={unanswered || noteMissing}>
        <legend>
          {item.name}
          {#if item.is_critical}<span class="critical">Crítico</span>{/if}
        </legend>
        <div class="choice">
          <button
            type="button"
            id={`pass-${item.id}`}
            class:good={answer.passed === true}
            aria-pressed={answer.passed === true}
            onclick={() => (answer.passed = true)}>Bien</button
          >
          <button
            type="button"
            class:bad-choice={answer.passed === false}
            aria-pressed={answer.passed === false}
            onclick={() => (answer.passed = false)}>Falla</button
          >
        </div>
        {#if unanswered}<small class="message">Marca si está bien o tiene falla.</small>{/if}
        {#if answer.passed === false}
          <label class="details">
            <span>{item.is_critical ? '¿Qué falla?' : '¿Qué falla? (opcional)'}</span>
            <textarea
              rows="2"
              maxlength="500"
              id={`note-${item.id}`}
              bind:value={answer.notes}
              aria-required={item.is_critical ? 'true' : undefined}
              aria-invalid={noteMissing ? 'true' : undefined}
              aria-describedby={noteMissing ? `note-error-${item.id}` : undefined}
            ></textarea>
          </label>
          {#if noteMissing}
            <small id={`note-error-${item.id}`} class="message">Describe la falla.</small>
          {/if}
          <ImageUpload
            id={`photo-${item.id}`}
            label="Foto (opcional)"
            purpose="vehicle_image"
            companyId={company.id}
            bind:value={answer.photo}
            shape="wide"
          />
        {/if}
      </fieldset>
    {/each}
    <label class="details">
      <span>Observaciones (opcional)</span>
      <textarea rows="2" maxlength="1000" bind:value={notes}></textarea>
    </label>
    {#if criticalFails.length}
      <p class="warning" role="status">
        Con {criticalFails.map((item) => item.name).join(', ')} en falla, el despacho pedirá autorización
        hasta resolverlo.
      </p>
    {/if}
    {#if formError}
      <p id="inspection-form-error" class="message" role="alert">{formError}</p>
    {/if}
  </form>
  {#snippet footer()}
    <span class="progress" aria-live="polite">{answered} de {items.length}</span>
    <Button size="lg" variant="secondary" disabled={saving} onclick={closeForm}>Cancelar</Button>
    <Button size="lg" type="submit" form="inspection-form" disabled={saving}>
      {saving ? 'Guardando…' : 'Guardar inspección'}
    </Button>
  {/snippet}
</Modal>

<style>
  .panel {
    display: grid;
    gap: 16px;
    scroll-margin-top: 72px;
  }
  .progress {
    margin-right: auto;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    font-variant-numeric: tabular-nums;
  }
  .results a {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: rgb(var(--primary));
    font-size: 12px;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  .toolbar > div {
    flex: 1 1 220px;
  }
  .toolbar :global(.record) {
    flex: 1 1 100%;
  }
  h2 {
    font-size: 14px;
    font-weight: 600;
  }
  h3 {
    font-size: 13px;
    font-weight: 600;
    color: rgb(var(--danger));
  }
  small,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  small {
    display: block;
  }
  .success,
  .failure,
  .empty {
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
  .success.blocked {
    border-color: rgb(var(--warning) / 0.4);
    background: rgb(var(--warning) / 0.08);
    color: rgb(var(--foreground));
  }
  .failure {
    display: grid;
    gap: 10px;
    justify-items: start;
    border-color: rgb(var(--danger) / 0.3);
    color: rgb(var(--danger));
  }
  .empty {
    background: rgb(var(--surface));
    color: rgb(var(--foreground-muted));
  }
  .pending {
    display: grid;
    gap: 10px;
    padding: 14px;
    border: 1px solid rgb(var(--danger) / 0.35);
    border-radius: 12px;
    background: rgb(var(--danger) / 0.06);
  }
  .pending ul,
  .history,
  .results {
    display: grid;
    gap: 8px;
    list-style: none;
  }
  .pending li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    font-size: 13px;
  }
  .pending li > div {
    flex: 1 1 200px;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .pending a {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: rgb(var(--primary));
    font-size: 12px;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .history > li {
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  .summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    width: 100%;
    min-height: 56px;
    padding: 10px 14px;
    font-size: 13px;
    text-align: left;
  }
  .badge {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
  }
  .pass {
    background: rgb(var(--success) / 0.12);
    color: rgb(var(--success));
  }
  .fail {
    background: rgb(var(--danger) / 0.1);
    color: rgb(var(--danger));
  }
  .results {
    padding: 2px 14px 12px;
  }
  .results li {
    display: grid;
    grid-template-columns: 42px minmax(0, 1fr);
    gap: 8px;
    font-size: 13px;
    overflow-wrap: anywhere;
  }
  .ok {
    color: rgb(var(--success));
    font-weight: 600;
  }
  .bad {
    color: rgb(var(--danger));
    font-weight: 600;
  }
  .notes {
    padding: 0 14px 12px;
  }
  .form {
    display: grid;
    gap: 10px;
  }
  .point {
    display: grid;
    gap: 8px;
    min-width: 0;
    padding: 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
  }
  .point.invalid {
    border-color: rgb(var(--danger) / 0.6);
  }
  legend {
    float: left;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 0;
    font-size: 14px;
    font-weight: 500;
  }
  .choice {
    clear: both;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .choice button {
    min-height: 48px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 10px;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 500;
  }
  .choice .good::before,
  .choice .bad-choice::before {
    content: '✓ ';
  }
  .choice .good {
    border-color: rgb(var(--success));
    background: rgb(var(--success) / 0.14);
    color: rgb(var(--success));
    font-weight: 600;
  }
  .choice .bad-choice {
    border-color: rgb(var(--danger));
    background: rgb(var(--danger) / 0.12);
    color: rgb(var(--danger));
    font-weight: 600;
  }
  .critical {
    padding: 1px 7px;
    border-radius: 999px;
    background: rgb(var(--warning) / 0.14);
    color: rgb(var(--warning));
    font-size: 11px;
    font-weight: 600;
  }
  .details {
    display: grid;
    gap: 4px;
    font-size: 13px;
    font-weight: 500;
  }
  textarea {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 16px;
    font-weight: 400;
  }
  .message {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .warning {
    padding: 10px 12px;
    border: 1px solid rgb(var(--warning) / 0.4);
    border-radius: 10px;
    background: rgb(var(--warning) / 0.08);
    font-size: 13px;
  }
  @media (min-width: 640px) {
    .toolbar :global(.record) {
      flex: 0 0 auto;
    }
  }
  @media (min-width: 768px) {
    textarea {
      font-size: 13px;
    }
  }
</style>
