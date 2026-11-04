<script lang="ts">
  import { goto } from '$app/navigation';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import OwnedDocumentsPanel from '$lib/features/documents/components/OwnedDocumentsPanel.svelte';
  import {
    formatDate,
    formatDateTime,
    plateLabel,
    LICENSE_LABELS,
    INCIDENT_KIND_LABELS,
    INCIDENT_STATUS_LABELS,
    type LicenseClass
  } from '$lib/features/fleet/catalog';
  import { fleetApi, type FleetIncident } from '$lib/features/fleet/api';
  import ComplianceList from '$lib/features/fleet/ComplianceList.svelte';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import ImageLightbox from '$lib/features/fleet/ImageLightbox.svelte';
  import MoveToTrashDialog from '$lib/features/fleet/MoveToTrashDialog.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import LicenseCaptureEntry from './capture/LicenseCaptureEntry.svelte';
  import {
    DRIVER_STATUS_META,
    driversApi,
    type Assignment,
    type Driver,
    type DriverStatus,
    type DriverTrip
  } from './api';

  let { driverId }: { driverId: string } = $props();

  type Tab = 'summary' | 'license' | 'history';
  let driver = $state<Driver | null>(null);
  let assignments = $state<Assignment[]>([]);
  let trips = $state<DriverTrip[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let tab = $state<Tab>('summary');
  let incidents = $state<FleetIncident[]>([]);
  let incidentsError = $state(false);

  let modal = $state<'edit' | 'status' | 'branch' | null>(null);
  let trashOpen = $state(false);
  let licenseClass = $state<LicenseClass>('liviana');
  let notes = $state('');
  let nextStatus = $state<DriverStatus>('active');
  let targetBranch = $state('');
  let reason = $state('');
  let saving = $state(false);
  let actionError = $state<string | null>(null);
  let backUrl = $state<string | null>(null);
  let backIndex = $state(0);
  let backLoading = $state(false);
  let backError = $state<string | null>(null);
  let backOrigin: HTMLElement | null = null;

  const canUpdate = $derived(permissions.hasPermission('drivers:update'));
  // El reverso lleva datos de salud: solo lo abre quien gestiona licencias.
  const canSeeBack = $derived(permissions.hasPermission('drivers:documents'));
  // La papelera es administrativa: requiere alcance de todas las sucursales.
  const canDelete = $derived(
    permissions.hasPermission('drivers:delete') && branch.accessAllBranches
  );
  const licenseOptions = Object.keys(LICENSE_LABELS) as LicenseClass[];
  const statusOptions = $derived(
    (['active', 'suspended', 'inactive'] as const).filter((item) => item !== driver?.status)
  );
  const branchOptions = $derived(branch.branches.filter((item) => item.id !== driver?.branch_id));

  async function loadIncidents() {
    incidentsError = false;
    try {
      incidents = await fleetApi.driverIncidents(driverId);
    } catch {
      incidentsError = true;
    }
  }

  async function openBack() {
    if (!driver || backLoading) return;
    backOrigin = document.activeElement as HTMLElement | null;
    backLoading = true;
    backError = null;
    try {
      backUrl = (await driversApi.licenseBackPreview(driver.id)).url;
      backIndex = 0;
    } catch (err) {
      backError =
        err instanceof HttpError && err.status === 404
          ? 'Esta licencia no tiene reverso registrado.'
          : 'No se pudo abrir el reverso. Inténtalo de nuevo.';
    } finally {
      backLoading = false;
    }
  }

  async function load() {
    loading = true;
    error = null;
    try {
      const [profile, history, travelled] = await Promise.all([
        driversApi.get(driverId),
        driversApi.assignments(driverId),
        driversApi.trips(driverId)
      ]);
      driver = profile;
      assignments = history;
      trips = travelled;
      void loadIncidents();
    } catch (err) {
      error =
        err instanceof HttpError && err.status === 404
          ? 'El conductor no existe o pertenece a otra sucursal.'
          : err instanceof HttpError
            ? err.message
            : 'No se pudo cargar el conductor.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void driverId;
    void load();
  });

  function open(kind: 'edit' | 'status' | 'branch') {
    actionError = null;
    reason = '';
    if (kind === 'edit' && driver) {
      licenseClass = driver.license.license_class;
      notes = driver.notes ?? '';
    }
    if (kind === 'status') nextStatus = statusOptions[0] ?? 'active';
    if (kind === 'branch') targetBranch = branchOptions[0]?.id ?? '';
    modal = kind;
  }

  async function run(action: () => Promise<Driver>) {
    saving = true;
    actionError = null;
    try {
      driver = await action();
      modal = null;
      assignments = await driversApi.assignments(driverId);
    } catch (err) {
      actionError = err instanceof HttpError ? err.message : 'No se pudo completar la acción.';
    } finally {
      saving = false;
    }
  }
</script>

{#if loading && !driver}
  <div class="state">Cargando conductor…</div>
{:else if error || !driver}
  <div class="state error" role="alert">
    <p>{error}</p>
    <Button variant="secondary" size="sm" onclick={() => goto('/drivers')}
      >Volver a Conductores</Button
    >
  </div>
{:else}
  <div class="profile">
    <header class="hero">
      {#if driver.employee.photo_url}
        <img class="photo" src={driver.employee.photo_url} alt="" />
      {:else}
        <span class="photo initials">{driver.employee.initials}</span>
      {/if}
      <div class="hero-body">
        <a class="back" href="/drivers"><FleetIcon name="chevronLeft" size={14} />Conductores</a>
        <div class="title">
          <h1>{driver.employee.name}</h1>
          <span class="pill {DRIVER_STATUS_META[driver.status].tone}"
            >{DRIVER_STATUS_META[driver.status].label}</span
          >
        </div>
        <p class="meta">
          {driver.employee.code}
          <span>·</span>{driver.employee.position ?? 'Sin puesto'}
          <span>·</span><FleetIcon name="pin" size={13} />{driver.branch_name}
        </p>
        <p class="meta">
          Licencia {LICENSE_LABELS[driver.license.license_class]}
          {#if driver.license.number}<span>·</span>N.º {driver.license.number}{/if}
          <span>·</span>{driver.license.expires_on
            ? `vence ${formatDate(driver.license.expires_on)}`
            : 'sin licencia cargada'}
        </p>
        {#if driver.status !== 'active' && driver.status_reason}
          <p class="reason">Motivo: {driver.status_reason}</p>
        {/if}
        {#if canUpdate}
          <div class="actions">
            <Button size="sm" variant="secondary" onclick={() => open('edit')}>Editar</Button>
            <Button size="sm" variant="secondary" onclick={() => open('status')}
              >Cambiar estado</Button
            >
            {#if branchOptions.length}
              <Button size="sm" variant="secondary" onclick={() => open('branch')}
                >Cambiar sucursal</Button
              >
            {/if}
            <Button
              size="sm"
              variant="ghost"
              onclick={() => goto(`/employees/${driver!.employee.id}`)}>Ver empleado</Button
            >
            {#if canDelete}
              <Button size="sm" variant="ghost" onclick={() => (trashOpen = true)}
                >Mover a papelera</Button
              >
            {/if}
          </div>
        {/if}
      </div>
    </header>

    <MoveToTrashDialog
      open={trashOpen}
      title="Mover conductor a la papelera"
      resource="drivers"
      recordId={driver.id}
      description={`Se retira el perfil de conductor de ${driver.employee.name}; el empleado no se modifica. Debe estar sin vehículo asignado y sin traslados en ruta.`}
      onclose={() => (trashOpen = false)}
      ondone={() => goto('/drivers')}
    />

    <nav class="tabs" aria-label="Secciones del conductor">
      <button
        type="button"
        class:active={tab === 'summary'}
        aria-pressed={tab === 'summary'}
        onclick={() => (tab = 'summary')}>Resumen</button
      >
      <button
        type="button"
        class:active={tab === 'license'}
        aria-pressed={tab === 'license'}
        onclick={() => (tab = 'license')}>Licencia</button
      >
      <button
        type="button"
        class:active={tab === 'history'}
        aria-pressed={tab === 'history'}
        onclick={() => (tab = 'history')}>Vehículos y viajes</button
      >
    </nav>

    {#if tab === 'summary'}
      <div class="grid">
        <section class="card">
          <h2>Aptitud para conducir</h2>
          <ComplianceList compliance={driver.compliance} />
        </section>
        <section class="card">
          <h2>Vehículo asignado</h2>
          {#if driver.vehicle}
            <a class="link-row" href={`/fleet/${driver.vehicle.vehicle_id}`}>
              <FleetIcon name="truck" size={18} />
              <span
                ><strong>{driver.vehicle.code} · {plateLabel(driver.vehicle.plate)}</strong><small
                  >{driver.vehicle.kind_name} · desde {formatDate(driver.vehicle.since)}</small
                ></span
              >
              <FleetIcon name="chevron" size={14} />
            </a>
          {:else}
            <p class="muted">
              Sin vehículo asignado. La asignación se hace desde la ficha del vehículo.
            </p>
          {/if}
          <h2 class="spaced">Contacto</h2>
          <dl class="specs">
            <div>
              <dt>DUI</dt>
              <dd>{driver.employee.document_id ?? '—'}</dd>
            </div>
            <div>
              <dt>Teléfono</dt>
              <dd>{driver.employee.phone ?? '—'}</dd>
            </div>
          </dl>
          {#if driver.notes}<p class="notes">{driver.notes}</p>{/if}
        </section>
      </div>
    {:else if tab === 'license'}
      {#if backUrl}
        <ImageLightbox
          images={[{ src: backUrl, alt: 'Reverso de la licencia' }]}
          bind:index={backIndex}
          title="Reverso de la licencia"
          onclose={() => {
            backUrl = null;
            requestAnimationFrame(() => backOrigin?.focus());
          }}
        />
      {/if}
      {#if driver.license.document_id}
        <section class="card license-data">
          <h2>Datos de la licencia</h2>
          <dl class="specs">
            <div>
              <dt>Clase</dt>
              <dd>{LICENSE_LABELS[driver.license.license_class]}</dd>
            </div>
            <div>
              <dt>Número</dt>
              <dd>{driver.license.number ?? '—'}</dd>
            </div>
            <div>
              <dt>Expedición</dt>
              <dd>{formatDate(driver.license.issued_on)}</dd>
            </div>
            <div>
              <dt>Vence</dt>
              <dd>{formatDate(driver.license.expires_on)}</dd>
            </div>
            <div>
              <dt>Número de control</dt>
              <dd>{driver.license.control_number ?? '—'}</dd>
            </div>
          </dl>
          {#if canSeeBack}
            <div class="license-back">
              <Button variant="secondary" disabled={backLoading} onclick={() => void openBack()}>
                <FleetIcon name="image" size={16} />{backLoading ? 'Abriendo…' : 'Ver reverso'}
              </Button>
              <small>Contiene datos de salud.</small>
            </div>
            {#if backError}<p class="back-error" role="alert">{backError}</p>{/if}
          {/if}
        </section>
      {/if}
      <LicenseCaptureEntry {driver} onconfirmed={() => void load()} />
      <OwnedDocumentsPanel
        owner={driversApi.documents(driver.id)}
        title="Licencia de conducir"
        description="Licencia registrada con la captura guiada. Se guarda en el expediente del empleado y una licencia vencida impide conducir."
        readOnly
        emptyHint="La licencia se registra con la captura guiada: usa el botón de fotos."
        permissionCodes={{
          read: 'drivers:read',
          upload: 'drivers:documents',
          update: 'drivers:documents',
          download: 'drivers:read'
        }}
        onchanged={load}
      />
    {:else}
      <div class="grid">
        <section class="card">
          <h2>Historial de vehículos</h2>
          {#if assignments.length === 0}
            <p class="muted">Aún no ha tenido vehículos asignados.</p>
          {:else}
            <ol class="timeline">
              {#each assignments as item (item.id)}
                <li>
                  <strong>{item.vehicle_code} · {plateLabel(item.vehicle_plate)}</strong>
                  <small
                    >{formatDate(item.starts_at)} — {item.ends_at
                      ? formatDate(item.ends_at)
                      : 'actual'}</small
                  >
                  {#if item.end_reason}<small>{item.end_reason}</small>{/if}
                </li>
              {/each}
            </ol>
          {/if}
        </section>
        <section class="card">
          <h2>Incidentes</h2>
          {#if incidentsError}
            <p class="muted" role="alert">No se pudieron cargar los incidentes.</p>
          {:else if incidents.length === 0}
            <p class="muted">Sin incidentes registrados.</p>
          {:else}
            <ol class="timeline">
              {#each incidents as incident (incident.id)}
                <li>
                  <a href={`/fleet/${incident.vehicle_id}?tab=incidents`}>
                    <strong>
                      {INCIDENT_KIND_LABELS[incident.kind]} · {incident.vehicle_code}
                    </strong>
                  </a>
                  <small>
                    {formatDate(incident.occurred_at)} · {INCIDENT_STATUS_LABELS[incident.status]}
                  </small>
                </li>
              {/each}
            </ol>
          {/if}
        </section>
        <section class="card">
          <h2>Viajes</h2>
          {#if trips.length === 0}
            <p class="muted">Sin traslados registrados como conductor.</p>
          {:else}
            <ol class="timeline">
              {#each trips as trip (trip.transfer_id)}
                <li>
                  <strong>{trip.code}</strong>
                  <small>{trip.origin_branch} → {trip.destination_branch}</small>
                  <small
                    >{trip.vehicle_code ?? 'Sin vehículo'} · salió {formatDateTime(
                      trip.dispatched_at
                    )}</small
                  >
                </li>
              {/each}
            </ol>
          {/if}
        </section>
      </div>
    {/if}
  </div>

  <Modal open={modal === 'edit'} title="Editar conductor" onclose={() => (modal = null)}>
    <div class="modal-body">
      <label>
        <span>Clase de licencia</span>
        <select bind:value={licenseClass}>
          {#each licenseOptions as option (option)}
            <option value={option}>{LICENSE_LABELS[option]}</option>
          {/each}
        </select>
      </label>
      <label>
        <span>Notas</span>
        <textarea bind:value={notes} rows="3" maxlength="2000"></textarea>
      </label>
      {#if actionError}<p class="error-text" role="alert">{actionError}</p>{/if}
      <div class="modal-actions">
        <Button variant="secondary" onclick={() => (modal = null)}>Cancelar</Button>
        <Button
          disabled={saving}
          onclick={() =>
            run(() =>
              driversApi.update(driver!.id, {
                license_class: licenseClass,
                notes: notes.trim() || null
              })
            )}>Guardar</Button
        >
      </div>
    </div>
  </Modal>

  <Modal open={modal === 'status'} title="Cambiar estado" onclose={() => (modal = null)}>
    <div class="modal-body">
      <label>
        <span>Nuevo estado</span>
        <select bind:value={nextStatus}>
          {#each statusOptions as option (option)}
            <option value={option}>{DRIVER_STATUS_META[option].label}</option>
          {/each}
        </select>
      </label>
      {#if nextStatus !== 'active'}
        <label>
          <span>Motivo</span>
          <textarea bind:value={reason} rows="3" maxlength="500"></textarea>
        </label>
        {#if driver.vehicle}
          <p class="warning">
            Se finalizará su asignación al vehículo {driver.vehicle.code}.
          </p>
        {/if}
      {/if}
      {#if actionError}<p class="error-text" role="alert">{actionError}</p>{/if}
      <div class="modal-actions">
        <Button variant="secondary" onclick={() => (modal = null)}>Cancelar</Button>
        <Button
          disabled={saving || (nextStatus !== 'active' && reason.trim().length < 3)}
          onclick={() =>
            run(() => driversApi.setStatus(driver!.id, nextStatus, reason.trim() || undefined))}
          >Confirmar</Button
        >
      </div>
    </div>
  </Modal>

  <Modal open={modal === 'branch'} title="Cambiar sucursal base" onclose={() => (modal = null)}>
    <div class="modal-body">
      <label>
        <span>Nueva sucursal</span>
        <select bind:value={targetBranch}>
          {#each branchOptions as option (option.id)}
            <option value={option.id}>{option.name}</option>
          {/each}
        </select>
      </label>
      <label>
        <span>Motivo</span>
        <textarea bind:value={reason} rows="3" maxlength="500"></textarea>
      </label>
      <p class="muted">
        El empleado debe tener asignación activa en la nueva sucursal y ningún vehículo asignado.
      </p>
      {#if actionError}<p class="error-text" role="alert">{actionError}</p>{/if}
      <div class="modal-actions">
        <Button variant="secondary" onclick={() => (modal = null)}>Cancelar</Button>
        <Button
          disabled={saving || !targetBranch || reason.trim().length < 3}
          onclick={() =>
            run(() => driversApi.changeBranch(driver!.id, targetBranch, reason.trim()))}
          >Confirmar</Button
        >
      </div>
    </div>
  </Modal>
{/if}

<style>
  .profile {
    max-width: 1300px;
    margin: 0 auto;
    padding: 22px 30px;
  }
  .state {
    padding: 48px;
    text-align: center;
    color: rgb(var(--foreground-muted));
  }
  .state.error {
    display: grid;
    justify-items: center;
    gap: 12px;
    color: rgb(var(--danger));
  }
  .hero {
    display: flex;
    gap: 22px;
    align-items: flex-start;
    padding: 20px;
    border: 1px solid rgb(var(--border));
    border-radius: 14px;
    background: rgb(var(--surface));
  }
  .photo {
    flex-shrink: 0;
    width: 96px;
    height: 96px;
    border-radius: 50%;
    object-fit: cover;
  }
  .initials {
    display: grid;
    place-items: center;
    border: 1px solid rgb(var(--border));
    background: rgb(var(--surface-hover));
    font-size: 28px;
    font-weight: 650;
  }
  .back {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .title {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 6px;
  }
  h1 {
    font-size: 26px;
    font-weight: 650;
    letter-spacing: -0.8px;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .reason {
    margin-top: 8px;
    font-size: 12px;
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 14px;
  }
  .pill {
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
  }
  .pill.available {
    background: rgb(var(--success) / 0.1);
    color: rgb(var(--success));
  }
  .pill.maintenance {
    background: rgb(var(--warning) / 0.12);
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .pill.muted {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground-muted));
  }
  .tabs {
    display: flex;
    gap: 18px;
    margin: 20px 0 16px;
    border-bottom: 1px solid rgb(var(--border));
  }
  .tabs button {
    padding: 10px 0;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    color: rgb(var(--foreground-muted));
  }
  .tabs button.active {
    border-bottom-color: rgb(var(--foreground));
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }
  .license-data {
    margin-bottom: 16px;
  }
  .license-back {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 12px;
    margin-top: 16px;
  }
  .license-back small {
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  .back-error {
    margin-top: 8px;
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .card {
    padding: 18px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  h2 {
    margin-bottom: 12px;
    font-size: 13px;
    font-weight: 600;
  }
  .spaced {
    margin-top: 18px;
  }
  .link-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 9px;
  }
  .link-row:hover {
    background: rgb(var(--surface-hover));
  }
  .link-row > span {
    display: grid;
    flex: 1;
    gap: 2px;
  }
  strong {
    font-size: 12px;
    font-weight: 600;
  }
  small,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .specs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  dt {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  dd {
    margin-top: 3px;
    font-size: 13px;
    font-weight: 550;
  }
  .notes {
    margin-top: 14px;
    font-size: 12px;
    white-space: pre-line;
  }
  .timeline {
    display: grid;
    gap: 10px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .timeline li {
    display: grid;
    gap: 2px;
    padding: 10px 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 9px;
  }
  .modal-body {
    display: grid;
    gap: 12px;
  }
  .modal-body label {
    display: grid;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
  }
  .modal-body select,
  .modal-body textarea {
    padding: 9px 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .warning {
    font-size: 12px;
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .error-text {
    font-size: 12px;
    color: rgb(var(--danger));
  }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  @media (max-width: 900px) {
    .profile {
      padding: 16px;
    }
    .hero {
      flex-direction: column;
    }
    .grid {
      grid-template-columns: 1fr;
    }
  }
</style>
