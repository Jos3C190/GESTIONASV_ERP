<script lang="ts">
  import { goto } from '$app/navigation';
  import {
    api,
    HttpError,
    type EmployeeOut,
    type DepartmentOut,
    type UserOut,
    type Page
  } from '$lib/api/client';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { resolvePhotoUrl, initialsOf } from '$lib/features/employees/avatar';
  import { untrack } from 'svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Avatar from '$lib/components/ui/Avatar.svelte';
  import KebabMenu from '$lib/components/ui/KebabMenu.svelte';
  import type { KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';

  let employees = $state<EmployeeOut[]>([]);
  let meta = $state<{ page: number; size: number; total: number; pages: number } | null>(null);
  let departments = $state<DepartmentOut[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let page = $state(1);
  let size = $state(10);
  let deptFilter = $state('');
  let statusFilter = $state('');
  let actionLoading = $state<string | null>(null);

  // KPI stats del sistema completo (independientes de la paginación)
  let kpiTotal = $state(0);
  let kpiActive = $state(0);
  let kpiVacations = $state(0);
  let kpiLinked = $state(0);

  // Modal solo para vincular usuario
  let showLinkModal = $state(false);
  let linkEmp = $state<EmployeeOut | null>(null);
  let users = $state<UserOut[]>([]);
  let fLinkUserId = $state('');
  let linkError = $state<string | null>(null);
  let linkLoading = $state(false);

  /** Carga la página actual de la tabla. NO toca page — el caller lo establece. */
  async function loadData() {
    loading = true;
    error = null;
    try {
      const [empResult, deptResult] = await Promise.all([
        api.employees.list({
          page: untrack(() => page),
          size,
          search: globalSearch.query || undefined,
          department_id: deptFilter || undefined,
          status: statusFilter || undefined
        }),
        api.departments.list()
      ]);
      employees = empResult.items;
      meta = empResult.meta;
      departments = deptResult;
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      loading = false;
    }
  }

  /** Carga estadísticas globales para los KPIs mediante un único GROUP BY en la BD. */
  async function loadKpis() {
    try {
      const s = await api.employees.stats();
      kpiTotal = s.total;
      kpiActive = s.active;
      kpiVacations = s.on_leave;
      kpiLinked = s.linked_to_user;
    } catch {
      /* silencioso — los KPIs no son críticos */
    }
  }

  function goToPage(p: number) {
    if (p < 1 || (meta && p > meta.pages)) return;
    page = p;
    // Llamamos loadData directamente SIN pasar por el $effect para no resetear page.
    loadData();
  }
  function deptName(id: string | null): string {
    if (!id) return '—';
    return departments.find((d) => d.id === id)?.name ?? '—';
  }
  function statusBadge(s: string): string {
    const m: Record<string, string> = {
      activo: 'badge-success',
      inactivo: 'badge-neutral',
      vacaciones: 'badge-warning',
      baja: 'badge-danger'
    };
    return m[s] ?? 'badge-neutral';
  }

  async function openLink(e: EmployeeOut) {
    linkEmp = e;
    showLinkModal = true;
    linkError = null;
    fLinkUserId = '';
    try {
      const r = await api.users.list({ size: 100 });
      users = r.items;
    } catch {
      users = [];
    }
  }
  function closeLinkModal() {
    showLinkModal = false;
    linkEmp = null;
    linkError = null;
  }

  async function handleLink() {
    if (!linkEmp || !fLinkUserId) return;
    linkLoading = true;
    linkError = null;
    try {
      await api.employees.linkUser(linkEmp.id, fLinkUserId);
      success = 'Usuario vinculado correctamente.';
      closeLinkModal();
      await Promise.all([loadData(), loadKpis()]);
    } catch (err) {
      linkError = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      linkLoading = false;
    }
  }

  async function deleteEmp(e: EmployeeOut) {
    if (!confirm(`¿Eliminar al empleado "${e.first_name} ${e.last_name}"?`)) return;
    actionLoading = e.id;
    try {
      await api.employees.delete(e.id);
      success = 'Empleado eliminado correctamente.';
      await Promise.all([loadData(), loadKpis()]);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      actionLoading = null;
    }
  }

  async function unlinkEmp(e: EmployeeOut) {
    if (!confirm('¿Desvincular la cuenta de usuario de este empleado?')) return;
    actionLoading = e.id;
    try {
      await api.employees.unlinkUser(e.id);
      success = 'Usuario desvinculado correctamente.';
      await Promise.all([loadData(), loadKpis()]);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'Error.';
    } finally {
      actionLoading = null;
    }
  }

  function menuItems(emp: EmployeeOut): KebabItem[] {
    const items: KebabItem[] = [
      {
        id: 'detail',
        label: 'Ver detalle',
        icon: 'detail',
        onClick: () => goto(`/employees/${emp.id}`)
      }
    ];
    if (permissions.hasPermission('employees:update')) {
      items.push(
        {
          id: 'edit',
          label: 'Editar',
          icon: 'edit',
          onClick: () => goto(`/employees/${emp.id}/edit`)
        },
        {
          id: 'link',
          label: emp.user_id ? 'Desvincular usuario' : 'Vincular usuario',
          icon: emp.user_id ? 'unlink' : 'link',
          onClick: () => (emp.user_id ? unlinkEmp(emp) : openLink(emp))
        }
      );
    }
    if (permissions.hasPermission('employees:delete')) {
      items.push({
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => deleteEmp(emp)
      });
    }
    return items;
  }

  // Sólo rastrear filtros y búsqueda. Cuando cambian: resetear a página 1 y recargar.
  // untrack() dentro de loadData evita que `page` quede registrado como dependencia del effect.
  $effect(() => {
    // Leer las dependencias que SÍ queremos rastrear:
    const _q = globalSearch.query;
    const _d = deptFilter;
    const _s = statusFilter;
    // El resto se ejecuta fuera del sistema de tracking:
    untrack(() => {
      page = 1;
      loadData();
      loadKpis();
    });
  });

  // --- KPI derivados de los datos globales (independientes de la página) ---
  const ringR = 16;
  const ringC = 2 * Math.PI * ringR;
  let ringOffset = $derived(kpiTotal > 0 ? ringC - (kpiActive / kpiTotal) * ringC : ringC);
  let linkedRatio = $derived(kpiTotal > 0 ? Math.round((kpiLinked / kpiTotal) * 100) : 0);
</script>

<svelte:head><title>Empleados — ERP System</title></svelte:head>

<div class="p-6 md:p-8">
  <!-- Header -->
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">
      {meta ? `${meta.total} empleado(s)` : 'Cargando...'}
    </p>
    <div class="flex items-center gap-2">
      <select
        bind:value={deptFilter}
        onchange={() => {
          page = 1;
          loadData();
        }}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value="">Todos los deptos</option>
        {#each departments as d (d.id)}<option value={d.id}>{d.name}</option>{/each}
      </select>
      <select
        bind:value={statusFilter}
        onchange={() => {
          page = 1;
          loadData();
        }}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value="">Todos</option>
        <option value="activo">Activos</option>
        <option value="inactivo">Inactivos</option>
        <option value="vacaciones">Vacaciones</option>
        <option value="baja">Baja</option>
      </select>
      {#if permissions.hasPermission('employees:create')}
        <Button size="sm" onclick={() => goto('/employees/new')}>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg
          >
          Crear
        </Button>
      {/if}
    </div>
  </div>

  <!-- FILA DE 4 KPI CARDS -->
  <div class="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <!-- KPI 1: Total empleados -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Total empleados</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle
              cx="9"
              cy="7"
              r="4"
            /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-16 rounded skeleton"
            ></span>{:else}{kpiTotal}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Registrados en el sistema</p>
      </div>
    </div>

    <!-- KPI 2: Empleados activos -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Activos</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-success/10 text-success">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline
              points="22 4 12 14.01 9 11.01"
            /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-10 rounded skeleton"
            ></span>{:else}{kpiActive}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Total en el sistema</p>
      </div>
    </div>

    <!-- KPI 3: En vacaciones -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >En vacaciones</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-warning/10 text-warning">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><path d="M18 8h1a4 4 0 0 1 0 8h-1" /><path
              d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"
            /><line x1="6" y1="1" x2="6" y2="4" /><line x1="10" y1="1" x2="10" y2="4" /><line
              x1="14"
              y1="1"
              x2="14"
              y2="4"
            /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-8 rounded skeleton"
            ></span>{:else}{kpiVacations}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Ausencia temporal</p>
      </div>
    </div>

    <!-- KPI 4: Con usuario vinculado + Mini Ring -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Usuarios vinculados</span
        >
        <div class="font-mono text-lg font-bold text-foreground">
          {#if loading}<span class="inline-block h-5 w-12 rounded skeleton"
            ></span>{:else}{kpiLinked}
            <span class="text-xs font-normal text-foreground-subtle">/ {kpiTotal}</span>{/if}
        </div>
      </div>
      <div class="flex items-center gap-3">
        <!-- Mini Anillo SVG -->
        <svg
          width="40"
          height="40"
          viewBox="0 0 40 40"
          class="-rotate-90 flex-none"
          aria-hidden="true"
        >
          <circle
            cx="20"
            cy="20"
            r={ringR}
            fill="none"
            stroke="rgb(var(--border))"
            stroke-width="4.5"
          />
          <circle
            cx="20"
            cy="20"
            r={ringR}
            fill="none"
            stroke="rgb(var(--primary))"
            stroke-width="4.5"
            stroke-dasharray={ringC.toFixed(1)}
            stroke-dashoffset={ringOffset.toFixed(1)}
            stroke-linecap="round"
            class="transition-all duration-700 ease-out"
          />
        </svg>
        <div class="text-[11px] space-y-0.5 text-foreground-muted">
          <p><strong class="font-semibold text-foreground">{linkedRatio}%</strong> activos</p>
          <p>
            <strong class="font-semibold text-foreground-subtle"
              >{kpiTotal - kpiActive - kpiVacations}</strong
            > inactivos/baja
          </p>
        </div>
      </div>
    </div>
  </div>

  {#if error}<div
      class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>{/if}
  {#if success}<div
      class="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
      role="status"
    >
      {success}
    </div>{/if}

  <Card class="overflow-hidden p-0">
    {#if loading}<div class="flex items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">Cargando...</p>
      </div>
    {:else if employees.length === 0}<div class="flex flex-col items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">No se encontraron empleados.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border bg-surface-muted"
            ><tr
              ><th class="px-4 py-3 text-left font-semibold text-foreground">Código</th><th
                class="px-4 py-3 text-left font-semibold text-foreground">Empleado</th
              ><th class="px-4 py-3 text-left font-semibold text-foreground">Departamento</th><th
                class="px-4 py-3 text-left font-semibold text-foreground">Cargo</th
              ><th class="px-4 py-3 text-left font-semibold text-foreground">Estado</th><th
                class="px-4 py-3 text-left font-semibold text-foreground">Usuario</th
              ><th class="px-2 py-3 text-center font-semibold text-foreground w-11"></th></tr
            ></thead
          >
          <tbody class="divide-y divide-border">
            {#each employees as emp (emp.id)}
              <tr class="hover:bg-surface-muted">
                <td class="px-4 py-3 font-mono text-foreground">{emp.employee_code}</td>
                <td class="px-4 py-3">
                  <button
                    class="flex items-center gap-3 font-medium text-foreground hover:text-primary"
                    onclick={() => goto(`/employees/${emp.id}`)}
                  >
                    <Avatar
                      initials={initialsOf(emp.first_name, emp.last_name)}
                      size={32}
                      src={resolvePhotoUrl(emp.photo_url, emp.id)}
                      alt={`${emp.first_name} ${emp.last_name}`}
                    />
                    {emp.first_name}
                    {emp.last_name}
                  </button>
                </td>
                <td class="px-4 py-3 text-foreground-muted">{deptName(emp.department_id)}</td>
                <td class="px-4 py-3 text-foreground-muted">{emp.position ?? '—'}</td>
                <td class="px-4 py-3"
                  ><span
                    class="{statusBadge(
                      emp.status
                    )} inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                    ><span class="h-1.5 w-1.5 rounded-full bg-current"></span> {emp.status}</span
                  ></td
                >
                <td class="px-4 py-3"
                  >{#if emp.user_id}<span class="text-xs text-success">Vinculado</span>{:else}<span
                      class="text-xs text-foreground-muted">—</span
                    >{/if}</td
                >
                <td class="px-2 py-3 text-center">
                  <KebabMenu items={menuItems(emp)} />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </Card>

  {#if meta && meta.pages > 1}<div class="mt-4 flex items-center justify-between">
      <p class="text-xs text-foreground-muted">Página {meta.page} de {meta.pages}</p>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onclick={() => goToPage(meta!.page - 1)}
          disabled={meta!.page <= 1}>Anterior</Button
        ><Button
          variant="secondary"
          size="sm"
          onclick={() => goToPage(meta!.page + 1)}
          disabled={meta!.page >= meta!.pages}>Siguiente</Button
        >
      </div>
    </div>{/if}
</div>

<Modal open={showLinkModal} title="Vincular usuario" onclose={closeLinkModal}>
  <form
    onsubmit={(e) => {
      e.preventDefault();
      handleLink();
    }}
    class="space-y-4"
  >
    {#if linkError}<div
        class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2 text-sm text-danger"
      >
        {linkError}
      </div>{/if}
    <p class="text-sm text-foreground-muted">
      Selecciona el usuario a vincular con <strong
        >{linkEmp?.first_name} {linkEmp?.last_name}</strong
      >
    </p>
    <FormField
      id="e-link-user"
      label="Usuario"
      bind:value={fLinkUserId}
      options={[
        { value: '', label: '— Seleccionar —' },
        ...users.map((u) => ({ value: u.id, label: `${u.username} (${u.email})` }))
      ]}
    />
    <div class="flex justify-end gap-2 pt-2">
      <Button variant="secondary" onclick={closeLinkModal}>Cancelar</Button><Button
        type="submit"
        disabled={linkLoading || !fLinkUserId}>{linkLoading ? 'Vinculando...' : 'Vincular'}</Button
      >
    </div>
  </form>
</Modal>
