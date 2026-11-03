<script lang="ts">
  import { goto } from '$app/navigation';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import OwnedDocumentsPanel from '$lib/features/documents/components/OwnedDocumentsPanel.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetVehicle } from './api';
  import {
    formatDate,
    formatDateTime,
    formatNumber,
    FUEL_LABELS,
    meterName,
    meterShort,
    plateLabel,
    LICENSE_LABELS,
    VEHICLE_STATUS_LABELS,
    type VehicleStatus as StoredStatus
  } from './catalog';
  import ComplianceList from './ComplianceList.svelte';
  import FleetIcon from './FleetIcon.svelte';
  import MoveToTrashDialog from './MoveToTrashDialog.svelte';
  import VehicleCouplingCard from './VehicleCouplingCard.svelte';
  import VehicleDriverPanel from './VehicleDriverPanel.svelte';
  import VehicleFuelPanel from './VehicleFuelPanel.svelte';
  import VehicleGallery from './VehicleGallery.svelte';
  import VehicleGpsPanel from './VehicleGpsPanel.svelte';
  import VehicleImage from './VehicleImage.svelte';
  import VehicleMaintenancePanel from './VehicleMaintenancePanel.svelte';
  import VehicleOdometerPanel from './VehicleOdometerPanel.svelte';
  import VehicleStatus from './VehicleStatus.svelte';

  let { vehicleId }: { vehicleId: string } = $props();

  type Tab =
    'summary' | 'driver' | 'documents' | 'maintenance' | 'fuel' | 'odometer' | 'gps' | 'gallery';
  let vehicle = $state<FleetVehicle | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let tab = $state<Tab>('summary');
  let statusOpen = $state(false);
  let branchOpen = $state(false);
  let nextStatus = $state<Exclude<StoredStatus, 'maintenance'>>('active');
  let reason = $state('');
  let targetBranch = $state('');
  let saving = $state(false);
  let actionError = $state<string | null>(null);
  let trashOpen = $state(false);

  const canUpdate = $derived(permissions.hasPermission('fleet:update'));
  // La papelera es administrativa: requiere alcance de todas las sucursales.
  const canDelete = $derived(permissions.hasPermission('fleet:delete') && branch.accessAllBranches);
  const canReadDocuments = $derived(permissions.hasPermission('fleet_documents:read'));
  const tabs = $derived(
    [
      { id: 'summary' as const, label: 'Resumen', visible: true },
      {
        id: 'driver' as const,
        label: 'Conductor',
        visible: permissions.hasPermission('drivers:read')
      },
      { id: 'documents' as const, label: 'Documentos', visible: canReadDocuments },
      { id: 'maintenance' as const, label: 'Mantenimiento', visible: true },
      { id: 'fuel' as const, label: 'Combustible', visible: vehicle?.type.fuel_applicable ?? true },
      {
        id: 'odometer' as const,
        label: meterName(vehicle?.type.meter_unit ?? 'km'),
        visible: true
      },
      { id: 'gps' as const, label: 'GPS', visible: true },
      { id: 'gallery' as const, label: 'Galería', visible: true }
    ].filter((item) => item.visible)
  );
  const statusOptions = $derived(
    (['active', 'out_of_service', 'retired'] as const).filter((item) => item !== vehicle?.status)
  );
  const branchOptions = $derived(branch.branches.filter((item) => item.id !== vehicle?.branch_id));
  const reasonRequired = $derived(nextStatus !== 'active' || vehicle?.status === 'retired');

  async function load() {
    loading = true;
    error = null;
    try {
      vehicle = await fleetApi.get(vehicleId);
    } catch (err) {
      error =
        err instanceof HttpError && err.status === 404
          ? 'El vehículo no existe o pertenece a otra sucursal.'
          : err instanceof HttpError
            ? err.message
            : 'No se pudo cargar el vehículo.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void vehicleId;
    void load();
  });

  function openStatus() {
    nextStatus = statusOptions[0] ?? 'active';
    reason = '';
    actionError = null;
    statusOpen = true;
  }
  function openBranch() {
    targetBranch = branchOptions[0]?.id ?? '';
    reason = '';
    actionError = null;
    branchOpen = true;
  }

  async function run(action: () => Promise<FleetVehicle>) {
    saving = true;
    actionError = null;
    try {
      vehicle = await action();
      statusOpen = false;
      branchOpen = false;
    } catch (err) {
      actionError = err instanceof HttpError ? err.message : 'No se pudo completar la acción.';
    } finally {
      saving = false;
    }
  }
</script>

{#if loading && !vehicle}
  <div class="state">Cargando vehículo…</div>
{:else if error || !vehicle}
  <div class="state error" role="alert">
    <p>{error}</p>
    <Button variant="secondary" size="sm" onclick={() => goto('/fleet')}>Volver a Flota</Button>
  </div>
{:else}
  <div class="vehicle-file">
    <header class="hero">
      <div class="hero-image">
        <VehicleImage
          image={vehicle.type.base_image}
          typeName={vehicle.type.name}
          label={`${vehicle.brand} ${vehicle.model}`}
          large
        />
      </div>
      <div class="hero-body">
        <a class="back" href="/fleet"><FleetIcon name="chevronLeft" size={14} />Flota</a>
        <div class="title">
          <h1>{vehicle.code}</h1>
          <VehicleStatus status={vehicle.operational_status} />
        </div>
        <p class="subtitle">
          {vehicle.brand}
          {vehicle.model} · {vehicle.year} · <span class="plate">{vehicle.plate}</span>
        </p>
        <p class="meta">
          <FleetIcon name="pin" size={13} />{vehicle.branch_name}
          <span>·</span>{vehicle.type.name}
          <span>·</span>{formatNumber(vehicle.odometer_km)}
          {meterShort(vehicle.type.meter_unit)}
        </p>
        {#if canUpdate}
          <div class="actions">
            {#if vehicle.status !== 'retired'}
              <Button
                size="sm"
                variant="secondary"
                onclick={() => goto(`/fleet/${vehicle!.id}/edit`)}>Editar</Button
              >
            {/if}
            {#if vehicle.status !== 'maintenance'}
              <Button size="sm" variant="secondary" onclick={openStatus}>Cambiar estado</Button>
            {/if}
            {#if branchOptions.length && vehicle.status !== 'retired'}
              <Button size="sm" variant="secondary" onclick={openBranch}>Cambiar sucursal</Button>
            {/if}
            {#if canDelete}
              <Button size="sm" variant="ghost" onclick={() => (trashOpen = true)}
                >Mover a papelera</Button
              >
            {/if}
          </div>
        {/if}
      </div>
    </header>

    <nav class="tabs" aria-label="Secciones del vehículo">
      {#each tabs as item (item.id)}
        <button
          type="button"
          class:active={tab === item.id}
          aria-pressed={tab === item.id}
          onclick={() => (tab = item.id)}>{item.label}</button
        >
      {/each}
    </nav>

    <div class="panel">
      {#if tab === 'summary'}
        <div class="summary-grid">
          <section class="card">
            <h2>Aptitud para operar</h2>
            <ComplianceList compliance={vehicle.compliance} />
          </section>
          <section class="card">
            <h2>Operación</h2>
            {#if vehicle.current_transfer}
              <a class="link-row" href={`/tracking?transfer=${vehicle.current_transfer.id}`}>
                <FleetIcon name="route" size={16} />
                <span
                  ><strong>En traslado {vehicle.current_transfer.code}</strong><small
                    >Hacia {vehicle.current_transfer.destination_branch} · salió {formatDateTime(
                      vehicle.current_transfer.dispatched_at
                    )}</small
                  ></span
                >
                <FleetIcon name="chevron" size={14} />
              </a>
            {:else}
              <p class="muted">Sin traslados en curso.</p>
            {/if}
            {#if vehicle.driver}
              <a class="link-row" href={`/drivers/${vehicle.driver.driver_id}`}>
                <span class="avatar">{vehicle.driver.initials}</span>
                <span
                  ><strong>{vehicle.driver.name}</strong><small
                    >Licencia {LICENSE_LABELS[vehicle.driver.license_class]} · desde {formatDate(
                      vehicle.driver.since
                    )}</small
                  ></span
                >
                <FleetIcon name="chevron" size={14} />
              </a>
            {:else}
              <p class="muted">Sin conductor asignado.</p>
            {/if}
          </section>
          <section class="card wide">
            <h2>Ficha técnica</h2>
            <dl class="specs">
              <div>
                <dt>Código</dt>
                <dd>{vehicle.code}</dd>
              </div>
              <div>
                <dt>Placa</dt>
                <dd>{plateLabel(vehicle.plate)}</dd>
              </div>
              <div>
                <dt>VIN</dt>
                <dd>{vehicle.vin ?? '—'}</dd>
              </div>
              <div>
                <dt>Tipo</dt>
                <dd>{vehicle.type.name}</dd>
              </div>
              <div>
                <dt>Marca y modelo</dt>
                <dd>{vehicle.brand} {vehicle.model}</dd>
              </div>
              <div>
                <dt>Año</dt>
                <dd>{vehicle.year}</dd>
              </div>
              <div>
                <dt>Color</dt>
                <dd>{vehicle.color ?? '—'}</dd>
              </div>
              <div>
                <dt>Capacidad</dt>
                <dd>{formatNumber(vehicle.capacity_kg)} kg</dd>
              </div>
              <div>
                <dt>Combustible</dt>
                <dd>{FUEL_LABELS[vehicle.fuel_type]}</dd>
              </div>
              <div>
                <dt>{meterName(vehicle.type.meter_unit)}</dt>
                <dd>{formatNumber(vehicle.odometer_km)} {meterShort(vehicle.type.meter_unit)}</dd>
              </div>
              <div>
                <dt>Estado</dt>
                <dd>{VEHICLE_STATUS_LABELS[vehicle.status]}</dd>
              </div>
              <div>
                <dt>GPS</dt>
                <dd>{vehicle.gps_device_unique_id ?? 'Sin GPS'}</dd>
              </div>
              <div>
                <dt>Registrado</dt>
                <dd>{formatDate(vehicle.created_at)}</dd>
              </div>
            </dl>
            {#if vehicle.notes}<p class="notes">{vehicle.notes}</p>{/if}
          </section>
          {#if vehicle.type.can_tow || vehicle.type.is_towable}
            <VehicleCouplingCard {vehicle} onchanged={(next) => (vehicle = next)} />
          {/if}
        </div>
      {:else if tab === 'driver'}
        <VehicleDriverPanel {vehicle} onchanged={load} />
      {:else if tab === 'documents'}
        <OwnedDocumentsPanel
          owner={fleetApi.documents(vehicle.id)}
          title="Documentos del vehículo"
          description="Tarjeta de circulación, seguro, revisión técnica y demás documentación. Los obligatorios vencidos bloquean los despachos."
          permissionPrefix="fleet_documents"
          onchanged={load}
        />
      {:else if tab === 'maintenance'}
        <VehicleMaintenancePanel {vehicle} onchanged={load} />
      {:else if tab === 'fuel'}
        <VehicleFuelPanel {vehicle} onchanged={load} />
      {:else if tab === 'odometer'}
        <VehicleOdometerPanel {vehicle} onchanged={load} />
      {:else if tab === 'gps'}
        <VehicleGpsPanel {vehicle} onchanged={(next) => (vehicle = next)} />
      {:else}
        <VehicleGallery
          vehicleId={vehicle.id}
          title={`${vehicle.code} · ${vehicle.brand} ${vehicle.model}`}
          canManage={canUpdate && vehicle.status !== 'retired'}
        />
      {/if}
    </div>
  </div>

  <Modal open={statusOpen} title="Cambiar estado del vehículo" onclose={() => (statusOpen = false)}>
    <div class="modal-body">
      <label>
        <span>Nuevo estado</span>
        <select bind:value={nextStatus}>
          {#each statusOptions as option (option)}
            <option value={option}>{VEHICLE_STATUS_LABELS[option]}</option>
          {/each}
        </select>
      </label>
      {#if reasonRequired}
        <label>
          <span>Motivo</span>
          <textarea bind:value={reason} rows="3" maxlength="500"></textarea>
        </label>
      {/if}
      {#if nextStatus === 'retired'}
        <p class="warning">
          Dar de baja retira la unidad de la operación y de los traslados. Puede reactivarse
          después.
        </p>
      {/if}
      {#if actionError}<p class="error-text" role="alert">{actionError}</p>{/if}
      <div class="modal-actions">
        <Button variant="secondary" onclick={() => (statusOpen = false)}>Cancelar</Button>
        <Button
          disabled={saving || (reasonRequired && reason.trim().length < 3)}
          onclick={() =>
            run(() => fleetApi.setStatus(vehicle!.id, nextStatus, reason.trim() || undefined))}
          >Confirmar</Button
        >
      </div>
    </div>
  </Modal>

  <MoveToTrashDialog
    open={trashOpen}
    title="Mover vehículo a la papelera"
    resource="fleet_vehicles"
    recordId={vehicle.id}
    description={`${vehicle.code} · ${plateLabel(vehicle.plate)} dejará de aparecer en Flota, Traslados y Seguimiento. Debe estar sin conductor, sin traslado en ruta, sin órdenes de taller abiertas y sin GPS vinculado.`}
    onclose={() => (trashOpen = false)}
    ondone={() => goto('/fleet')}
  />

  <Modal open={branchOpen} title="Cambiar sucursal base" onclose={() => (branchOpen = false)}>
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
      <p class="hint">
        El vehículo no debe estar en un traslado ni tener conductor asignado. Solo la nueva sucursal
        lo verá después del cambio.
      </p>
      {#if actionError}<p class="error-text" role="alert">{actionError}</p>{/if}
      <div class="modal-actions">
        <Button variant="secondary" onclick={() => (branchOpen = false)}>Cancelar</Button>
        <Button
          disabled={saving || !targetBranch || reason.trim().length < 3}
          onclick={() => run(() => fleetApi.changeBranch(vehicle!.id, targetBranch, reason.trim()))}
          >Confirmar</Button
        >
      </div>
    </div>
  </Modal>
{/if}

<style>
  .vehicle-file {
    max-width: 1400px;
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
    display: grid;
    grid-template-columns: minmax(240px, 360px) minmax(0, 1fr);
    gap: 24px;
    align-items: center;
    padding: 18px;
    border: 1px solid rgb(var(--border));
    border-radius: 14px;
    background: rgb(var(--surface));
  }
  .hero-image {
    padding: 8px;
    border-radius: 12px;
    background: rgb(var(--surface-muted));
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
    margin-top: 8px;
  }
  h1 {
    font-size: 28px;
    font-weight: 650;
    letter-spacing: -1px;
  }
  .subtitle {
    margin-top: 6px;
    font-size: 14px;
  }
  .plate {
    padding: 2px 6px;
    border: 1px solid rgb(var(--border-strong));
    border-radius: 4px;
    font:
      12px 'Geist Mono',
      monospace;
  }
  .meta {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
  }
  .tabs {
    display: flex;
    gap: 18px;
    margin: 20px 0 16px;
    border-bottom: 1px solid rgb(var(--border));
    overflow-x: auto;
  }
  .tabs button {
    padding: 10px 0;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    color: rgb(var(--foreground-muted));
    white-space: nowrap;
  }
  .tabs button.active {
    border-bottom-color: rgb(var(--foreground));
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }
  .card {
    padding: 18px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  .card.wide {
    grid-column: 1 / -1;
  }
  h2 {
    margin-bottom: 12px;
    font-size: 13px;
    font-weight: 600;
  }
  .link-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    padding: 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 9px;
  }
  .link-row:hover {
    background: rgb(var(--surface-hover));
  }
  .link-row > span:not(.avatar) {
    display: grid;
    flex: 1;
    gap: 2px;
  }
  .link-row strong {
    font-size: 12px;
  }
  .link-row small,
  .muted {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .muted {
    margin-bottom: 8px;
    font-size: 12px;
  }
  .avatar {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    background: rgb(var(--surface-hover));
    font-size: 11px;
    font-weight: 600;
  }
  .specs {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    gap: 14px;
  }
  dt {
    margin-bottom: 3px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  dd {
    font-size: 13px;
    font-weight: 550;
  }
  .notes {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid rgb(var(--border));
    font-size: 12px;
    white-space: pre-line;
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
  .warning,
  .hint {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .warning {
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
    .vehicle-file {
      padding: 16px;
    }
    .hero,
    .summary-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
