<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { formatDate, LICENSE_LABELS, type LicenseClass } from '$lib/features/fleet/catalog';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import {
    DRIVER_STATUS_META,
    driversApi,
    type Driver,
    type DriverCandidate,
    type DriversSummary,
    type DriverStatus
  } from './api';

  const PAGE_SIZE = 50;
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
  let generation = 0;

  let createOpen = $state(false);
  let createBranch = $state('');
  let candidateSearch = $state('');
  let candidates = $state<DriverCandidate[]>([]);
  let candidateId = $state('');
  let licenseClass = $state<LicenseClass>('liviana');
  let createNotes = $state('');
  let creating = $state(false);
  let createError = $state<string | null>(null);

  const canCreate = $derived(permissions.hasPermission('drivers:create'));
  const licenseOptions = Object.keys(LICENSE_LABELS) as LicenseClass[];

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
    } catch (err) {
      if (current !== generation) return;
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar los conductores.';
    } finally {
      if (current === generation) loading = false;
    }
  }

  onMount(() => (mounted = true));
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
    load();
  });

  async function loadCandidates() {
    if (!createBranch) {
      candidates = [];
      return;
    }
    try {
      candidates = await driversApi.candidates(createBranch, candidateSearch.trim() || undefined);
      if (!candidates.some((item) => item.employee_id === candidateId)) candidateId = '';
    } catch (err) {
      createError = err instanceof HttpError ? err.message : 'No se pudieron cargar los empleados.';
    }
  }

  function openCreate() {
    createBranch = branch.id ?? branch.branches[0]?.id ?? '';
    candidateSearch = '';
    candidateId = '';
    licenseClass = 'liviana';
    createNotes = '';
    createError = null;
    createOpen = true;
  }

  $effect(() => {
    if (!createOpen) return;
    void createBranch;
    void candidateSearch;
    const timer = setTimeout(loadCandidates, 250);
    return () => clearTimeout(timer);
  });

  async function create() {
    creating = true;
    createError = null;
    try {
      const driver = await driversApi.create({
        employee_id: candidateId,
        branch_id: createBranch,
        license_class: licenseClass,
        notes: createNotes.trim() || null
      });
      createOpen = false;
      await goto(`/drivers/${driver.id}`);
    } catch (err) {
      createError = err instanceof HttpError ? err.message : 'No se pudo registrar el conductor.';
    } finally {
      creating = false;
    }
  }
</script>

<div class="drivers">
  <header class="heading">
    <div>
      <h1>Conductores</h1>
      <p>
        Empleados habilitados para conducir en {branch.id ? branch.label : 'la empresa'}, su
        licencia y el vehículo que tienen asignado.
      </p>
    </div>
    {#if canCreate}
      <Button size="sm" onclick={openCreate}
        ><FleetIcon name="plus" size={15} />Nuevo conductor</Button
      >
    {/if}
  </header>

  <section class="metrics" aria-label="Resumen de conductores">
    <div><span>Conductores</span><strong>{summary?.total ?? '—'}</strong></div>
    <div><span>Activos aptos</span><strong class="ok">{summary?.fit ?? '—'}</strong></div>
    <div>
      <span>Con advertencias</span><strong class="warn">{summary?.warning ?? '—'}</strong>
    </div>
    <div><span>Activos no aptos</span><strong class="bad">{summary?.blocked ?? '—'}</strong></div>
    <div><span>Con vehículo</span><strong>{summary?.assigned ?? '—'}</strong></div>
  </section>

  <div class="filters">
    <label class="search">
      <FleetIcon name="search" size={16} />
      <input
        type="search"
        bind:value={query}
        placeholder="Buscar por nombre, código o DUI…"
        aria-label="Buscar conductores"
      />
    </label>
    <select bind:value={statusFilter} aria-label="Filtrar por estado" onchange={() => (page = 1)}>
      <option value="">Todos los estados</option>
      <option value="active">Activos</option>
      <option value="suspended">Suspendidos</option>
      <option value="inactive">Inactivos</option>
    </select>
  </div>

  {#if error}
    <div class="error" role="alert">
      {error}
      <Button variant="secondary" size="sm" onclick={load}>Reintentar</Button>
    </div>
  {/if}

  {#if loading && drivers.length === 0}
    <p class="muted">Cargando conductores…</p>
  {:else if drivers.length === 0}
    <div class="empty">
      <FleetIcon name="info" size={22} />
      <h3>{query || statusFilter ? 'Sin coincidencias' : 'Aún no hay conductores'}</h3>
      <p>
        {query || statusFilter
          ? 'Prueba con otro nombre o estado.'
          : 'Registra como conductor a un empleado asignado a la sucursal.'}
      </p>
    </div>
  {:else}
    <div class="table-wrap" class:refreshing={loading}>
      <table>
        <caption class="sr-only">Conductores</caption>
        <thead>
          <tr>
            <th>Conductor</th>
            <th>Sucursal</th>
            <th>Licencia</th>
            <th>Vehículo</th>
            <th>Estado</th>
            <th>Aptitud</th>
          </tr>
        </thead>
        <tbody>
          {#each drivers as driver (driver.id)}
            {@const top =
              driver.compliance.issues.find((issue) => issue.severity === 'blocking') ??
              driver.compliance.issues[0]}
            <tr>
              <td>
                <a class="person" href={`/drivers/${driver.id}`}>
                  {#if driver.employee.photo_url}
                    <img src={driver.employee.photo_url} alt="" />
                  {:else}
                    <span class="avatar">{driver.employee.initials}</span>
                  {/if}
                  <span>
                    <strong>{driver.employee.name}</strong>
                    <small>{driver.employee.code}</small>
                  </span>
                </a>
              </td>
              <td>{driver.branch_name}</td>
              <td>
                {LICENSE_LABELS[driver.license.license_class]}
                <small class="block"
                  >{driver.license.expires_on
                    ? `Vence ${formatDate(driver.license.expires_on)}`
                    : 'Sin licencia cargada'}</small
                >
              </td>
              <td>{driver.vehicle ? `${driver.vehicle.code} · ${driver.vehicle.plate}` : '—'}</td>
              <td>
                <span class="pill {DRIVER_STATUS_META[driver.status].tone}"
                  >{DRIVER_STATUS_META[driver.status].label}</span
                >
              </td>
              <td>
                {#if top}
                  <span class="issue {top.severity}" title={top.message}>{top.message}</span>
                {:else}
                  <span class="issue ok">Apto</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if pages > 1}
      <div class="pager">
        <span>Página {page} de {pages}</span>
        <Button variant="secondary" size="sm" disabled={page <= 1} onclick={() => (page -= 1)}
          >Anterior</Button
        >
        <Button variant="secondary" size="sm" disabled={page >= pages} onclick={() => (page += 1)}
          >Siguiente</Button
        >
      </div>
    {/if}
  {/if}
</div>

<Modal open={createOpen} title="Nuevo conductor" size="lg" onclose={() => (createOpen = false)}>
  <div class="form">
    <p class="hint">
      Un conductor es un empleado con asignación activa en la sucursal. La licencia se carga después
      en su perfil y queda también en su expediente de empleado.
    </p>
    <label>
      <span>Sucursal base</span>
      <select bind:value={createBranch}>
        {#each branch.branches as item (item.id)}
          <option value={item.id}>{item.name}</option>
        {/each}
      </select>
    </label>
    <label>
      <span>Buscar empleado</span>
      <input bind:value={candidateSearch} placeholder="Nombre o código" />
    </label>
    <div class="candidates" role="listbox" aria-label="Empleados disponibles">
      {#each candidates as candidate (candidate.employee_id)}
        <button
          type="button"
          role="option"
          aria-selected={candidateId === candidate.employee_id}
          class:selected={candidateId === candidate.employee_id}
          onclick={() => (candidateId = candidate.employee_id)}
        >
          <strong>{candidate.name}</strong>
          <small>{candidate.code}{candidate.position ? ` · ${candidate.position}` : ''}</small>
        </button>
      {:else}
        <p class="muted">No hay empleados disponibles en esta sucursal.</p>
      {/each}
    </div>
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
      <textarea bind:value={createNotes} rows="2" maxlength="2000"></textarea>
    </label>
    {#if createError}<p class="error-text" role="alert">{createError}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={() => (createOpen = false)}>Cancelar</Button>
      <Button disabled={creating || !candidateId || !createBranch} onclick={create}
        >{creating ? 'Registrando…' : 'Registrar conductor'}</Button
      >
    </div>
  </div>
</Modal>

<style>
  .drivers {
    max-width: 1600px;
    margin: 0 auto;
    padding: 22px 30px;
  }
  .heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 18px;
  }
  h1 {
    font-size: 27px;
    font-weight: 650;
    letter-spacing: -1px;
  }
  .heading p {
    margin-top: 6px;
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 18px;
  }
  .metrics div {
    display: grid;
    gap: 6px;
    padding: 14px 16px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  .metrics span {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .metrics strong {
    font-size: 24px;
    font-weight: 650;
  }
  .ok {
    color: rgb(var(--success));
  }
  .warn {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .bad {
    color: rgb(var(--danger));
  }
  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 14px;
  }
  .search {
    display: flex;
    flex: 1;
    align-items: center;
    gap: 8px;
    min-width: 240px;
    max-width: 420px;
    padding: 0 12px;
    border: 1px solid rgb(var(--border));
    border-radius: 9px;
    color: rgb(var(--foreground-muted));
  }
  .search input {
    flex: 1;
    height: 38px;
    border: 0;
    background: transparent;
    color: rgb(var(--foreground));
    outline: none;
    font-size: 13px;
  }
  select,
  input:not([type='search']),
  textarea {
    min-height: 38px;
    padding: 0 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  textarea {
    padding: 8px 10px;
  }
  .table-wrap {
    overflow-x: auto;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface));
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  th {
    padding: 11px 14px;
    border-bottom: 1px solid rgb(var(--border));
    font-size: 11px;
    font-weight: 600;
    text-align: left;
    color: rgb(var(--foreground-muted));
  }
  td {
    padding: 11px 14px;
    border-bottom: 1px solid rgb(var(--border));
    vertical-align: middle;
  }
  tr:last-child td {
    border-bottom: 0;
  }
  .person {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .person span:not(.avatar) {
    display: grid;
  }
  .person img,
  .avatar {
    flex-shrink: 0;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    object-fit: cover;
  }
  .avatar {
    display: grid;
    place-items: center;
    border: 1px solid rgb(var(--border));
    background: rgb(var(--surface-hover));
    font-size: 11px;
    font-weight: 600;
  }
  small {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .block {
    display: block;
  }
  .pill {
    padding: 3px 8px;
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
  .issue {
    display: inline-block;
    max-width: 280px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
  }
  .issue.blocking {
    color: rgb(var(--danger));
  }
  .issue.warning {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .issue.ok {
    color: rgb(var(--success));
  }
  .empty {
    display: grid;
    justify-items: center;
    gap: 6px;
    padding: 48px 16px;
    border: 1px dashed rgb(var(--border-strong));
    border-radius: 12px;
    text-align: center;
    color: rgb(var(--foreground-muted));
  }
  .empty h3 {
    color: rgb(var(--foreground));
    font-size: 15px;
  }
  .error {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
    padding: 10px 12px;
    border: 1px solid rgb(var(--danger) / 0.3);
    border-radius: 9px;
    background: rgb(var(--danger) / 0.07);
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .muted,
  .hint {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  .refreshing {
    opacity: 0.6;
  }
  .pager {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
    font-size: 12px;
  }
  .form {
    display: grid;
    gap: 12px;
  }
  .form label {
    display: grid;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
  }
  .candidates {
    display: grid;
    gap: 6px;
    max-height: 240px;
    overflow-y: auto;
  }
  .candidates button {
    display: grid;
    gap: 2px;
    padding: 9px 11px;
    border: 1px solid rgb(var(--border));
    border-radius: 9px;
    text-align: left;
  }
  .candidates button.selected {
    border-color: rgb(var(--primary));
    background: rgb(var(--primary) / 0.08);
  }
  .error-text {
    font-size: 12px;
    color: rgb(var(--danger));
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  @media (max-width: 900px) {
    .drivers {
      padding: 16px;
    }
    .metrics {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
