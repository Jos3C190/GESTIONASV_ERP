<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import OwnedDocumentsPanel from '$lib/features/documents/components/OwnedDocumentsPanel.svelte';
  import {
    formatDate,
    formatDateTime,
    plateLabel,
    LICENSE_LABELS
  } from '$lib/features/fleet/catalog';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import VehicleImage from '$lib/features/fleet/VehicleImage.svelte';
  import ComplianceList from '$lib/features/fleet/ComplianceList.svelte';
  import {
    driversApi,
    DRIVER_STATUS_META,
    type Driver,
    type Assignment,
    type DriverTrip
  } from './api';
  import DriverAvatar from './DriverAvatar.svelte';
  import DriverLicensePreview from './DriverLicensePreview.svelte';
  import LicenseCaptureEntry from './capture/LicenseCaptureEntry.svelte';

  let {
    driver,
    onclose,
    showClose = true,
    onchanged
  }: { driver: Driver; onclose: () => void; showClose?: boolean; onchanged: () => void } = $props();
  let tab = $state<'summary' | 'documents' | 'history'>('summary');
  let historyLoading = $state(false);
  let historyError = $state<string | null>(null);
  let assignments = $state<Assignment[]>([]);
  let trips = $state<DriverTrip[]>([]);
  let historyAttempt = $state(0);
  const owner = $derived(driversApi.documents(driver.id));
  const fitness = $derived(
    driver.compliance.state === 'blocked'
      ? 'No apto'
      : driver.compliance.state === 'warning'
        ? 'Con advertencias'
        : 'Apto'
  );

  $effect(() => {
    if (tab !== 'history') return;
    const id = driver.id;
    void historyAttempt;
    let cancelled = false;
    historyLoading = true;
    historyError = null;
    Promise.all([driversApi.assignments(id), driversApi.trips(id)])
      .then(([past, travelled]) => {
        if (!cancelled) {
          assignments = past;
          trips = travelled;
        }
      })
      .catch((err) => {
        if (!cancelled)
          historyError = err instanceof HttpError ? err.message : 'No se pudo cargar el historial.';
      })
      .finally(() => {
        if (!cancelled) historyLoading = false;
      });
    return () => {
      cancelled = true;
    };
  });
</script>

<aside
  class="inspector driver-inspector"
  class:in-dialog={!showClose}
  aria-label={`Expediente de ${driver.employee.name}`}
>
  <header class="profile-header">
    <DriverAvatar
      name={driver.employee.name}
      initials={driver.employee.initials}
      src={driver.employee.photo_url}
      large
    />
    <div class="identity">
      <h2>{driver.employee.name}</h2>
      <div class="badges">
        <span class="code">{driver.employee.code}</span><span
          class="status {DRIVER_STATUS_META[driver.status].tone}"
          >{DRIVER_STATUS_META[driver.status].label}</span
        ><span class="status {driver.compliance.state}">{fitness}</span>
      </div>
    </div>
    {#if showClose}
      <button
        type="button"
        class="close"
        aria-label="Cerrar resumen del conductor"
        title="Cerrar resumen"
        onclick={onclose}><FleetIcon name="close" size={16} /></button
      >
    {/if}
  </header>
  <nav class="tabs" aria-label="Contenido del expediente">
    {#each [{ id: 'summary', label: 'Resumen' }, { id: 'documents', label: 'Documentos' }, { id: 'history', label: 'Historial' }] as item}
      <button
        type="button"
        class:active={tab === item.id}
        aria-pressed={tab === item.id}
        onclick={() => (tab = item.id as typeof tab)}>{item.label}</button
      >
    {/each}
  </nav>
  <div class="content">
    {#if tab === 'summary'}
      <section>
        <h3>Información del conductor</h3>
        <dl>
          <div>
            <dt>Sucursal base</dt>
            <dd>{driver.branch_name}</dd>
          </div>
          <div>
            <dt>Clase de licencia</dt>
            <dd>{LICENSE_LABELS[driver.license.license_class]}</dd>
          </div>
          <div>
            <dt>Puesto</dt>
            <dd>{driver.employee.position ?? 'Sin puesto registrado'}</dd>
          </div>
        </dl>
      </section>
      <section>
        <h3>Aptitud para conducir</h3>
        <ComplianceList compliance={driver.compliance} />
      </section>
      <section class="license-card">
        <div class="section-title">
          <FleetIcon name="file" size={17} />
          <h3>Licencia de conducir</h3>
        </div>
        {#if driver.license.document_id}
          <DriverLicensePreview
            {owner}
            documentId={driver.license.document_id}
            name={driver.employee.name}
          />
          <strong>{driver.license.number ?? 'Licencia registrada'}</strong>
          <p>
            {driver.license.expires_on
              ? `Vence el ${formatDate(driver.license.expires_on)}`
              : 'Sin vencimiento registrado'}
          </p>
        {:else}<p class="missing"><FleetIcon name="file" size={28} />Sin documento cargado</p>{/if}
        <LicenseCaptureEntry {driver} compact onconfirmed={onchanged} />
        <button class="text-action" type="button" onclick={() => (tab = 'documents')}
          ><FleetIcon name="file" size={14} />Ver documentos<FleetIcon
            name="chevron"
            size={13}
          /></button
        >
      </section>
      <section class="vehicle-card">
        <div class="section-title">
          <FleetIcon name="truck" size={17} />
          <h3>Vehículo asignado</h3>
        </div>
        {#if driver.vehicle}
          <a class="vehicle" href={`/fleet/${driver.vehicle.vehicle_id}`}
            ><VehicleImage
              image={driver.vehicle.base_image}
              typeName={driver.vehicle.kind_name}
              label={`${driver.vehicle.kind_name}, ${driver.vehicle.code}`}
            />
            <div>
              <strong>{driver.vehicle.code}</strong>
              <p>{plateLabel(driver.vehicle.plate)} · {driver.vehicle.kind_name}</p>
              <span class="text-action">Ver vehículo <FleetIcon name="chevron" size={13} /></span>
            </div></a
          >
        {:else}<p class="muted">Sin vehículo asignado. Puedes asignarlo desde la ficha de Flota.</p>
          <a class="text-action" href="/fleet">Ir a Flota <FleetIcon name="chevron" size={13} /></a
          >{/if}
      </section>
      <section>
        <h3>Contacto y expediente</h3>
        <dl>
          <div>
            <dt>DUI</dt>
            <dd>{driver.employee.document_id ?? 'Sin registrar'}</dd>
          </div>
          <div>
            <dt>Teléfono</dt>
            <dd>
              {#if driver.employee.phone}<a href={`tel:${driver.employee.phone}`}
                  >{driver.employee.phone}</a
                >{:else}Sin registrar{/if}
            </dd>
          </div>
        </dl>
        {#if driver.notes}<p class="notes">{driver.notes}</p>{/if}
      </section>
    {:else if tab === 'documents'}
      <OwnedDocumentsPanel
        {owner}
        title="Licencia de conducir"
        description="Consulta la licencia de este conductor. Sus datos y vencimiento actualizan la aptitud para conducir."
        readOnly
        emptyHint="La licencia se registra con la captura guiada: usa el botón de fotos."
        permissionCodes={{
          read: 'drivers:read',
          upload: 'drivers:documents',
          update: 'drivers:documents',
          download: 'drivers:read'
        }}
        {onchanged}
      />
    {:else if historyLoading}<div class="history-loading" role="status">
        <span class="skeleton"></span>Cargando historial…
      </div>
    {:else if historyError}<div class="history-error" role="alert">
        <p>{historyError}</p>
        <Button variant="secondary" size="sm" onclick={() => historyAttempt++}
          >Reintentar historial</Button
        >
      </div>
    {:else}
      <section>
        <h3>Historial de vehículos</h3>
        {#if assignments.length}<ol>
            {#each assignments as item (item.id)}<li>
                <a href={`/fleet/${item.vehicle_id}`}
                  ><strong>{item.vehicle_code} · {item.vehicle_plate}</strong></a
                >
                <p>
                  {formatDate(item.starts_at)} — {item.ends_at
                    ? formatDate(item.ends_at)
                    : 'Actual'}
                </p>
                {#if item.end_reason}<p>{item.end_reason}</p>{/if}
              </li>{/each}
          </ol>{:else}<p class="muted">Aún no tiene asignaciones registradas.</p>{/if}
      </section>
      <section>
        <h3>Viajes realizados</h3>
        {#if trips.length}<ol>
            {#each trips as trip (trip.transfer_id)}<li>
                <strong>{trip.code}</strong>
                <p>{trip.origin_branch} → {trip.destination_branch}</p>
                <p>{trip.vehicle_code ?? 'Sin vehículo'} · {formatDateTime(trip.dispatched_at)}</p>
              </li>{/each}
          </ol>{:else}<p class="muted">Sin traslados registrados como conductor.</p>{/if}
      </section>
    {/if}
  </div>
  <footer>
    <a class="full-profile" href={`/drivers/${driver.id}`}
      ><FleetIcon name="file" size={17} />Ver expediente completo<FleetIcon
        name="arrow"
        size={15}
      /></a
    >
    <p>Edición, estado y sucursal desde el expediente.</p>
  </footer>
</aside>

<style>
  .inspector {
    --danger: 185 28 28;
    --fleet-warning-ink: 137 75 0;
    position: sticky;
    top: 16px;
    min-width: 0;
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius-lg);
    background: rgb(var(--surface));
    overflow: hidden;
    max-height: calc(100dvh - 190px);
    display: flex;
    flex-direction: column;
  }
  .inspector.in-dialog {
    position: static;
    max-height: none;
    border: 0;
    border-radius: 0;
  }
  .profile-header {
    display: flex;
    align-items: center;
    gap: var(--driver-space-3);
    padding: var(--driver-space-5) var(--driver-space-5) var(--driver-space-5);
    position: relative;
    flex-shrink: 0;
  }
  .identity {
    min-width: 0;
    padding-right: var(--driver-space-3);
  }
  h2 {
    font-size: 18px;
    font-weight: 650;
    line-height: 1.3;
    letter-spacing: -0.4px;
    margin: var(--driver-space-1) 0 var(--driver-space-3);
    overflow-wrap: anywhere;
  }
  .badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--driver-space-2);
    align-items: center;
  }
  .code,
  .status {
    font-size: 11px;
    border: 1px solid rgb(var(--border));
    padding: 3px var(--driver-space-2);
    border-radius: 5px;
    white-space: nowrap;
  }
  .status {
    border-radius: 999px;
  }
  .status.available,
  .status.ok {
    color: rgb(var(--fleet-success-ink, var(--success)));
    background: rgb(var(--success) / 0.08);
    border-color: rgb(var(--success) / 0.2);
  }
  .status.blocked {
    color: rgb(var(--danger));
    background: rgb(var(--danger) / 0.08);
    border-color: rgb(var(--danger) / 0.2);
  }
  .status.warning,
  .status.maintenance {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
    background: rgb(var(--warning) / 0.08);
    border-color: rgb(var(--warning) / 0.2);
  }
  .close {
    position: absolute;
    right: 10px;
    top: 10px;
    width: 32px;
    height: 32px;
    display: grid;
    place-items: center;
    border-radius: var(--driver-radius-sm);
    color: rgb(var(--foreground-muted));
  }
  .close:hover {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
  }
  .tabs {
    display: flex;
    gap: var(--driver-space-5);
    padding: 0 var(--driver-space-5);
    border-bottom: 1px solid rgb(var(--border));
    flex-shrink: 0;
  }
  .tabs button {
    padding: var(--driver-space-3) 0;
    font-size: 12px;
    border-bottom: 2px solid transparent;
    color: rgb(var(--foreground-muted));
  }
  .tabs button.active {
    color: rgb(var(--fleet-success-ink, var(--success)));
    border-bottom-color: rgb(var(--success));
    font-weight: 600;
  }
  .content {
    padding: var(--driver-space-5);
    overflow: auto;
    min-height: 0;
    display: grid;
    gap: var(--driver-space-5);
  }
  h3 {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: var(--driver-space-3);
  }
  dl {
    display: grid;
    gap: var(--driver-space-3);
    font-size: 12px;
  }
  dl > div {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--driver-space-4);
  }
  dt {
    color: rgb(var(--foreground-muted));
    flex-shrink: 0;
  }
  dd {
    text-align: right;
    overflow-wrap: anywhere;
  }
  p {
    font-size: 12px;
    line-height: 1.5;
    color: rgb(var(--foreground-muted));
  }
  .license-card,
  .vehicle-card {
    padding: var(--driver-space-3);
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius);
    background: rgb(var(--surface-muted) / 0.35);
  }
  .section-title {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2);
  }
  .section-title h3 {
    margin: 0;
  }
  .license-card > strong {
    display: block;
    font-size: 13px;
    margin-top: var(--driver-space-4);
  }
  .missing {
    display: flex;
    align-items: center;
    gap: var(--driver-space-3);
    padding: var(--driver-space-4) 0;
  }
  .text-action {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2);
    font-size: 12px;
    font-weight: 550;
    color: rgb(var(--fleet-success-ink, var(--success)));
    min-height: 36px;
  }
  .text-action :global(svg:last-child) {
    margin-left: auto;
  }
  .vehicle > div {
    font-size: 13px;
  }
  .notes {
    margin-top: var(--driver-space-3);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  ol {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: var(--driver-space-3);
  }
  li {
    border-left: 2px solid rgb(var(--border));
    padding-left: var(--driver-space-3);
  }
  li strong {
    font-size: 12px;
  }
  .history-loading {
    display: grid;
    gap: var(--driver-space-3);
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .history-loading span {
    height: 80px;
    border-radius: var(--driver-radius);
  }
  .history-error {
    display: grid;
    gap: var(--driver-space-3);
    padding: var(--driver-space-3);
    border: 1px solid rgb(var(--danger) / 0.3);
    border-radius: var(--driver-radius);
  }
  footer {
    padding: var(--driver-space-4) var(--driver-space-5);
    border-top: 1px solid rgb(var(--border));
    flex-shrink: 0;
  }
  .full-profile {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2);
    justify-content: center;
    min-height: 40px;
    border: 1px solid rgb(var(--border-strong));
    border-radius: var(--driver-radius);
    font-size: 12px;
    font-weight: 550;
  }
  .full-profile :global(svg:last-child) {
    margin-left: auto;
  }
  footer p {
    font-size: 11px;
    margin-top: var(--driver-space-2);
    text-align: center;
  }
  button:focus-visible,
  a:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 3px;
  }
  @media (max-width: 1100px) {
    .inspector {
      position: static;
      max-height: none;
    }
    .content {
      overflow: visible;
    }
    .close {
      width: 40px;
      height: 40px;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .skeleton {
      animation: none;
    }
  }
  :global([data-theme='dark']) .inspector {
    --danger: 255 107 107;
    --fleet-warning-ink: 255 184 77;
  }
</style>
