<script lang="ts">
  import { tick } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { driversApi, type Driver } from '$lib/features/drivers/api';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    fleetApi,
    type FleetIncident,
    type FleetVehicle,
    type IncidentKind,
    type IncidentResponsible,
    type IncidentSeverity,
    type IncidentStatus
  } from './api';
  import {
    formatDateTime,
    formatMoney,
    INCIDENT_KIND_LABELS,
    INCIDENT_RESPONSIBLE_LABELS,
    INCIDENT_SEVERITY_LABELS,
    INCIDENT_STATUS_LABELS,
    localDateTime
  } from './catalog';
  import ReceiptField from './ReceiptField.svelte';
  import ReceiptLink from './ReceiptLink.svelte';

  let { vehicle, onchanged }: { vehicle: FleetVehicle; onchanged: () => void } = $props();
  let panel = $state<HTMLElement | null>(null);

  const options = <T extends string>(labels: Record<T, string>, blank?: string) => [
    ...(blank ? [{ value: '', label: blank }] : []),
    ...(Object.keys(labels) as T[]).map((value) => ({ value, label: labels[value] }))
  ];
  const kindOptions = options(INCIDENT_KIND_LABELS, 'Elige el tipo');
  const severityOptions = options(INCIDENT_SEVERITY_LABELS, 'Elige la gravedad');
  const responsibleOptions = options(INCIDENT_RESPONSIBLE_LABELS);
  const statusOptions = options(INCIDENT_STATUS_LABELS);

  let incidents = $state<FleetIncident[]>([]);
  let drivers = $state<Driver[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let saving = $state(false);
  let attempted = $state(false);
  let formError = $state<string | null>(null);
  let createOpen = $state(false);
  let form = $state(blank());
  let followed = $state<FleetIncident | null>(null);
  let follow = $state({
    status: 'open' as IncidentStatus,
    responsible: 'unknown' as IncidentResponsible,
    cost: '',
    insurance_claim: '',
    resolution: '',
    document_id: ''
  });

  const canRecord = $derived(permissions.hasPermission('fleet:incidents'));
  const open = $derived(incidents.filter((item) => item.status !== 'closed').length);
  const serious = $derived(form.kind === 'theft' || form.severity === 'severe');
  const onRoad = $derived(vehicle.operational_status === 'in_route');
  const canStop = $derived(serious && vehicle.status === 'active' && !onRoad);
  const dirty = $derived(
    Boolean(
      form.kind ||
      form.severity ||
      form.description.trim() ||
      form.location.trim() ||
      form.cost ||
      form.insurance_claim.trim() ||
      form.document_id
    )
  );
  const kindError = $derived(form.kind ? undefined : 'Elige el tipo.');
  const severityError = $derived(form.severity ? undefined : 'Elige la gravedad.');
  const dateError = $derived(form.occurred_at ? undefined : 'Indica la fecha y hora.');
  const descriptionError = $derived(
    form.description.trim().length >= 3 ? undefined : 'Describe qué pasó.'
  );
  const costError = $derived(moneyError(form.cost));
  const followCostError = $derived(moneyError(follow.cost));
  const resolutionError = $derived(
    follow.status === 'closed' && follow.resolution.trim().length < 3
      ? 'Indica cómo se resolvió.'
      : undefined
  );

  function closeCreate() {
    if (!dirty) {
      createOpen = false;
      return;
    }
    confirmation.request({
      kind: 'revoke',
      title: 'Descartar incidente',
      description: 'Se perderá lo que escribiste en este formulario.',
      confirmLabel: 'Descartar',
      execute: async () => {
        createOpen = false;
      }
    });
  }

  async function showResult() {
    await tick();
    panel?.scrollIntoView?.({ block: 'start' });
  }

  async function showFormError(id: string) {
    await tick();
    document.getElementById(id)?.scrollIntoView?.({ block: 'center' });
  }

  function moneyError(value: unknown): string | undefined {
    if (value === '' || value === null || value === undefined) return undefined;
    return /^\d{1,8}(\.\d{1,2})?$/.test(String(value)) ? undefined : 'Monto con hasta 2 decimales.';
  }

  function blank() {
    return {
      kind: '' as IncidentKind | '',
      severity: '' as IncidentSeverity | '',
      responsible: 'unknown' as IncidentResponsible,
      occurred_at: localDateTime(new Date()),
      location: '',
      description: '',
      driver_id: '',
      cost: '',
      insurance_claim: '',
      document_id: '',
      take_out_of_service: true
    };
  }

  function message(err: unknown, fallback: string): string {
    return err instanceof HttpError ? err.message : fallback;
  }

  async function load() {
    loading = true;
    error = null;
    try {
      incidents = await fleetApi.incidents(vehicle.id);
    } catch (err) {
      error = message(err, 'No se pudieron cargar los incidentes.');
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void vehicle.id;
    void load();
  });

  async function openCreate() {
    form = blank();
    attempted = false;
    formError = null;
    success = null;
    createOpen = true;
    if (permissions.hasPermission('drivers:read') && drivers.length === 0) {
      try {
        drivers = (await driversApi.forBranch(vehicle.branch_id)).items;
      } catch {
        drivers = [];
      }
    }
    form.driver_id = vehicle.driver?.driver_id ?? '';
  }

  async function submitCreate(event: SubmitEvent) {
    event.preventDefault();
    attempted = true;
    const firstInvalid = kindError
      ? 'incident-kind'
      : severityError
        ? 'incident-severity'
        : dateError
          ? 'incident-date'
          : descriptionError
            ? 'incident-description'
            : costError
              ? 'incident-cost'
              : null;
    if (firstInvalid) {
      await tick();
      document.getElementById(firstInvalid)?.focus();
      return;
    }
    saving = true;
    formError = null;
    try {
      const saved = await fleetApi.addIncident(vehicle.id, {
        kind: form.kind as IncidentKind,
        severity: form.severity as IncidentSeverity,
        responsible: form.responsible,
        occurred_at: new Date(form.occurred_at).toISOString(),
        location: form.location.trim() || null,
        description: form.description.trim(),
        driver_id: form.driver_id || null,
        cost: form.cost === '' || form.cost === null ? null : String(form.cost),
        insurance_claim: form.insurance_claim.trim() || null,
        document_id: form.document_id || null,
        take_out_of_service: canStop && form.take_out_of_service
      });
      const stopped = saved.vehicle_taken_out === true;
      success = stopped
        ? 'Incidente registrado. El vehículo quedó fuera de servicio.'
        : 'Incidente registrado.';
      createOpen = false;
      await load();
      if (stopped) onchanged();
      void showResult();
    } catch (err) {
      formError = message(err, 'No se pudo registrar el incidente.');
      void showFormError('incident-form-error');
    } finally {
      saving = false;
    }
  }

  function openFollow(incident: FleetIncident) {
    followed = incident;
    follow = {
      status: incident.status,
      responsible: incident.responsible,
      cost: incident.cost ? String(Number(incident.cost)) : '',
      insurance_claim: incident.insurance_claim ?? '',
      resolution: incident.resolution ?? '',
      document_id: incident.document_id ?? ''
    };
    attempted = false;
    formError = null;
    success = null;
  }

  async function submitFollow(event: SubmitEvent) {
    event.preventDefault();
    const target = followed;
    if (!target) return;
    attempted = true;
    if (followCostError || resolutionError) {
      await tick();
      document.getElementById(followCostError ? 'follow-cost' : 'follow-resolution')?.focus();
      return;
    }
    saving = true;
    formError = null;
    try {
      await fleetApi.updateIncident(vehicle.id, target.id, {
        status: follow.status,
        responsible: follow.responsible,
        cost: follow.cost === '' || follow.cost === null ? null : String(follow.cost),
        insurance_claim: follow.insurance_claim.trim() || null,
        document_id: follow.document_id || null,
        ...(follow.status === 'closed' ? { resolution: follow.resolution.trim() } : {})
      });
      success = 'Incidente actualizado.';
      followed = null;
      await load();
    } catch (err) {
      formError = message(err, 'No se pudo actualizar el incidente.');
      void showFormError('follow-form-error');
    } finally {
      saving = false;
    }
  }
</script>

<div class="panel" bind:this={panel}>
  <div class="toolbar">
    <div>
      <h2>Incidentes</h2>
      <p class="muted">
        Accidentes, robos, multas y daños. {#if !loading && !error}{open === 1
            ? '1 sin cerrar.'
            : `${open} sin cerrar.`}{/if}
      </p>
    </div>
    {#if canRecord}
      <Button size="lg" class="record" onclick={openCreate}>Registrar incidente</Button>
    {/if}
  </div>

  <div role="status">
    {#if success}<p class="success">{success}</p>{/if}
  </div>

  {#if error}
    <div class="failure" role="alert">
      <p>{error}</p>
      <Button size="lg" variant="secondary" onclick={load}>Reintentar</Button>
    </div>
  {:else if loading && incidents.length === 0}
    <p class="muted" role="status">Cargando…</p>
  {:else if incidents.length === 0}
    <p class="empty">Este vehículo no tiene incidentes registrados.</p>
  {:else}
    <ul class="incidents">
      {#each incidents as incident (incident.id)}
        <li>
          <div class="line">
            <strong>{INCIDENT_KIND_LABELS[incident.kind]}</strong>
            <span class={`badge ${incident.status}`}>{INCIDENT_STATUS_LABELS[incident.status]}</span
            >
          </div>
          <small>
            {formatDateTime(incident.occurred_at)} · Gravedad {INCIDENT_SEVERITY_LABELS[
              incident.severity
            ].toLowerCase()}{incident.location ? ` · ${incident.location}` : ''}
          </small>
          <p>{incident.description}</p>
          <small>
            Responsable: {INCIDENT_RESPONSIBLE_LABELS[incident.responsible]}{incident.driver_name
              ? ` · Conductor: ${incident.driver_name}`
              : ''}{incident.cost
              ? ` · Costo: ${formatMoney(incident.cost)}`
              : ''}{incident.insurance_claim ? ` · Reclamo: ${incident.insurance_claim}` : ''}
          </small>
          {#if incident.status === 'closed'}
            <small>Cerrado por {incident.closed_by_name ?? '—'}: {incident.resolution}</small>
          {/if}
          <div class="row-actions">
            {#if incident.document_id}
              <ReceiptLink
                vehicleId={vehicle.id}
                documentId={incident.document_id}
                label="Ver documento"
              />
            {/if}
            {#if canRecord}
              <button
                type="button"
                aria-label={`Dar seguimiento a ${INCIDENT_KIND_LABELS[incident.kind]} del ${formatDateTime(incident.occurred_at)}`}
                onclick={() => openFollow(incident)}>Dar seguimiento</button
              >
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<Modal
  open={createOpen}
  title="Registrar incidente"
  mobileFullScreen
  preventClose={saving}
  onclose={closeCreate}
>
  <form id="incident-form" class="form" onsubmit={submitCreate} novalidate>
    <div class="pair">
      <FormField
        id="incident-kind"
        label="Tipo"
        type="select"
        bind:value={form.kind}
        options={kindOptions}
        required
        error={attempted ? kindError : undefined}
      />
      <FormField
        id="incident-severity"
        label="Gravedad"
        type="select"
        bind:value={form.severity}
        options={severityOptions}
        required
        error={attempted ? severityError : undefined}
      />
    </div>
    <FormField
      id="incident-date"
      label="Fecha y hora"
      type="datetime-local"
      bind:value={form.occurred_at}
      required
      error={attempted ? dateError : undefined}
    />
    <div class="field">
      <label for="incident-description">¿Qué pasó? <span class="required">*</span></label>
      <textarea
        id="incident-description"
        rows="3"
        maxlength="4000"
        bind:value={form.description}
        aria-invalid={attempted && descriptionError ? 'true' : undefined}
        aria-describedby={attempted && descriptionError ? 'incident-description-error' : undefined}
      ></textarea>
      {#if attempted && descriptionError}
        <small id="incident-description-error" class="invalid">{descriptionError}</small>
      {/if}
    </div>
    {#if canStop}
      <label class="stop">
        <input type="checkbox" bind:checked={form.take_out_of_service} />
        <span>
          <strong>Poner el vehículo fuera de servicio</strong>
          <small>No podrá despacharse hasta que alguien lo reactive.</small>
        </span>
      </label>
    {/if}
    {#if serious && onRoad}
      <p class="note" role="status">
        Está en un traslado: el incidente se registra, pero podrás ponerlo fuera de servicio cuando
        el traslado termine.
      </p>
    {/if}
    <FormField
      id="incident-location"
      label="Lugar (opcional)"
      bind:value={form.location}
      maxlength={200}
    />
    <div class="pair">
      <FormField
        id="incident-responsible"
        label="Responsable"
        type="select"
        bind:value={form.responsible}
        options={responsibleOptions}
      />
      {#if drivers.length}
        <div class="field">
          <label for="incident-driver">Conductor (opcional)</label>
          <select id="incident-driver" bind:value={form.driver_id}>
            <option value="">Sin conductor</option>
            {#each drivers as driver (driver.id)}
              <option value={driver.id}>{driver.employee.name}</option>
            {/each}
          </select>
        </div>
      {/if}
    </div>
    <div class="pair">
      <FormField
        id="incident-cost"
        label="Costo en USD (opcional)"
        type="number"
        min="0"
        step="0.01"
        bind:value={form.cost}
        error={attempted ? costError : undefined}
      />
      <FormField
        id="incident-claim"
        label="Reclamo al seguro (opcional)"
        bind:value={form.insurance_claim}
        maxlength={80}
      />
    </div>
    <ReceiptField
      id="incident-document"
      label="Documento o foto (opcional)"
      noun="documento"
      vehicleId={vehicle.id}
      bind:value={form.document_id}
    />
    {#if formError}<p id="incident-form-error" class="error" role="alert">{formError}</p>{/if}
  </form>
  {#snippet footer()}
    <Button size="lg" variant="secondary" disabled={saving} onclick={closeCreate}>Cancelar</Button>
    <Button size="lg" type="submit" form="incident-form" disabled={saving}>
      {saving ? 'Registrando…' : 'Registrar'}
    </Button>
  {/snippet}
</Modal>

<Modal
  open={followed !== null}
  title="Seguimiento del incidente"
  mobileFullScreen
  preventClose={saving}
  onclose={() => (followed = null)}
>
  <form id="follow-form" class="form" onsubmit={submitFollow} novalidate>
    {#if followed}
      <div class="context">
        <strong>
          {INCIDENT_KIND_LABELS[followed.kind]} · {formatDateTime(followed.occurred_at)}
        </strong>
        <small>{followed.description}</small>
      </div>
    {/if}
    <div class="pair">
      <FormField
        id="follow-status"
        label="Estado"
        type="select"
        bind:value={follow.status}
        options={statusOptions}
      />
      <FormField
        id="follow-responsible"
        label="Responsable"
        type="select"
        bind:value={follow.responsible}
        options={responsibleOptions}
      />
    </div>
    {#if followed?.status === 'closed' && follow.status !== 'closed'}
      <p class="note" role="status">Al reabrirlo se borrará la resolución guardada.</p>
    {/if}
    {#if follow.status === 'closed'}
      <div class="field">
        <label for="follow-resolution">¿Cómo se resolvió? <span class="required">*</span></label>
        <textarea
          id="follow-resolution"
          rows="3"
          maxlength="1000"
          bind:value={follow.resolution}
          aria-invalid={attempted && resolutionError ? 'true' : undefined}
          aria-describedby={attempted && resolutionError ? 'follow-resolution-error' : undefined}
        ></textarea>
        {#if attempted && resolutionError}
          <small id="follow-resolution-error" class="invalid">{resolutionError}</small>
        {/if}
      </div>
    {/if}
    <div class="pair">
      <FormField
        id="follow-cost"
        label="Costo en USD (opcional)"
        type="number"
        min="0"
        step="0.01"
        bind:value={follow.cost}
        error={attempted ? followCostError : undefined}
      />
      <FormField
        id="follow-claim"
        label="Reclamo al seguro (opcional)"
        bind:value={follow.insurance_claim}
        maxlength={80}
      />
    </div>
    <ReceiptField
      id="follow-document"
      label="Documento o foto (opcional)"
      noun="documento"
      vehicleId={vehicle.id}
      bind:value={follow.document_id}
    />
    {#if formError}<p id="follow-form-error" class="error" role="alert">{formError}</p>{/if}
  </form>
  {#snippet footer()}
    <Button size="lg" variant="secondary" disabled={saving} onclick={() => (followed = null)}>
      Cancelar
    </Button>
    <Button size="lg" type="submit" form="follow-form" disabled={saving}>
      {saving ? 'Guardando…' : 'Guardar'}
    </Button>
  {/snippet}
</Modal>

<style>
  .panel {
    display: grid;
    gap: 16px;
    scroll-margin-top: 72px;
  }
  .note,
  .context {
    padding: 10px 12px;
    border-radius: 10px;
    font-size: 13px;
  }
  .note {
    border: 1px solid rgb(var(--warning) / 0.4);
    background: rgb(var(--warning) / 0.08);
  }
  .context {
    display: grid;
    gap: 2px;
    background: rgb(var(--surface-hover));
    overflow-wrap: anywhere;
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
  small,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
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
  .incidents {
    display: grid;
    gap: 10px;
    list-style: none;
  }
  .incidents li {
    display: grid;
    gap: 4px;
    padding: 12px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  .incidents p {
    font-size: 13px;
    overflow-wrap: anywhere;
    white-space: pre-line;
  }
  .line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 13px;
  }
  .badge {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
  }
  .open {
    background: rgb(var(--danger) / 0.1);
    color: rgb(var(--danger));
  }
  .in_review {
    background: rgb(var(--warning) / 0.14);
    color: rgb(var(--warning));
  }
  .closed {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground-muted));
  }
  .row-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 14px;
  }
  .row-actions button {
    min-height: 44px;
    color: rgb(var(--primary));
    font-size: 12px;
    font-weight: 500;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .form {
    display: grid;
    gap: 12px;
  }
  .pair {
    display: grid;
    gap: 12px;
  }
  .field {
    display: grid;
    gap: 4px;
    font-size: 14px;
    font-weight: 500;
  }
  .required {
    color: rgb(var(--danger));
  }
  .invalid {
    color: rgb(var(--danger));
    font-weight: 400;
  }
  textarea,
  select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 16px;
    font-weight: 400;
  }
  select {
    min-height: 44px;
    padding-block: 0;
  }
  .form :global(input:not([type='checkbox'])),
  .form :global(select) {
    border-color: rgb(var(--control-border));
    font-size: 16px;
    font-weight: 400;
  }
  .stop {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px;
    border: 1px solid rgb(var(--warning) / 0.4);
    border-radius: 10px;
    background: rgb(var(--warning) / 0.08);
    font-size: 13px;
  }
  .stop input {
    width: 20px;
    height: 20px;
    margin-top: 1px;
    flex: none;
  }
  .stop span {
    display: grid;
    gap: 2px;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  @media (min-width: 640px) {
    .toolbar :global(.record) {
      flex: 0 0 auto;
    }
    .pair {
      grid-template-columns: 1fr 1fr;
    }
  }
  @media (min-width: 768px) {
    textarea,
    select,
    .form :global(input:not([type='checkbox'])),
    .form :global(select) {
      font-size: 13px;
    }
  }
</style>
