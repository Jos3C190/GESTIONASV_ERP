<script lang="ts">
  import type { GeofenceOut, SiteOut, SitesOut } from '$lib/api/client';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { describeShape, type DraftKind, type GeofenceDraft } from './geofences';

  let {
    geofences,
    canManage,
    draft,
    saving = false,
    error = null,
    highlighted = null,
    onstartdraw,
    onundo,
    onradius,
    oncancel,
    onsave,
    ondelete,
    onfocus,
    sites = null,
    canSync = false,
    syncing = false,
    onsync,
    onfocussite
  }: {
    geofences: GeofenceOut[];
    canManage: boolean;
    draft: GeofenceDraft | null;
    saving?: boolean;
    error?: string | null;
    highlighted?: number | null;
    onstartdraw: (kind: DraftKind) => void;
    onundo: () => void;
    onradius: (radiusM: number) => void;
    oncancel: () => void;
    onsave: (data: {
      name: string;
      description: string;
      speedLimit: number | null;
      branchId: string | null;
    }) => void;
    ondelete: (geofence: GeofenceOut) => void;
    onfocus: (geofence: GeofenceOut) => void;
    /** Capa fija de sucursales y almacenes con su estado de sincronización. */
    sites?: SitesOut | null;
    canSync?: boolean;
    syncing?: boolean;
    onsync?: () => void;
    onfocussite?: (site: SiteOut) => void;
  } = $props();

  let sitesOpen = $state(true);

  const syncLabel = $derived.by(() => {
    if (!sites) return '';
    if (!sites.sync.configured) return 'Servidor GPS sin configurar: sin eventos de llegada.';
    if (sites.sync.error) return 'Geocercas de sucursales pendientes de sincronizar.';
    return sites.sync.synced_at ? 'Geocercas de llegada sincronizadas.' : 'Sincronizando…';
  });

  let name = $state('');
  let description = $state('');
  let speedLimit = $state('');
  /** '' = toda la empresa. */
  let scopeBranch = $state('');
  let confirmDelete = $state<number | null>(null);

  const ready = $derived(
    !!draft &&
      (draft.kind === 'circle' ? draft.vertices.length >= 1 : draft.vertices.length >= 3) &&
      name.trim().length > 0
  );

  const hint = $derived.by(() => {
    if (!draft) return '';
    if (draft.kind === 'circle')
      return draft.vertices.length
        ? 'Haz clic de nuevo para fijar el radio o ajústalo abajo.'
        : 'Haz clic en el mapa para colocar el centro.';
    const missing = 3 - draft.vertices.length;
    return missing > 0
      ? `Haz clic en el mapa para agregar vértices (faltan ${missing}).`
      : 'Sigue agregando vértices o haz doble clic para cerrar la figura.';
  });

  function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!ready) return;
    const limit = Number.parseInt(speedLimit, 10);
    onsave({
      name: name.trim(),
      description: description.trim(),
      speedLimit: Number.isFinite(limit) ? limit : null,
      branchId: scopeBranch || null
    });
  }

  $effect(() => {
    if (!draft) {
      name = '';
      description = '';
      speedLimit = '';
      // Por defecto, la sucursal operativa; toda la empresa solo para quien ve todas.
      scopeBranch = branch.id ?? (branch.accessAllBranches ? '' : (branch.branches[0]?.id ?? ''));
    }
  });
</script>

{#if draft}
  <form class="draft" onsubmit={submit}>
    <div class="draft-head">
      <strong>Nueva geocerca</strong>
      <div class="kind-switch" role="group" aria-label="Tipo de geocerca">
        <button
          type="button"
          class:active={draft.kind === 'polygon'}
          aria-pressed={draft.kind === 'polygon'}
          onclick={() => onstartdraw('polygon')}>Polígono</button
        >
        <button
          type="button"
          class:active={draft.kind === 'circle'}
          aria-pressed={draft.kind === 'circle'}
          onclick={() => onstartdraw('circle')}>Círculo</button
        >
      </div>
    </div>
    <p class="hint"><FleetIcon name="info" size={13} />{hint}</p>
    {#if draft.kind === 'circle' && draft.vertices.length}
      <label class="field">
        <span>Radio (m)</span>
        <input
          type="number"
          min="20"
          max="100000"
          step="10"
          value={Math.round(draft.radiusM)}
          oninput={(event) => onradius(Number(event.currentTarget.value) || 20)}
        />
      </label>
    {/if}
    <label class="field">
      <span>Nombre</span>
      <input bind:value={name} maxlength="120" placeholder="Ej. Centro de distribución" required />
    </label>
    <label class="field">
      <span>Aplica a</span>
      <select bind:value={scopeBranch}>
        {#if branch.accessAllBranches}<option value="">Toda la empresa</option>{/if}
        {#each branch.branches as item (item.id)}
          <option value={item.id}>{item.name}</option>
        {/each}
      </select>
    </label>
    <label class="field">
      <span>Descripción <em>opcional</em></span>
      <input bind:value={description} maxlength="500" />
    </label>
    <label class="field">
      <span>Límite de velocidad dentro (km/h) <em>opcional</em></span>
      <input bind:value={speedLimit} type="number" min="5" max="200" placeholder="Sin límite" />
    </label>
    {#if error}<p class="error">{error}</p>{/if}
    <div class="draft-actions">
      <button type="button" onclick={oncancel}>Cancelar</button>
      <button type="button" disabled={!draft.vertices.length} onclick={onundo}
        >Deshacer punto</button
      >
      <button type="submit" class="primary" disabled={!ready || saving}
        >{saving ? 'Guardando…' : 'Guardar'}</button
      >
    </div>
  </form>
{:else}
  <div class="content">
    {#if sites}
      <section class="group" aria-labelledby="sites-heading">
        <button
          type="button"
          class="group-head"
          aria-expanded={sitesOpen}
          onclick={() => (sitesOpen = !sitesOpen)}
        >
          <span class="group-title">
            <strong id="sites-heading">Sucursales y almacenes</strong>
            <span class="count">{sites.sites.length}</span>
          </span>
          <span class="chevron" class:open={sitesOpen}><FleetIcon name="chevron" size={14} /></span>
        </button>
        <p class="group-note">Automáticas · se administran en Sucursales y Almacenes</p>
        <p class="sync" class:warn={!!sites.sync.error || !sites.sync.configured}>
          <span class="dot"></span>
          <span class="sync-text">{syncLabel}</span>
          {#if canSync && sites.sync.configured && sites.sync.error}
            <button type="button" disabled={syncing} onclick={() => onsync?.()}
              >{syncing ? 'Reintentando…' : 'Reintentar'}</button
            >
          {/if}
        </p>
        {#if sitesOpen}
          <ul class="list">
            {#each sites.sites as site (site.id)}
              <li>
                <button type="button" class="row" onclick={() => onfocussite?.(site)}>
                  <span class="swatch site" class:warehouse={site.kind === 'warehouse'}></span>
                  <span class="main">
                    <strong title={site.name}
                      >{site.kind === 'branch' ? 'Sucursal' : 'Almacén'} {site.name}</strong
                    >
                    <span
                      >Radio {site.radius_m} m{site.kind === 'branch' && site.warehouses.length
                        ? ` · ${site.warehouses.length} ${site.warehouses.length === 1 ? 'almacén' : 'almacenes'}`
                        : site.kind === 'warehouse'
                          ? ` · ${site.branch_name}`
                          : ''}</span
                    >
                  </span>
                </button>
              </li>
            {:else}
              <li class="empty">Aún no hay sucursales con ubicación en el mapa.</li>
            {/each}
          </ul>
          {#if sites.missing.length}
            <p class="missing">
              <FleetIcon name="alert" size={13} />
              <span
                >Sin ubicación en el mapa: {sites.missing
                  .map((item) => `${item.kind === 'branch' ? 'Sucursal' : 'Almacén'} ${item.name}`)
                  .join(', ')}. Complétala en <a href="/branches">Sucursales</a> o
                <a href="/warehouses">Almacenes</a>.</span
              >
            </p>
          {/if}
        {/if}
      </section>
    {/if}

    <section class="group" aria-labelledby="custom-heading">
      <div class="group-head static">
        <span class="group-title">
          <strong id="custom-heading">Geocercas personalizadas</strong>
          <span class="count">{geofences.length}</span>
        </span>
        {#if canManage}
          <button type="button" class="primary" onclick={() => onstartdraw('polygon')}
            ><FleetIcon name="plus" size={14} />Nueva</button
          >
        {/if}
      </div>
      {#if error}<p class="error inline">{error}</p>{/if}
      <ul class="list">
        {#each geofences as geofence (geofence.id)}
          <li class:highlighted={highlighted === geofence.id}>
            <button type="button" class="row" onclick={() => onfocus(geofence)}>
              <span class="swatch" class:circle={geofence.shape.type === 'circle'}></span>
              <span class="main">
                <strong>{geofence.name}</strong>
                <span
                  >{describeShape(geofence.shape)} · {geofence.branch_name ??
                    'Toda la empresa'}</span
                >
                {#if geofence.speed_limit_kmh}<span class="limit"
                    >Máx. {geofence.speed_limit_kmh} km/h</span
                  >{/if}
              </span>
            </button>
            {#if canManage && geofence.can_manage}
              {#if confirmDelete === geofence.id}
                <span class="confirm">
                  <button type="button" class="danger" onclick={() => ondelete(geofence)}
                    >Eliminar</button
                  >
                  <button type="button" onclick={() => (confirmDelete = null)}>No</button>
                </span>
              {:else}
                <button
                  type="button"
                  class="icon"
                  aria-label={`Eliminar ${geofence.name}`}
                  onclick={() => (confirmDelete = geofence.id)}
                  ><FleetIcon name="trash" size={14} /></button
                >
              {/if}
            {/if}
          </li>
        {:else}
          <li class="empty">
            Aún no hay geocercas. {canManage
              ? 'Dibuja una para recibir alertas cuando una unidad entre o salga.'
              : ''}
          </li>
        {/each}
      </ul>
    </section>
  </div>
{/if}

<style>
  button.primary {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 10px;
    border-radius: 7px;
    background: rgb(var(--foreground));
    color: rgb(var(--surface));
    font-size: 12px;
    font-weight: 600;
  }
  button.primary:disabled {
    opacity: 0.45;
  }
  .list {
    margin: 0;
    padding: 0 6px;
    list-style: none;
  }
  .list li {
    display: flex;
    align-items: center;
    gap: 4px;
    border-radius: 9px;
  }
  .list li:hover,
  .list li.highlighted {
    background: rgb(var(--surface-hover));
  }
  .row {
    display: flex;
    flex: 1;
    align-items: center;
    gap: 10px;
    min-width: 0;
    padding: 9px 8px;
    text-align: left;
  }
  .swatch {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    border: 2px solid #7c3aed;
    border-radius: 6px;
    background: rgb(124 58 237 / 0.15);
    transform: rotate(-8deg);
  }
  .swatch.circle {
    border-radius: 50%;
    transform: none;
  }
  .main {
    display: grid;
    gap: 2px;
    min-width: 0;
  }
  .main strong {
    font-size: 13px;
    font-weight: 600;
  }
  .main span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .main .limit {
    color: rgb(var(--fleet-warning-ink, var(--warning)));
  }
  .icon {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    margin-right: 4px;
    border-radius: 7px;
    color: rgb(var(--foreground-muted));
  }
  .icon:hover {
    color: rgb(var(--danger));
    background: rgb(var(--danger) / 0.08);
  }
  .confirm {
    display: flex;
    gap: 4px;
    margin-right: 6px;
  }
  .confirm button {
    padding: 4px 7px;
    border: 1px solid rgb(var(--border));
    border-radius: 6px;
    font-size: 11px;
  }
  .confirm .danger {
    border-color: rgb(var(--danger));
    background: rgb(var(--danger));
    color: #fff;
  }
  .empty {
    padding: 24px 12px;
    font-size: 12px;
    line-height: 1.5;
    text-align: center;
    color: rgb(var(--foreground-muted));
  }
  .draft {
    display: grid;
    gap: 10px;
    padding: 12px;
    overflow-y: auto;
  }
  .draft-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 13px;
  }
  .kind-switch {
    display: flex;
    padding: 2px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
  }
  .kind-switch button {
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .kind-switch .active {
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  .hint {
    display: flex;
    gap: 6px;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgb(245 158 11 / 0.1);
    font-size: 11px;
    line-height: 1.5;
  }
  .field {
    display: grid;
    gap: 4px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .field em {
    font-style: normal;
    opacity: 0.7;
  }
  .field input,
  .field select {
    height: 34px;
    padding: 0 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: transparent;
    color: rgb(var(--foreground));
    font-size: 12px;
  }
  .field input:focus {
    outline: none;
    border-color: rgb(var(--primary));
  }
  .draft-actions {
    display: flex;
    gap: 6px;
    justify-content: flex-end;
  }
  .draft-actions button:not(.primary) {
    padding: 6px 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 7px;
    font-size: 12px;
  }
  .draft-actions button:disabled {
    opacity: 0.45;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .error.inline {
    padding: 0 14px 8px;
  }
  button:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
  .content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
  }
  .group {
    padding: 4px 0 8px;
  }
  .group + .group {
    border-top: 1px solid rgb(var(--border));
  }
  .group-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    min-height: 44px;
    padding: 8px 14px;
    text-align: left;
  }
  button.group-head:hover .chevron {
    color: rgb(var(--foreground));
  }
  .group-title {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    font-size: 13px;
  }
  .group-title strong {
    font-weight: 600;
  }
  .count {
    padding: 1px 7px;
    border-radius: 999px;
    background: rgb(var(--surface-hover));
    font-size: 11px;
    font-weight: 600;
    color: rgb(var(--foreground-muted));
  }
  .chevron {
    display: grid;
    place-items: center;
    color: rgb(var(--foreground-muted));
    transition: transform 0.15s ease;
  }
  .chevron.open {
    transform: rotate(90deg);
  }
  .group-note,
  .sync,
  .missing {
    margin: 0;
    padding: 0 14px;
    font-size: 11px;
    line-height: 1.45;
    color: rgb(var(--foreground-muted));
  }
  .sync {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 4px 0 6px;
  }
  .sync .dot {
    flex-shrink: 0;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgb(var(--success));
  }
  .sync.warn {
    color: rgb(var(--warning));
  }
  .sync.warn .dot {
    background: rgb(var(--warning));
  }
  .sync-text {
    flex: 1;
    min-width: 0;
  }
  .sync button,
  .missing a {
    flex-shrink: 0;
    font-weight: 600;
    color: rgb(var(--primary));
  }
  .missing {
    display: flex;
    gap: 6px;
    margin: 6px 14px 0;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgb(var(--warning) / 0.08);
    color: rgb(var(--warning));
  }
  .missing :global(svg) {
    flex-shrink: 0;
    margin-top: 1px;
  }
  .swatch.site {
    border-color: #0f766e;
    border-style: dashed;
    background: rgb(15 118 110 / 0.12);
  }
  .swatch.site.warehouse {
    border-color: #b45309;
    background: rgb(180 83 9 / 0.12);
  }
</style>
