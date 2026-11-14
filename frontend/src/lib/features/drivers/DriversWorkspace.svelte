<script lang="ts">
  import { onMount, tick, untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { BASE_IMAGES, formatDate, LICENSE_LABELS, plateLabel } from '$lib/features/fleet/catalog';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    DRIVER_STATUS_META,
    driversApi,
    type Driver,
    type DriversSummary,
    type DriverStatus
  } from './api';

  import CreateDriverDialog from './CreateDriverDialog.svelte';
  import DriverAvatar from './DriverAvatar.svelte';
  import DriverInspector from './DriverInspector.svelte';
  import './drivers-theme.css';

  const PAGE_SIZE = 12;
  let drivers = $state<Driver[]>([]);
  let summary = $state<DriversSummary | null>(null);
  let total = $state(0);
  let pages = $state(1);
  let page = $state(1);
  let statusFilter = $state<'' | DriverStatus>('');
  let query = $state('');
  let debounced = $state('');
  let loading = $state(true);
  let error = $state<string | null>(null);
  let mounted = $state(false);
  let compact = $state(false);
  let mobile = $state(false);
  let generation = 0;
  let scopeId: string | null | undefined;
  let selectedId = $state<string | null>(null);
  let panelOpen = $state(true);
  let inspectorSlot = $state<HTMLDivElement>();
  let directoryElement = $state<HTMLElement>();
  let lastTrigger: HTMLButtonElement | undefined;
  const selected = $derived(
    panelOpen ? (drivers.find((item) => item.id === selectedId) ?? null) : null
  );
  const attention = $derived((summary?.blocked ?? 0) + (summary?.warning ?? 0));
  const stateTabs = [
    { value: '', label: 'Todos' },
    { value: 'active', label: 'Activos' },
    { value: 'suspended', label: 'Suspendidos' },
    { value: 'inactive', label: 'Inactivos' }
  ] as const;

  async function selectDriver(id: string, event: MouseEvent) {
    lastTrigger = event.currentTarget as HTMLButtonElement;
    selectedId = id;
    panelOpen = true;
    await tick();
    inspectorSlot?.focus({ preventScroll: true });
    if (window.matchMedia('(max-width: 1100px)').matches)
      inspectorSlot?.scrollIntoView({ block: 'start' });
  }

  function closeInspector() {
    const focusTarget = lastTrigger?.isConnected
      ? lastTrigger
      : directoryElement?.querySelector<HTMLButtonElement>('.inspect-button[aria-pressed="true"]');
    panelOpen = false;
    selectedId = null;
    requestAnimationFrame(() => focusTarget?.focus());
  }

  function resetFilters() {
    query = '';
    debounced = '';
    statusFilter = '';
    page = 1;
  }

  let createOpen = $state(false);

  const canCreate = $derived(permissions.hasPermission('drivers:create'));

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const [result, stats] = await Promise.all([
        driversApi.list({
          status: statusFilter,
          search: debounced.trim() || undefined,
          page,
          size: PAGE_SIZE
        }),
        driversApi.summary()
      ]);
      if (current !== generation) return;
      summary = stats;
      drivers = result.items;
      total = result.meta.total;
      pages = result.meta.pages;
      if (page > pages) {
        page = pages;
        return;
      }
      if (panelOpen && (!compact || selectedId) && !drivers.some((item) => item.id === selectedId))
        selectedId = drivers[0]?.id ?? null;
    } catch (err) {
      if (current !== generation) return;
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar los conductores.';
    } finally {
      if (current === generation) loading = false;
    }
  }

  onMount(() => {
    const media = window.matchMedia('(max-width: 1450px)');
    const small = window.matchMedia('(max-width: 1000px)');
    const resize = () => {
      const nextCompact = media.matches;
      if (nextCompact && !compact) {
        panelOpen = false;
        selectedId = null;
      }
      compact = nextCompact;
      mobile = small.matches;
    };
    resize();
    media.addEventListener('change', resize);
    small.addEventListener('change', resize);
    mounted = true;
    return () => {
      generation++;
      media.removeEventListener('change', resize);
      small.removeEventListener('change', resize);
    };
  });
  $effect(() => {
    const value = query;
    const timer = setTimeout(() => {
      if (value !== debounced) {
        debounced = value;
        page = 1;
      }
    }, 300);
    return () => clearTimeout(timer);
  });
  $effect(() => {
    if (!mounted) return;
    void statusFilter;
    void debounced;
    void page;
    const nextScope = branch.id;
    if (nextScope !== scopeId) {
      scopeId = nextScope;
      untrack(() => {
        drivers = [];
        summary = null;
        selectedId = null;
        page = 1;
      });
    }
    untrack(load);
  });
</script>

<div class="drivers">
  <header class="heading">
    <div>
      <h1>Conductores</h1>
      <p>
        Personas, documentación y disponibilidad<span class="scope"
          ><FleetIcon name="pin" size={12} />{branch.id
            ? branch.label
            : 'Todas las sucursales'}</span
        >
      </p>
    </div>
    {#if canCreate}<Button size="sm" onclick={() => (createOpen = true)}
        ><FleetIcon name="plus" size={15} />Nuevo conductor</Button
      >{/if}
  </header>
  <div class="workspace" class:with-inspector={!!selected && !compact}>
    <section class="directory" bind:this={directoryElement} aria-label="Directorio de conductores">
      <section class="metrics" aria-label="Resumen de conductores">
        <div>
          <span class="metric-icon"><FleetIcon name="list" size={24} /></span><span
            ><strong>{summary?.total ?? '—'}</strong><small>Conductores</small></span
          >
        </div>
        <div>
          <span class="metric-icon ok"><FleetIcon name="shield" size={24} /></span><span
            ><strong>{summary?.fit ?? '—'}</strong><small>Activos aptos</small></span
          >
        </div>
        <div>
          <span class="metric-icon warn"><FleetIcon name="clock" size={24} /></span><span
            ><strong>{summary?.warning ?? '—'}</strong><small>Con advertencias</small></span
          >
        </div>
        <div>
          <span class="metric-icon bad"><FleetIcon name="alert" size={24} /></span><span
            ><strong>{summary?.blocked ?? '—'}</strong><small>Activos no aptos</small></span
          >
        </div>
        <div>
          <span class="metric-icon"><FleetIcon name="truck" size={24} /></span><span
            ><strong>{summary?.assigned ?? '—'}</strong><small>Con vehículo</small></span
          >
        </div>
      </section>
      {#if attention > 0}<div class="attention">
          <FleetIcon name="alert" size={17} /><strong
            >{attention}
            {attention === 1 ? 'conductor requiere' : 'conductores requieren'} atención</strong
          ><span>Consulta las incidencias en su expediente antes de asignar un viaje.</span>
        </div>{/if}
      {#if error}<div class="error" role="alert">
          <FleetIcon name="alert" size={17} /><span>{error}</span><Button
            variant="secondary"
            size="sm"
            onclick={load}>Reintentar</Button
          >
        </div>{/if}

      <div class="filters">
        <nav class="status-tabs" aria-label="Filtrar por estado administrativo">
          {#each stateTabs as item}<button
              type="button"
              class:active={statusFilter === item.value}
              aria-pressed={statusFilter === item.value}
              onclick={() => {
                statusFilter = item.value;
                page = 1;
              }}
              >{item.label}{#if item.value === '' && summary}<span>{summary.total}</span
                >{/if}</button
            >{/each}
        </nav>
        <label class="search"
          ><FleetIcon name="search" size={15} /><input
            type="search"
            bind:value={query}
            placeholder="Buscar nombre, código, DUI o licencia…"
            aria-label="Buscar conductores"
          /></label
        >
      </div>
      {#if loading && drivers.length === 0}
        <div class="loading" role="status">
          <span class="sr-only">Cargando conductores…</span>{#each Array(6) as _}<div
              class="skeleton"
            ></div>{/each}
        </div>
      {:else if drivers.length === 0}
        <div class="empty">
          <span class="empty-icon"
            ><FleetIcon name={query || statusFilter ? 'search' : 'list'} size={24} /></span
          >
          <h3>
            {error
              ? 'El directorio no está disponible'
              : query || statusFilter
                ? 'Sin coincidencias'
                : 'Aún no hay conductores'}
          </h3>
          <p>
            {error
              ? 'Reintenta la consulta para ver los conductores.'
              : query || statusFilter
                ? 'Prueba con otro nombre o estado administrativo.'
                : 'Registra como conductor a un empleado de tu sucursal.'}
          </p>
          {#if query || statusFilter}<Button variant="secondary" size="sm" onclick={resetFilters}
              >Limpiar filtros</Button
            >{:else if canCreate && !error}<Button size="sm" onclick={() => (createOpen = true)}
              >Registrar conductor</Button
            >{/if}
        </div>
      {:else}
        <div class="table-wrap" class:refreshing={loading} aria-busy={loading}>
          {#if mobile}
            <div class="driver-cards">
              {#each drivers as driver (driver.id)}
                {@const top =
                  driver.compliance.issues.find((issue) => issue.severity === 'blocking') ??
                  driver.compliance.issues[0]}
                <article class="driver-card">
                  <div class="card-identity">
                    <DriverAvatar
                      name={driver.employee.name}
                      initials={driver.employee.initials}
                      src={driver.employee.photo_url}
                    />
                    <div>
                      <a class="name" href={`/drivers/${driver.id}`}>{driver.employee.name}</a
                      ><small
                        >{driver.employee.code} · {DRIVER_STATUS_META[driver.status].label}</small
                      >
                    </div>
                  </div>
                  <dl>
                    <div>
                      <dt>Sucursal</dt>
                      <dd>{driver.branch_name.replace(/^Pastelería Lorena /, '')}</dd>
                    </div>
                    <div>
                      <dt>Licencia</dt>
                      <dd>
                        {LICENSE_LABELS[driver.license.license_class]}<small class="block"
                          >{driver.license.expires_on
                            ? `Vence ${formatDate(driver.license.expires_on)}`
                            : driver.license.document_id
                              ? 'Sin vencimiento registrado'
                              : 'Sin licencia cargada'}</small
                        >
                      </dd>
                    </div>
                    <div>
                      <dt>Vehículo</dt>
                      <dd>
                        {#if driver.vehicle}<a href={`/fleet/${driver.vehicle.vehicle_id}`}
                            >{driver.vehicle.code} · {plateLabel(driver.vehicle.plate)}</a
                          >{:else}Sin asignar{/if}
                      </dd>
                    </div>
                  </dl>
                  <div class="card-bottom">
                    <span
                      class="fitness {driver.compliance.state}"
                      title={top?.message ?? 'Sin incidencias'}
                      >{driver.compliance.state === 'ok'
                        ? 'Apto'
                        : driver.compliance.state === 'warning'
                          ? 'Advertencias'
                          : 'No apto'}</span
                    ><button
                      type="button"
                      class="card-summary"
                      aria-label={`Ver resumen de ${driver.employee.name}`}
                      onclick={(event) => selectDriver(driver.id, event)}
                      >Ver resumen<FleetIcon name="chevron" size={15} /></button
                    >
                  </div>
                </article>
              {/each}
            </div>
          {:else}
            <table>
              <caption class="sr-only">Conductores</caption><thead
                ><tr
                  ><th>Conductor</th><th>Sucursal</th><th>Licencia</th><th>Vehículo asignado</th><th
                    >Aptitud</th
                  ><th><span class="sr-only">Resumen</span></th></tr
                ></thead
              ><tbody>
                {#each drivers as driver (driver.id)}
                  {@const top =
                    driver.compliance.issues.find((issue) => issue.severity === 'blocking') ??
                    driver.compliance.issues[0]}
                  <tr class:selected={selected?.id === driver.id}>
                    <td
                      ><div class="person">
                        <DriverAvatar
                          name={driver.employee.name}
                          initials={driver.employee.initials}
                          src={driver.employee.photo_url}
                        /><span
                          ><a href={`/drivers/${driver.id}`} class="name">{driver.employee.name}</a
                          ><small
                            >{driver.employee.code}<span
                              class="admin-status {DRIVER_STATUS_META[driver.status].tone}"
                              >{DRIVER_STATUS_META[driver.status].label}</span
                            ></small
                          ></span
                        >
                      </div></td
                    >
                    <td
                      ><span class="branch-name" title={driver.branch_name}
                        >{driver.branch_name.replace(/^Pastelería Lorena /, '')}</span
                      ></td
                    >
                    <td
                      ><span>{LICENSE_LABELS[driver.license.license_class]}</span><small
                        class="block"
                        >{driver.license.expires_on
                          ? `Vence ${formatDate(driver.license.expires_on)}`
                          : driver.license.document_id
                            ? 'Sin vencimiento registrado'
                            : 'Sin licencia cargada'}</small
                      ></td
                    >
                    <td
                      >{#if driver.vehicle}<a
                          class="vehicle"
                          href={`/fleet/${driver.vehicle.vehicle_id}`}
                          >{#if driver.vehicle.base_image}<img
                            src={BASE_IMAGES[driver.vehicle.base_image].image}
                            alt=""
                            width="58"
                            height="36"
                          />{/if}<span
                            >{driver.vehicle.code}<small class="block">{plateLabel(driver.vehicle.plate)}</small
                            ></span
                          ></a
                        >{:else}<span class="muted">Sin asignar</span>{/if}</td
                    >
                    <td
                      ><span
                        class="fitness {driver.compliance.state}"
                        title={top?.message ?? 'Sin incidencias'}
                        ><FleetIcon
                          name={driver.compliance.state === 'ok'
                            ? 'check'
                            : driver.compliance.state === 'warning'
                              ? 'clock'
                              : 'file'}
                          size={12}
                        />{driver.compliance.state === 'ok'
                          ? 'Apto'
                          : driver.compliance.state === 'warning'
                            ? 'Advertencias'
                            : 'No apto'}</span
                      >{#if top}<span class="sr-only">{top.message}</span>{/if}</td
                    >
                    <td
                      ><button
                        type="button"
                        class="inspect-button"
                        title="Ver resumen del conductor"
                        aria-label={`Ver resumen de ${driver.employee.name}`}
                        aria-pressed={selected?.id === driver.id}
                        onclick={(event) => selectDriver(driver.id, event)}
                        ><FleetIcon name="chevron" size={16} /></button
                      ></td
                    >
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
          <div class="pager">
            <span
              >Mostrando {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} de {total} conductores</span
            >{#if pages > 1}<div class="page-controls">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={page <= 1 || loading}
                  onclick={() => page--}
                  ><FleetIcon name="chevronLeft" size={15} /><span class="sr-only"
                    >Página anterior</span
                  ></Button
                ><span aria-live="polite">{page} / {pages}</span><Button
                  variant="ghost"
                  size="sm"
                  disabled={page >= pages || loading}
                  onclick={() => page++}
                  ><FleetIcon name="chevron" size={15} /><span class="sr-only"
                    >Página siguiente</span
                  ></Button
                >
              </div>{/if}
          </div>
        </div>
      {/if}
    </section>
    {#if selected && !compact}<div
        class="inspector-slot"
        bind:this={inspectorSlot}
        tabindex="-1"
        role="region"
        aria-label="Resumen del conductor seleccionado"
      >
        {#key selected.id}<DriverInspector
            driver={selected}
            onclose={closeInspector}
            onchanged={load}
          />{/key}
      </div>{/if}
  </div>
</div>

{#if selected && compact}
  <Modal open title="Resumen del conductor" size="lg" mobileFullScreen onclose={closeInspector}>
    {#key selected.id}<DriverInspector
        driver={selected}
        showClose={false}
        onclose={closeInspector}
        onchanged={load}
      />{/key}
  </Modal>
{/if}

<CreateDriverDialog bind:open={createOpen} oncreated={(driver) => goto(`/drivers/${driver.id}`)} />

<style>
  .drivers {
    --danger: 185 28 28;
    --fleet-warning-ink: 137 75 0;
    color: rgb(var(--foreground));
  }
  .heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--driver-space-4);
    margin-bottom: var(--driver-space-5);
  }
  .heading :global(button) {
    flex-shrink: 0;
    white-space: nowrap;
  }
  h1 {
    font-size: 28px;
    font-weight: 650;
    letter-spacing: -1px;
    line-height: 1.3;
  }
  .heading p {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--driver-space-2) var(--driver-space-4);
    margin-top: var(--driver-space-2);
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .scope {
    display: inline-flex;
    align-items: center;
    gap: var(--driver-space-1);
    font-size: 11px;
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius-lg);
    background: rgb(var(--surface));
    margin-bottom: var(--driver-space-3);
  }
  .metrics > div {
    display: flex;
    align-items: center;
    gap: var(--driver-space-3);
    margin: var(--driver-space-4) 0;
    padding: 0 var(--driver-space-5);
    min-width: 0;
    border-right: 1px solid rgb(var(--border));
  }
  .metrics > div:last-child {
    border: 0;
  }
  .metric-icon {
    color: rgb(var(--foreground-muted));
    flex-shrink: 0;
  }
  .metrics strong {
    display: block;
    font-size: 25px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }
  small {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .metrics small {
    display: block;
    margin-top: var(--driver-space-2);
    white-space: nowrap;
  }
  .ok {
    color: rgb(var(--fleet-success-ink, var(--success)));
  }
  .warn {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .bad {
    color: rgb(var(--danger));
  }
  .attention {
    display: flex;
    align-items: center;
    gap: var(--driver-space-3);
    flex-wrap: wrap;
    padding: var(--driver-space-3) var(--driver-space-3);
    border: 1px solid rgb(var(--warning) / 0.3);
    border-radius: var(--driver-radius);
    background: rgb(var(--warning) / 0.06);
    color: rgb(var(--fleet-warning-ink, var(--warning)));
    font-size: 12px;
    margin-bottom: var(--driver-space-5);
  }
  .attention span {
    margin-left: auto;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .workspace {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--driver-space-5);
    align-items: start;
  }
  .workspace.with-inspector {
    grid-template-columns: minmax(0, 1fr) minmax(340px, 360px);
  }
  .directory,
  .inspector-slot {
    position: sticky;
    top: 16px;
    min-width: 0;
  }
  .inspector-slot {
    position: sticky;
    top: 16px;
    scroll-margin-top: 80px;
    border-radius: var(--driver-radius-lg);
  }
  .filters {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--driver-space-3);
    margin-bottom: var(--driver-space-3);
    min-height: 38px;
  }
  .status-tabs {
    display: flex;
    align-items: center;
    gap: var(--driver-space-1);
    flex-wrap: wrap;
  }
  .status-tabs button {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2);
    min-height: 36px;
    padding: 0 var(--driver-space-3);
    border: 1px solid transparent;
    border-radius: var(--driver-radius);
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .status-tabs button:hover {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
  }
  .status-tabs button.active {
    color: rgb(var(--fleet-success-ink, var(--success)));
    border-color: rgb(var(--success) / 0.3);
    background: rgb(var(--success) / 0.08);
    font-weight: 550;
  }
  .status-tabs button span {
    padding: 1px var(--driver-space-1);
    border-radius: 5px;
    background: rgb(var(--success) / 0.1);
    font-size: 11px;
  }
  .search {
    display: flex;
    flex: 1;
    align-items: center;
    gap: var(--driver-space-2);
    min-width: 220px;
    max-width: 340px;
    padding: 0 var(--driver-space-3);
    border: 1px solid rgb(var(--control-border));
    border-radius: var(--driver-radius);
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface));
  }
  .search:focus-within {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
  .search input {
    flex: 1;
    min-width: 0;
    width: 100%;
    height: 36px;
    border: 0;
    background: transparent;
    color: rgb(var(--foreground));
    outline: none;
    font-size: 12px;
  }
  .driver-card {
    padding: var(--driver-space-4);
    border-bottom: 1px solid rgb(var(--border));
  }
  .card-identity {
    display: flex;
    gap: var(--driver-space-3);
    align-items: center;
  }
  .card-identity .name {
    font-size: 14px;
    max-width: none;
  }
  .card-identity small {
    display: block;
    margin-top: var(--driver-space-1);
  }
  .driver-card dl {
    display: grid;
    gap: var(--driver-space-3);
    margin: var(--driver-space-4) 0;
    font-size: 12px;
  }
  .driver-card dl > div {
    display: flex;
    justify-content: space-between;
    gap: var(--driver-space-4);
  }
  .driver-card dt {
    color: rgb(var(--foreground-muted));
  }
  .driver-card dd {
    text-align: right;
    overflow-wrap: anywhere;
  }
  .card-bottom {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--driver-space-3);
  }
  .card-summary {
    display: flex;
    align-items: center;
    gap: var(--driver-space-1);
    min-height: 40px;
    padding: 0 var(--driver-space-3);
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius-sm);
    font-size: 12px;
  }
  .table-wrap {
    overflow-x: auto;
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius-lg);
    background: rgb(var(--surface));
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  th {
    padding: var(--driver-space-3) var(--driver-space-3);
    border-bottom: 1px solid rgb(var(--border));
    font-size: 11px;
    font-weight: 500;
    text-align: left;
    color: rgb(var(--foreground-muted));
    white-space: nowrap;
    background: rgb(var(--surface-muted) / 0.35);
  }
  td {
    padding: 13px var(--driver-space-3);
    border-bottom: 1px solid rgb(var(--border));
    vertical-align: middle;
  }
  tr.selected {
    background: rgb(var(--success) / 0.06);
    box-shadow: inset 2px 0 rgb(var(--success));
  }
  tbody tr:hover {
    background: rgb(var(--surface-hover));
  }
  .person {
    display: flex;
    align-items: center;
    gap: var(--driver-space-3);
    min-width: 200px;
  }
  .name {
    display: block;
    font-weight: 550;
    font-size: 13px;
    line-height: 1.4;
    max-width: 260px;
  }
  .name:hover {
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .person small {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2);
    margin-top: var(--driver-space-1);
    font-size: 11px;
  }
  .admin-status {
    font-size: 10px;
    color: rgb(var(--foreground-muted));
  }
  .admin-status.available {
    color: rgb(var(--fleet-success-ink, var(--success)));
  }
  .admin-status.maintenance {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .branch-name {
    display: block;
    min-width: 95px;
    max-width: 160px;
    line-height: 1.5;
  }
  .block {
    display: block;
    margin-top: var(--driver-space-1);
    font-size: 11px;
    white-space: nowrap;
  }
  .vehicle {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2);
    white-space: nowrap;
    font-size: 11px;
  }
  .vehicle img {
    width: 58px;
    height: 36px;
    object-fit: contain;
  }
  .vehicle:hover {
    text-decoration: underline;
  }
  .fitness {
    display: inline-flex;
    align-items: center;
    gap: var(--driver-space-1);
    padding: var(--driver-space-1) var(--driver-space-2);
    border: 1px solid transparent;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 550;
    white-space: nowrap;
  }
  .fitness.ok {
    color: rgb(var(--fleet-success-ink, var(--success)));
    background: rgb(var(--success) / 0.08);
    border-color: rgb(var(--success) / 0.2);
  }
  .fitness.blocked {
    color: rgb(var(--danger));
    background: rgb(var(--danger) / 0.08);
    border-color: rgb(var(--danger) / 0.2);
  }
  .fitness.warning {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
    background: rgb(var(--warning) / 0.08);
    border-color: rgb(var(--warning) / 0.2);
  }
  .inspect-button {
    display: grid;
    place-items: center;
    width: 32px;
    height: 36px;
    border: 1px solid transparent;
    border-radius: var(--driver-radius-sm);
    color: rgb(var(--foreground-muted));
  }
  .inspect-button:hover,
  .inspect-button[aria-pressed='true'] {
    border-color: rgb(var(--border));
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
  }
  .pager {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--driver-space-3);
    padding: var(--driver-space-3) var(--driver-space-3);
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .page-controls {
    display: flex;
    align-items: center;
    gap: var(--driver-space-2);
  }
  .empty {
    display: grid;
    justify-items: center;
    gap: var(--driver-space-3);
    padding: 48px var(--driver-space-5);
    border: 1px dashed rgb(var(--border-strong));
    border-radius: var(--driver-radius-lg);
    text-align: center;
    color: rgb(var(--foreground-muted));
  }
  .empty-icon {
    display: grid;
    place-items: center;
    width: 48px;
    height: 48px;
    background: rgb(var(--surface-hover));
    border-radius: 50%;
  }
  .empty h3 {
    font-size: 15px;
    font-weight: 550;
    color: rgb(var(--foreground));
  }
  .empty p {
    font-size: 12px;
    max-width: 42ch;
  }
  .loading {
    display: grid;
    gap: var(--driver-space-2);
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius-lg);
    padding: var(--driver-space-3);
  }
  .loading > div {
    height: 50px;
    border-radius: var(--driver-radius-sm);
  }
  .error {
    display: flex;
    align-items: center;
    gap: var(--driver-space-3);
    padding: var(--driver-space-3);
    border: 1px solid rgb(var(--danger) / 0.3);
    border-radius: var(--driver-radius);
    background: rgb(var(--danger) / 0.06);
    font-size: 12px;
    margin-bottom: var(--driver-space-4);
  }
  .error > span {
    flex: 1;
  }
  .muted,
  .hint {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .refreshing {
    opacity: 0.65;
  }
  button:focus-visible,
  a:focus-visible,
  .inspector-slot:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 3px;
  }
  @media (max-width: 1350px) {
    .metrics > div {
      gap: var(--driver-space-3);
      padding: 0 var(--driver-space-4);
    }
    .workspace.with-inspector {
      grid-template-columns: minmax(0, 1fr) 340px;
    }
    .vehicle img {
      display: none;
    }
    td,
    th {
      padding-inline: var(--driver-space-3);
    }
    .person {
      min-width: 160px;
    }
  }
  @media (max-width: 1100px) {
    .inspector-slot {
      position: static;
    }
    .workspace.with-inspector {
      grid-template-columns: minmax(0, 1fr);
    }
    .metrics > div {
      padding: 0 var(--driver-space-3);
    }
    .metric-icon {
      display: none;
    }
    .metrics small {
      white-space: normal;
    }
    .vehicle img {
      display: block;
    }
  }
  @media (max-width: 1000px) {
    .heading {
      align-items: flex-start;
      flex-wrap: wrap;
    }
    h1 {
      font-size: 25px;
    }
    .metrics {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .metrics > div {
      margin: var(--driver-space-3) 0;
      padding: 0 var(--driver-space-4);
    }
    .metrics > div:nth-child(even) {
      border: 0;
    }
    .metrics > div:last-child {
      grid-column: span 2;
      border-top: 1px solid rgb(var(--border));
      padding-top: var(--driver-space-3);
      margin-top: 0;
    }
    .metrics strong {
      font-size: 23px;
    }
    .attention {
      align-items: flex-start;
    }
    .attention span {
      margin: 0;
    }
    .status-tabs {
      gap: 0;
    }
    .status-tabs button {
      padding: 0 var(--driver-space-2);
      min-height: 40px;
    }
    .search {
      max-width: none;
    }
    .filters {
      gap: var(--driver-space-3);
    }
    .pager {
      flex-wrap: wrap;
    }
    .inspect-button {
      height: 40px;
      width: 40px;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .skeleton {
      animation: none;
    }
  }
  :global([data-theme='dark']) .drivers {
    --danger: 255 107 107;
    --fleet-warning-ink: 255 184 77;
  }
  @media (max-width: 1000px) {
    .heading {
      flex-wrap: nowrap;
      align-items: flex-start;
    }
    .heading > div {
      min-width: 0;
      flex: 1;
    }
    .heading :global(button) {
      min-height: 40px;
      padding-inline: var(--driver-space-3);
      font-size: 11px;
    }
    .heading p {
      font-size: 11px;
    }
    .metrics {
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }
    .metrics > div {
      grid-column: span 2;
      padding-inline: var(--driver-space-3);
      border-right: 1px solid rgb(var(--border));
    }
    .metrics > div:nth-child(3) {
      border-right: 0;
    }
    .metrics > div:nth-child(n + 4) {
      grid-column: span 3;
      border-top: 1px solid rgb(var(--border));
      padding-top: var(--driver-space-3);
      margin-top: 0;
    }
    .metrics > div:last-child {
      border-right: 0;
    }
    .attention span {
      display: none;
    }
  }
</style>
