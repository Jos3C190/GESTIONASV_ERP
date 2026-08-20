<script lang="ts">
  import { HttpError } from '$lib/api/client';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import {
    buildCapacityGroupTree,
    capacityGroupDraftToInput,
    capacityGroupToDraft,
    getCapacityGroupDescendantIds
  } from '../capacity-groups.logic';
  import {
    getCapacityConfigurationDiagnostics,
    listCapacityGroups,
    updateCapacityGroup
  } from '../capacity-groups.service';
  import {
    CAPACITY_GROUP_TYPE_LABEL,
    type CapacityConfigurationIssue,
    type WarehouseCapacityGroup
  } from '../capacity-groups.types';
  import {
    CAPACITY_ENFORCEMENT_LABEL,
    CAPACITY_PROFILE_LABEL,
    CAPACITY_STATUS_LABEL,
    type CapacityStatus,
    type Warehouse
  } from '../types';
  import WarehouseCapacityGroupModal from './WarehouseCapacityGroupModal.svelte';

  interface Props {
    warehouseId: string;
    warehouse: Warehouse;
    canManage?: boolean;
    canViewLocations?: boolean;
  }

  let { warehouseId, warehouse, canManage = false, canViewLocations = false }: Props = $props();

  let groups = $state<WarehouseCapacityGroup[]>([]);
  let diagnosticIssues = $state<CapacityConfigurationIssue[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let success = $state<string | null>(null);
  let modalOpen = $state(false);
  let editingGroup = $state<WarehouseCapacityGroup | null>(null);
  let initialParentId = $state<string | null>(null);
  let changingId = $state<string | null>(null);
  let loadKey = $state('');

  let treeRows = $derived(buildCapacityGroupTree(groups));
  let activeCount = $derived(groups.filter((group) => group.isActive).length);
  let inactiveCount = $derived(groups.length - activeCount);

  $effect(() => {
    if (!warehouseId || loadKey === warehouseId) return;
    loadKey = warehouseId;
    void loadGroups(warehouseId);
  });

  async function loadGroups(requestedWarehouseId = warehouseId) {
    loading = true;
    loadError = null;
    try {
      const [loadedGroups, diagnostics] = await Promise.all([
        listCapacityGroups(requestedWarehouseId),
        getCapacityConfigurationDiagnostics(requestedWarehouseId)
      ]);
      if (requestedWarehouseId === warehouseId) {
        groups = loadedGroups;
        diagnosticIssues = diagnostics.issues;
      }
    } catch (error) {
      if (requestedWarehouseId === warehouseId) {
        loadError =
          error instanceof HttpError
            ? error.message
            : 'No se pudo cargar la estructura de capacidad del almacén.';
      }
    } finally {
      if (requestedWarehouseId === warehouseId) loading = false;
    }
  }

  function openCreate(parentId: string | null = null) {
    editingGroup = null;
    initialParentId = parentId;
    actionError = null;
    success = null;
    modalOpen = true;
  }

  function openEdit(group: WarehouseCapacityGroup) {
    editingGroup = group;
    initialParentId = null;
    actionError = null;
    success = null;
    modalOpen = true;
  }

  function handleSaved(saved: WarehouseCapacityGroup) {
    const existed = groups.some((group) => group.id === saved.id);
    groups = [...groups.filter((group) => group.id !== saved.id), saved];
    modalOpen = false;
    editingGroup = null;
    initialParentId = null;
    actionError = null;
    success = existed
      ? 'Estructura actualizada correctamente.'
      : 'Estructura creada correctamente.';
    void loadGroups();
  }

  async function changeActiveState(group: WarehouseCapacityGroup, isActive: boolean) {
    actionError = null;
    success = null;

    if (!isActive) {
      const activeDescendants = [...getCapacityGroupDescendantIds(groups, group.id)].filter(
        (id) => groups.find((candidate) => candidate.id === id)?.isActive
      );
      if (activeDescendants.length > 0) {
        actionError =
          'No puede desactivar esta estructura mientras tenga subestructuras activas. Muévalas o desactívelas primero.';
        return;
      }
      if (
        !window.confirm(
          `¿Desactivar ${group.code} · ${group.name}? Dejará de estar disponible para nuevas asignaciones.`
        )
      ) {
        return;
      }
    }

    changingId = group.id;
    try {
      const draft = capacityGroupToDraft(group);
      draft.is_active = isActive;
      const saved = await updateCapacityGroup(
        warehouseId,
        group.id,
        capacityGroupDraftToInput(draft)
      );
      groups = [...groups.filter((candidate) => candidate.id !== saved.id), saved];
      success = isActive
        ? 'Estructura reactivada correctamente.'
        : 'Estructura desactivada correctamente.';
      await loadGroups();
    } catch (error) {
      actionError =
        error instanceof HttpError
          ? error.message
          : `No se pudo ${isActive ? 'reactivar' : 'desactivar'} la estructura.`;
    } finally {
      changingId = null;
    }
  }

  function metric(value: number | null, unit: string): string {
    if (value == null) return 'No definido';
    return `${value.toLocaleString('es-SV', { maximumFractionDigits: 3 })} ${unit}`;
  }

  function hasDefinedPhysicalLimit(group: WarehouseCapacityGroup): boolean {
    return [
      group.certifiedMaxWeightKg,
      group.operationalMaxWeightKg,
      group.certifiedUsableVolumeM3,
      group.operationalUsableVolumeM3,
      group.usableLengthM,
      group.usableWidthM,
      group.usableHeightM
    ].some((value) => value != null);
  }

  function capacityVariant(status: CapacityStatus): 'success' | 'warning' | 'danger' | 'neutral' {
    if (status === 'available') return 'success';
    if (status === 'incomplete' || status === 'warning') return 'warning';
    if (
      status === 'critical' ||
      status === 'full' ||
      status === 'over_operational' ||
      status === 'over_certified'
    ) {
      return 'danger';
    }
    return 'neutral';
  }

  function issuesFor(scopeId: string): CapacityConfigurationIssue[] {
    return diagnosticIssues.filter((issue) => issue.scopeId === scopeId);
  }

  function issueText(issue: CapacityConfigurationIssue): string {
    const metric = issue.metric === 'weight' ? 'peso' : 'volumen';
    const kind = issue.limitKind === 'certified' ? 'certificado' : 'operativo';
    if (issue.code === 'nominal_capacity_overallocated') {
      const ratio = issue.allocationRatioPct?.toLocaleString('es-SV', {
        maximumFractionDigits: 1
      });
      return `Los máximos nominales de hijos asignan ${ratio ?? 'más de 100'}% del ${metric} ${kind}. Es una advertencia de planificación; el límite compartido continúa vigente.`;
    }
    if (issue.code === 'parent_limit_not_configured') {
      return `El contenedor superior no tiene configurado el ${metric} ${kind}.`;
    }
    return `El ${metric} ${kind} supera el límite del contenedor superior.`;
  }
</script>

<Card class="overflow-hidden">
  <div
    class="flex flex-col gap-4 border-b border-border px-6 py-5 sm:flex-row sm:items-start sm:justify-between"
  >
    <div>
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-sm font-semibold text-foreground">Estructuras y límites compartidos</h3>
        {#if !loading}
          <Badge variant="neutral">{activeCount} activos</Badge>
          {#if inactiveCount > 0}<Badge variant="neutral">{inactiveCount} inactivos</Badge>{/if}
        {/if}
      </div>
      <p class="mt-1 max-w-3xl text-xs leading-5 text-foreground-muted">
        Una estructura agrupa ubicaciones que comparten una restricción física, como un rack, una
        cámara o una zona de piso. El inventario siempre se guarda en una ubicación.
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      {#if canViewLocations}<a
          href={`/warehouses/${warehouseId}/locations`}
          class="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border bg-surface-elevated px-3 text-xs font-medium text-foreground shadow-soft transition-all duration-150 hover:border-border-strong hover:bg-surface-hover focus-visible:shadow-glow"
        >
          Ver todas las ubicaciones
        </a>{/if}
      {#if canManage}<Button size="sm" onclick={() => openCreate()}>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            aria-hidden="true"
          >
            <path d="M12 5v14M5 12h14" />
          </svg>
          Nueva estructura
        </Button>{/if}
    </div>
  </div>

  <div class="p-6">
    <div
      class="mb-5 grid gap-2 rounded-xl border border-border bg-surface-muted/20 p-3 md:grid-cols-3"
      aria-label="Cómo se aplica la capacidad"
    >
      <div class="rounded-lg bg-surface-elevated px-3 py-2.5">
        <p class="text-xs font-semibold text-foreground">1. Ubicación</p>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Dirección exacta donde se guarda y mueve el inventario.
        </p>
      </div>
      <div class="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2.5">
        <p class="text-xs font-semibold text-primary">2. Estructura compartida</p>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Controla en conjunto las ubicaciones vinculadas a un rack, nivel o zona.
        </p>
      </div>
      <div class="rounded-lg bg-surface-elevated px-3 py-2.5">
        <p class="text-xs font-semibold text-foreground">3. Almacén</p>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Mantiene el límite general de toda la instalación.
        </p>
      </div>
      <p class="text-xs leading-5 text-foreground-muted md:col-span-3">
        Al ingresar mercancía, el sistema comprueba los tres niveles. Sus máximos son restricciones
        independientes y no se suman automáticamente.
      </p>
    </div>
    {#if diagnosticIssues.length > 0}
      <div class="mb-5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3" role="status">
        <p class="text-xs font-semibold text-warning">
          {diagnosticIssues.length} aviso(s) de configuración jerárquica
        </p>
        <p class="mt-1 text-xs leading-5 text-foreground-muted">
          Las sobreasignaciones nominales son advertencias; los límites hijo–padre incompatibles
          deben corregirse antes de modificar su capacidad.
        </p>
      </div>
    {/if}
    {#if success}
      <div
        class="mb-4 flex items-center gap-2 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
        role="status"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg
        >
        {success}
      </div>
    {/if}
    {#if actionError}
      <div
        class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {actionError}
      </div>
    {/if}

    {#if loading}
      <div class="space-y-3" aria-label="Cargando estructuras de capacidad">
        {#each Array(3) as _}
          <div class="rounded-xl border border-border p-4">
            <div class="skeleton h-4 w-48 rounded"></div>
            <div class="mt-3 grid gap-2 sm:grid-cols-4">
              <div class="skeleton h-8 rounded"></div>
              <div class="skeleton h-8 rounded"></div>
              <div class="skeleton h-8 rounded"></div>
              <div class="skeleton h-8 rounded"></div>
            </div>
          </div>
        {/each}
      </div>
    {:else if loadError}
      <div class="rounded-xl border border-danger/30 bg-danger/10 p-5" role="alert">
        <p class="text-sm font-semibold text-danger">No se pudieron cargar las estructuras</p>
        <p class="mt-1 text-xs leading-5 text-danger/90">{loadError}</p>
        <div class="mt-4">
          <Button variant="secondary" size="sm" onclick={() => void loadGroups()}>Reintentar</Button
          >
        </div>
      </div>
    {:else if groups.length === 0}
      <div
        class="flex flex-col items-center rounded-xl border border-dashed border-border px-6 py-10 text-center"
      >
        <div
          class="flex h-11 w-11 items-center justify-center rounded-xl bg-surface-muted text-foreground-muted"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"><path d="M4 21V8l8-5 8 5v13M4 12h16M8 12v9M16 12v9" /></svg
          >
        </div>
        <p class="mt-3 text-sm font-semibold text-foreground">Aún no hay estructuras compartidas</p>
        <p class="mt-1 max-w-md text-xs leading-5 text-foreground-muted">
          Cree una estructura cuando varias ubicaciones deban compartir el límite real de un rack,
          una zona o una cámara. Un almacén pequeño puede operar sin esta subdivisión.
        </p>
        {#if canManage}
          <div class="mt-4">
            <Button size="sm" onclick={() => openCreate()}>Crear primera estructura</Button>
          </div>
        {/if}
      </div>
    {:else}
      <div class="space-y-2" role="tree" aria-label="Jerarquía de capacidad">
        {#each treeRows as row (row.group.id)}
          <div style={`padding-left: ${Math.min(row.depth, 8) * 22}px;`}>
            <div
              class="rounded-xl border border-border bg-surface px-4 py-3 {row.group.isActive
                ? ''
                : 'opacity-65'}"
              role="treeitem"
              aria-level={row.depth + 1}
              aria-selected={false}
              aria-label={`${row.group.code}, ${row.group.name}`}
            >
              <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    {#if row.depth > 0}
                      <span class="font-mono text-sm text-foreground-subtle" aria-hidden="true"
                        >└</span
                      >
                    {/if}
                    <span class="font-mono text-xs font-bold text-foreground">{row.group.code}</span
                    >
                    <span class="text-sm font-semibold text-foreground">{row.group.name}</span>
                    <Badge variant="neutral">{CAPACITY_GROUP_TYPE_LABEL[row.group.groupType]}</Badge
                    >
                    <Badge variant={row.group.isActive ? 'success' : 'neutral'}>
                      {row.group.isActive ? 'Activo' : 'Inactivo'}
                    </Badge>
                    <Badge variant={capacityVariant(row.group.capacityStatus)}>
                      {CAPACITY_STATUS_LABEL[row.group.capacityStatus]}
                    </Badge>
                  </div>
                  <div class="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    <div class="rounded-lg bg-surface-muted/50 px-3 py-2">
                      <p
                        class="text-[10px] font-bold uppercase tracking-wide text-foreground-subtle"
                      >
                        Peso
                      </p>
                      <p class="mt-1 text-xs text-foreground">
                        <span class="text-foreground-muted">Operativo:</span>
                        {metric(row.group.operationalMaxWeightKg, 'kg')}
                      </p>
                      <p class="mt-0.5 text-xs text-foreground">
                        <span class="text-foreground-muted">Certificado:</span>
                        {metric(row.group.certifiedMaxWeightKg, 'kg')}
                      </p>
                    </div>
                    <div class="rounded-lg bg-surface-muted/50 px-3 py-2">
                      <p
                        class="text-[10px] font-bold uppercase tracking-wide text-foreground-subtle"
                      >
                        Volumen útil
                      </p>
                      <p class="mt-1 text-xs text-foreground">
                        <span class="text-foreground-muted">Operativo:</span>
                        {metric(row.group.operationalUsableVolumeM3, 'm³')}
                      </p>
                      <p class="mt-0.5 text-xs text-foreground">
                        <span class="text-foreground-muted">Certificado:</span>
                        {metric(row.group.certifiedUsableVolumeM3, 'm³')}
                      </p>
                    </div>
                    <div class="rounded-lg bg-surface-muted/50 px-3 py-2">
                      <p
                        class="text-[10px] font-bold uppercase tracking-wide text-foreground-subtle"
                      >
                        Configuración
                      </p>
                      <p class="mt-1 text-xs text-foreground">
                        {CAPACITY_PROFILE_LABEL[row.group.capacityProfile]}
                      </p>
                      <p class="mt-0.5 text-xs text-foreground-muted">
                        {CAPACITY_ENFORCEMENT_LABEL[row.group.capacityEnforcementMode]}
                      </p>
                    </div>
                    <div class="rounded-lg bg-surface-muted/50 px-3 py-2">
                      <p
                        class="text-[10px] font-bold uppercase tracking-wide text-foreground-subtle"
                      >
                        Uso físico
                      </p>
                      <p class="mt-1 text-xs text-foreground">
                        {row.group.storageEligible ? 'Apto para mercancía' : 'No almacenable'}
                      </p>
                      <p class="mt-0.5 text-xs text-foreground-muted">
                        {row.group.usableLengthM == null ||
                        row.group.usableWidthM == null ||
                        row.group.usableHeightM == null
                          ? 'Dimensiones no definidas'
                          : `${metric(row.group.usableLengthM, 'm')} × ${metric(row.group.usableWidthM, 'm')} × ${metric(row.group.usableHeightM, 'm')}`}
                      </p>
                    </div>
                  </div>
                  <div
                    class="mt-3 rounded-lg border px-3 py-2 text-xs leading-5 {hasDefinedPhysicalLimit(
                      row.group
                    )
                      ? 'border-primary/20 bg-primary/5 text-foreground-muted'
                      : 'border-warning/30 bg-warning/10 text-warning'}"
                  >
                    {hasDefinedPhysicalLimit(row.group)
                      ? 'Este límite se aplica al consumo combinado de las ubicaciones vinculadas; la estructura no almacena inventario directamente.'
                      : 'Por ahora esta estructura solo organiza ubicaciones: no controla peso, volumen ni dimensiones hasta que configure un límite físico.'}
                  </div>
                  <div
                    class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-foreground-muted"
                  >
                    <span>{row.group.directLocationCount} ubicación(es) directas</span>
                    <span>{row.group.subtreeLocationCount} en esta estructura y subestructuras</span
                    >
                    {#if canViewLocations}<a
                        href={`/warehouses/${warehouseId}/locations?capacity_group_id=${encodeURIComponent(row.group.id)}&include_descendants=true`}
                        class="font-medium text-primary underline-offset-2 hover:underline focus-visible:shadow-glow"
                      >
                        Ver ubicaciones
                      </a>{/if}
                  </div>
                  {#if row.orphaned}
                    <p class="mt-2 text-xs text-warning">
                      La relación jerárquica de esta estructura necesita revisión.
                    </p>
                  {/if}
                  {#each issuesFor(row.group.id) as issue}
                    <p
                      class="mt-2 rounded-lg border px-3 py-2 text-xs leading-5 {issue.severity ===
                      'error'
                        ? 'border-danger/30 bg-danger/10 text-danger'
                        : 'border-warning/30 bg-warning/10 text-warning'}"
                      role={issue.severity === 'error' ? 'alert' : 'status'}
                    >
                      {issueText(issue)}
                    </p>
                  {/each}
                </div>

                {#if canManage}
                  <div class="flex flex-wrap items-center gap-1.5 lg:justify-end">
                    {#if row.group.isActive}
                      <Button variant="ghost" size="sm" onclick={() => openCreate(row.group.id)}>
                        Añadir subestructura
                      </Button>
                    {/if}
                    <Button variant="secondary" size="sm" onclick={() => openEdit(row.group)}>
                      Editar
                    </Button>
                    {#if row.group.isActive}
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={changingId === row.group.id}
                        onclick={() => void changeActiveState(row.group, false)}
                      >
                        {changingId === row.group.id ? 'Desactivando…' : 'Desactivar'}
                      </Button>
                    {:else}
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={changingId === row.group.id}
                        onclick={() => void changeActiveState(row.group, true)}
                      >
                        {changingId === row.group.id ? 'Reactivando…' : 'Reactivar'}
                      </Button>
                    {/if}
                  </div>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</Card>

{#if canManage}
  <WarehouseCapacityGroupModal
    open={modalOpen}
    {warehouseId}
    {warehouse}
    {groups}
    group={editingGroup}
    {initialParentId}
    onclose={() => {
      modalOpen = false;
      editingGroup = null;
      initialParentId = null;
    }}
    onsaved={handleSaved}
  />
{/if}
