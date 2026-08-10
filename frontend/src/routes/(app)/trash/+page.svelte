<script lang="ts">
  import { api, HttpError, type DeletedRecordOut, type PageMeta } from '$lib/api/client';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { clearPrivateQueryCache } from '$lib/services/query-client';

  const RESOURCE_LABELS: Record<string, string> = {
    companies: 'Empresas', branches: 'Sucursales', warehouse_categories: 'Categorías de almacén',
    warehouses: 'Almacenes', locations: 'Ubicaciones', departments: 'Departamentos',
    employees: 'Empleados', users: 'Usuarios', roles: 'Roles', permissions: 'Permisos personalizados',
    product_categories: 'Categorías de productos', product_subcategories: 'Subcategorías de productos',
    units: 'Unidades personalizadas', products: 'Productos', suppliers: 'Proveedores',
    supplier_contacts: 'Contactos de proveedores'
  };

  const RESTORE_PERMISSIONS: Record<string, string> = {
    companies: 'companies.restore', branches: 'branches.restore',
    warehouse_categories: 'warehouse_categories.restore', warehouses: 'warehouses.restore',
    locations: 'locations.restore', departments: 'departments:restore',
    employees: 'employees:restore', users: 'users:restore', roles: 'roles:restore',
    permissions: 'permissions:restore', product_categories: 'product_categories:restore',
    product_subcategories: 'product_categories:restore', units: 'units:restore',
    products: 'products:restore', suppliers: 'suppliers:restore',
    supplier_contacts: 'suppliers:restore'
  };

  let visibleResources = $derived(
    Object.entries(RESOURCE_LABELS).filter(([resource]) =>
      resource === 'companies'
        ? permissions.isSuperuser
        : permissions.hasPermission(RESTORE_PERMISSIONS[resource] ?? 'lifecycle:read')
    )
  );

  let records = $state<DeletedRecordOut[]>([]);
  let meta = $state<PageMeta>({ page: 1, size: 20, total: 0, pages: 1 });
  let selectedResource = $state('');
  let currentPage = $state(1);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let controller: AbortController | null = null;
  let requestSequence = 0;

  function formatDate(value: string | null): string {
    if (!value) return 'Fecha no disponible';
    return new Intl.DateTimeFormat('es-SV', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
  }

  async function load(query: string, resource: string, page: number) {
    controller?.abort();
    controller = new AbortController();
    const sequence = ++requestSequence;
    loading = true;
    error = null;
    try {
      const result = await api.lifecycle.list({ page, size: 20, search: query || undefined, resource: resource || undefined, signal: controller.signal });
      if (sequence !== requestSequence) return;
      records = result.items;
      meta = result.meta;
      if (currentPage > result.meta.pages) currentPage = result.meta.pages;
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return;
      if (sequence !== requestSequence) return;
      error = cause instanceof HttpError ? cause.message : 'No se pudo cargar la papelera.';
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function restoreRecord(record: DeletedRecordOut) {
    confirmation.request({
      kind: 'restore',
      title: 'Restaurar registro',
      description:
        'El registro volverá a los listados. Por seguridad, restaurarlo no lo activa automáticamente; la activación continúa siendo una acción independiente.',
      resourceName: record.label,
      confirmLabel: 'Restaurar',
      execute: async () => {
        await api.lifecycle.restore(record.resource, record.record_id);
        await clearPrivateQueryCache();
        success = `${record.label} fue restaurado correctamente.`;
        await load(globalSearch.query, selectedResource, currentPage);
      }
    });
  }

  function canRestore(record: DeletedRecordOut): boolean {
    if (record.resource === 'companies') return permissions.isSuperuser;
    const requiredPermission = RESTORE_PERMISSIONS[record.resource];
    return Boolean(requiredPermission && permissions.hasPermission(requiredPermission));
  }

  function changeResource(event: Event) {
    selectedResource = (event.currentTarget as HTMLSelectElement).value;
    currentPage = 1;
  }

  $effect(() => {
    const query = globalSearch.query;
    const resource = selectedResource;
    const page = currentPage;
    void load(query, resource, page);
    return () => controller?.abort();
  });
</script>

<svelte:head><title>Papelera · GestionaSV</title></svelte:head>

<div class="mx-auto w-full max-w-[1500px] p-4 md:p-8">
  <div class="mb-5 flex flex-wrap items-end justify-between gap-4">
    <p class="text-sm text-foreground-muted">{meta.total} registro(s) eliminado(s) · Ocultos de la operación diaria</p>
    <label class="grid gap-1.5 text-xs font-medium text-foreground-muted">
      Tipo de registro
      <select value={selectedResource} onchange={changeResource} class="h-9 min-w-56 rounded-lg border border-border bg-surface-elevated px-3 text-sm text-foreground outline-none focus:border-primary">
        <option value="">Todos los registros</option>
        {#each visibleResources as [value, label]}<option {value}>{label}</option>{/each}
      </select>
    </label>
  </div>

  {#if success}<div class="mb-4 rounded-xl border border-success/25 bg-success/10 px-4 py-3 text-sm text-success" role="status">{success}</div>{/if}
  {#if error}<div class="mb-4 rounded-xl border border-danger/25 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>{/if}

  <section class="overflow-hidden rounded-2xl border border-border bg-surface-elevated">
    {#if loading}
      <div class="grid gap-3 p-5">{#each Array(6) as _}<div class="h-16 rounded-xl skeleton"></div>{/each}</div>
    {:else if records.length === 0}
      <div class="flex min-h-72 flex-col items-center justify-center px-6 text-center">
        <div class="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-success/10 text-success" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5" /></svg></div>
        <h2 class="text-base font-semibold text-foreground">La papelera está vacía</h2>
        <p class="mt-1 max-w-sm text-sm text-foreground-muted">No hay registros eliminados para los filtros seleccionados.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full min-w-[780px] text-left text-sm">
          <thead class="border-b border-border bg-surface-muted/70 text-[11px] uppercase tracking-wide text-foreground-muted"><tr><th class="px-5 py-3 font-semibold">Registro</th><th class="px-5 py-3 font-semibold">Módulo</th><th class="px-5 py-3 font-semibold">Motivo</th><th class="px-5 py-3 font-semibold">Eliminado</th><th class="w-28 px-5 py-3 text-right font-semibold">Acción</th></tr></thead>
          <tbody class="divide-y divide-border">
            {#each records as record (record.resource + record.record_id)}
              <tr class="transition-colors hover:bg-surface-hover/60">
                <td class="max-w-72 px-5 py-4"><p class="truncate font-medium text-foreground" title={record.label}>{record.label}</p><p class="mt-0.5 truncate font-mono text-[11px] text-foreground-subtle">{record.record_id}</p></td>
                <td class="px-5 py-4 text-foreground-muted">{RESOURCE_LABELS[record.resource] ?? record.resource}</td>
                <td class="max-w-80 px-5 py-4 text-foreground-muted"><p class="line-clamp-2" title={record.deletion_reason ?? ''}>{record.deletion_reason ?? 'Sin motivo registrado'}</p></td>
                <td class="whitespace-nowrap px-5 py-4 text-foreground-muted">{formatDate(record.deleted_at)}</td>
                <td class="px-5 py-4 text-right">
                  {#if canRestore(record)}
                    <Button variant="secondary" size="sm" onclick={() => restoreRecord(record)}>Restaurar</Button>
                  {:else}
                    <span class="text-xs text-foreground-subtle">Sin permiso</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>

  {#if !loading && meta.total > 0}
    <div class="mt-4 flex items-center justify-between gap-3 text-xs text-foreground-muted">
      <span>Página {meta.page} de {meta.pages} · {meta.total} registros</span>
      <div class="flex gap-2"><Button variant="secondary" size="sm" disabled={currentPage <= 1} onclick={() => currentPage--}>Anterior</Button><Button variant="secondary" size="sm" disabled={currentPage >= meta.pages} onclick={() => currentPage++}>Siguiente</Button></div>
    </div>
  {/if}
</div>
