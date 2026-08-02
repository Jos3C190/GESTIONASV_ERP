<script lang="ts">
  import { beforeNavigate, goto } from '$app/navigation';
  import { onMount, tick } from 'svelte';
  import { api, HttpError, type EmployeeOut } from '$lib/api/client';
  import { getWarehouse } from '$lib/services/warehouses';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import ChipInput from '$lib/components/ui/ChipInput.svelte';
  import EditorSectionNav from '$lib/components/editor/EditorSectionNav.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import WarehouseImagesEditor from './WarehouseImagesEditor.svelte';
  import type { Warehouse, WarehouseImage } from '../types';

  interface Props {
    mode: 'create' | 'edit';
    warehouseId?: string;
  }
  let { mode, warehouseId }: Props = $props();

  const sections = [
    ['general', 'Información general'],
    ['organization', 'Organización'],
    ['operation', 'Responsable y operación'],
    ['capacity', 'Dimensiones y capacidad'],
    ['security', 'Seguridad'],
    ['environment', 'Condiciones ambientales'],
    ['maintenance', 'Mantenimiento'],
    ['compliance', 'Cumplimiento'],
    ['gallery', 'Galería'],
    ['locations', 'Ubicaciones físicas'],
    ['review', 'Revisión']
  ] as const;
  const SHIFT_OPTIONS = [
    ['mañana', 'Mañana'],
    ['tarde', 'Tarde'],
    ['noche', 'Noche']
  ] as const;
  const enumOptions = (items: [string, string][]) =>
    items.map(([value, label]) => ({ value, label }));
  const empty = () => ({
    branch_id: '',
    warehouse_category_id: '',
    code: '',
    name: '',
    description: '',
    warehouse_type: 'general',
    operational_status: 'active',
    physical_location: '',
    manager_employee_id: '',
    area: '',
    height: '',
    length: '',
    width: '',
    shelves_total: '',
    capacity: '',
    shifts: [] as string[],
    cameras: '',
    access_control: 'sin_control',
    has_alarm: false,
    fire_system: [] as string[],
    last_security_audit: '',
    temperature_range: '',
    humidity_range: '',
    cooling: 'sin_climatizacion',
    has_ventilation: false,
    last_maintenance: '',
    next_maintenance: '',
    maintenance_notes: '',
    sanitary_permit: '',
    sanitary_permit_expiry: '',
    last_inspection: '',
    certifications: [] as string[],
    images: [] as WarehouseImage[]
  });
  let f = $state(empty());
  let loading = $state(true);
  let saving = $state(false);
  let loadingManagers = $state(false);
  let error = $state<string | null>(null);
  let errors = $state<Record<string, string>>({});
  let initialSnapshot = $state('');
  let pendingTarget = $state<string | null>(null);
  let branches = $state<{ id: string; name: string; code?: string; status?: string }[]>([]);
  let categories = $state<
    { id: string; name: string; description: string | null; is_active: boolean }[]
  >([]);
  let managers = $state<EmployeeOut[]>([]);
  let locations = $state<Record<string, unknown>[]>([]);
  let originalImages = $state<WarehouseImage[]>([]);
  let editorHeader: HTMLElement;
  let activeSection = $state('general');
  let canManage = $derived(
    permissions.hasPermission(mode === 'create' ? 'warehouses.create' : 'warehouses.update')
  );
  let canViewLocations = $derived(permissions.hasPermission('locations.view'));
  let dirty = $derived(!loading && initialSnapshot !== JSON.stringify(f));
  let branchOptions = $derived(
    branches.map((item) => ({ value: item.id, label: item.name, description: item.code }))
  );
  let categoryOptions = $derived(
    categories
      .filter((item) => item.is_active || item.id === f.warehouse_category_id)
      .map((item) => ({
        value: item.id,
        label: item.name,
        description: item.description ?? undefined
      }))
  );
  let managerOptions = $derived(
    managers.map((item) => ({
      value: item.id,
      label: `${item.first_name} ${item.last_name}`,
      description: [item.employee_code, item.position].filter(Boolean).join(' · ')
    }))
  );

  function num(value: string) {
    return value === '' ? null : Number(value);
  }
  function dateValue(value: string | null | undefined) {
    return value?.slice(0, 10) ?? '';
  }
  function scrollToSection(id: string, behavior: ScrollBehavior = 'smooth') {
    const target = document.getElementById(id);
    const scrollContainer = target?.closest<HTMLElement>('[data-app-scroll-container]');
    if (!target || !scrollContainer) return;
    const containerRect = scrollContainer.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const requestedTop =
      scrollContainer.scrollTop +
      targetRect.top -
      containerRect.top -
      (editorHeader?.offsetHeight ?? 0) -
      16;
    const maximumTop = Math.max(scrollContainer.scrollHeight - scrollContainer.clientHeight, 0);
    activeSection = id;
    scrollContainer.scrollTo({ top: Math.min(Math.max(requestedTop, 0), maximumTop), behavior });
    history.replaceState(
      history.state,
      '',
      `${window.location.pathname}${window.location.search}#${id}`
    );
  }
  function fromWarehouse(warehouse: Warehouse) {
    f = {
      ...empty(),
      branch_id: warehouse.branchId,
      warehouse_category_id: warehouse.categoryId ?? '',
      code: warehouse.code,
      name: warehouse.name,
      description: warehouse.description,
      warehouse_type: warehouse.type,
      operational_status: warehouse.status,
      physical_location: warehouse.location,
      manager_employee_id: warehouse.managerEmployeeId ?? '',
      area: String(warehouse.area || ''),
      height: String(warehouse.height || ''),
      length: String(warehouse.length || ''),
      width: String(warehouse.width || ''),
      shelves_total: String(warehouse.shelvesTotal || ''),
      capacity: String(warehouse.capacity || ''),
      shifts: [...warehouse.shifts],
      cameras: String(warehouse.cameras || ''),
      access_control: warehouse.accessControl || 'sin_control',
      has_alarm: warehouse.hasAlarm,
      fire_system: [...warehouse.fireSystem],
      last_security_audit: dateValue(warehouse.lastSecurityAudit),
      temperature_range: warehouse.temperatureRange,
      humidity_range: warehouse.humidityRange,
      cooling: warehouse.cooling || 'sin_climatizacion',
      has_ventilation: warehouse.hasVentilation,
      last_maintenance: dateValue(warehouse.lastMaintenance),
      next_maintenance: dateValue(warehouse.nextMaintenance),
      maintenance_notes: warehouse.maintenanceNotes,
      sanitary_permit: warehouse.sanitaryPermit ?? '',
      sanitary_permit_expiry: dateValue(warehouse.sanitaryPermitExpiry),
      last_inspection: dateValue(warehouse.lastInspection),
      certifications: [...warehouse.certifications],
      images: warehouse.images.map((image) => ({ ...image }))
    };
    originalImages = warehouse.images.map((image) => ({ ...image }));
  }
  async function loadManagers(branchId: string, preserve = false) {
    loadingManagers = true;
    try {
      managers = branchId
        ? (await api.employees.list({ size: 100, status: 'activo', branch_id: branchId })).items
        : [];
      if (
        !preserve &&
        f.manager_employee_id &&
        !managers.some((item) => item.id === f.manager_employee_id)
      )
        f.manager_employee_id = '';
    } finally {
      loadingManagers = false;
    }
  }
  async function load() {
    loading = true;
    error = null;
    try {
      if (!company.id) throw new Error('Seleccione una empresa.');
      [branches, categories] = await Promise.all([
        api.branches.list(),
        api.warehouseCategories.catalogue()
      ]);
      if (mode === 'edit') {
        if (!warehouseId) throw new Error('Almacén no válido.');
        const warehouse = await getWarehouse(warehouseId);
        fromWarehouse(warehouse);
        await Promise.all([
          loadManagers(f.branch_id, true),
          canViewLocations
            ? api.locations.list(warehouseId).then((data) => (locations = data))
            : Promise.resolve()
        ]);
      } else {
        f.branch_id = branches[0]?.id ?? '';
        f.warehouse_category_id = categories.find((item) => item.is_active)?.id ?? '';
        await loadManagers(f.branch_id, true);
      }
      initialSnapshot = JSON.stringify(f);
    } catch (err) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo cargar el editor.';
    } finally {
      loading = false;
    }
  }
  function validate() {
    const next: Record<string, string> = {};
    if (f.code.trim().length < 2) next.code = 'Ingrese un código válido.';
    if (f.name.trim().length < 2) next.name = 'Ingrese el nombre.';
    if (!f.branch_id) next.branch_id = 'Seleccione una sucursal.';
    if (!f.warehouse_category_id) next.warehouse_category_id = 'Seleccione una categoría.';
    if (f.capacity !== '' && Number(f.capacity) <= 0)
      next.capacity = 'La capacidad debe ser mayor que cero.';
    if (f.last_maintenance && f.next_maintenance && f.next_maintenance < f.last_maintenance)
      next.next_maintenance = 'No puede ser anterior al último mantenimiento.';
    if (f.sanitary_permit_expiry && !f.sanitary_permit.trim())
      next.sanitary_permit = 'Indique el permiso sanitario.';
    errors = next;
    if (Object.keys(next).length) {
      if (next.code || next.name) scrollToSection('general');
      else if (next.branch_id || next.warehouse_category_id) scrollToSection('organization');
      else if (next.capacity) scrollToSection('capacity');
      else if (next.next_maintenance) scrollToSection('maintenance');
      else scrollToSection('compliance');
      return false;
    }
    return true;
  }
  function payload() {
    return {
      branch_id: f.branch_id,
      warehouse_category_id: f.warehouse_category_id,
      code: f.code.trim(),
      name: f.name.trim(),
      description: f.description.trim() || null,
      warehouse_type: f.warehouse_type,
      operational_status: f.operational_status,
      physical_location: f.physical_location.trim() || null,
      manager_employee_id: f.manager_employee_id || null,
      area: num(f.area),
      height: num(f.height),
      length: num(f.length),
      width: num(f.width),
      shelves_total: num(f.shelves_total),
      capacity: num(f.capacity),
      shifts: f.shifts,
      cameras: num(f.cameras),
      access_control: f.access_control || null,
      has_alarm: f.has_alarm,
      fire_system: f.fire_system,
      last_security_audit: f.last_security_audit || null,
      temperature_range: f.temperature_range.trim() || null,
      humidity_range: f.humidity_range.trim() || null,
      cooling: f.cooling || null,
      has_ventilation: f.has_ventilation,
      last_maintenance: f.last_maintenance || null,
      next_maintenance: f.next_maintenance || null,
      maintenance_notes: f.maintenance_notes.trim() || null,
      sanitary_permit: f.sanitary_permit.trim() || null,
      sanitary_permit_expiry: f.sanitary_permit_expiry || null,
      last_inspection: f.last_inspection || null,
      certifications: f.certifications,
      images: f.images.filter((image) => image.url)
    };
  }
  async function save() {
    if (!canManage) {
      error = 'No tiene permisos para guardar almacenes.';
      return;
    }
    if (!validate()) return;
    saving = true;
    error = null;
    try {
      let saved;
      if (mode === 'edit' && warehouseId) {
        saved = await api.warehouses.update(warehouseId, payload());
        const retained = new Set(f.images.map((image) => image.public_id).filter(Boolean));
        await Promise.allSettled(
          originalImages
            .filter((image) => image.public_id && !retained.has(image.public_id))
            .map((image) => api.media.deleteImage(company.id!, image.public_id!))
        );
      } else saved = await api.warehouses.create(payload());
      initialSnapshot = JSON.stringify(f);
      await goto(`/warehouses/${saved.id}`);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo guardar el almacén.';
    } finally {
      saving = false;
    }
  }
  function requestLeave(target: string) {
    if (dirty) pendingTarget = target;
    else void goto(target);
  }
  beforeNavigate((navigation) => {
    const from = navigation.from?.url;
    const to = navigation.to?.url;
    if (
      from &&
      to &&
      from.pathname === to.pathname &&
      from.search === to.search &&
      from.hash !== to.hash
    )
      return;
    if (dirty && !saving && navigation.to?.url.pathname !== pendingTarget) {
      navigation.cancel();
      pendingTarget = navigation.to?.url.pathname ?? '/warehouses';
    }
  });
  onMount(() => {
    void load().then(async () => {
      await tick();
      const id = window.location.hash.slice(1);
      if (sections.some(([key]) => key === id)) scrollToSection(id, 'auto');
    });
  });
</script>

<svelte:head
  ><title>{mode === 'create' ? 'Nuevo almacén' : 'Editar almacén'} — ERP System</title></svelte:head
>
<div class="min-h-full bg-background px-6 pb-6 md:px-8 md:pb-8">
  <header
    bind:this={editorHeader}
    class="sticky top-0 z-30 mb-6 flex items-center gap-3 border-b border-border bg-background/95 pb-3 pt-6 backdrop-blur md:pt-8"
  >
    <button
      type="button"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver"
      onclick={() =>
        requestLeave(mode === 'edit' && warehouseId ? `/warehouses/${warehouseId}` : '/warehouses')}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
        ><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg
      >
    </button>
    <div class="min-w-0 flex-1">
      <h1 class="text-xl font-bold text-foreground">
        {mode === 'create' ? 'Nuevo almacén' : 'Editar almacén'}
      </h1>
      <p class="text-sm text-foreground-muted">
        {mode === 'create'
          ? 'Información completa del nuevo almacén.'
          : 'Actualiza la información completa del almacén.'}
      </p>
    </div>
    <div class="flex shrink-0 items-center gap-2">
      {#if dirty}<span
          class="hidden rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning sm:inline"
          >Cambios sin guardar</span
        >{/if}
      <Button
        variant="secondary"
        size="sm"
        onclick={() =>
          requestLeave(
            mode === 'edit' && warehouseId ? `/warehouses/${warehouseId}` : '/warehouses'
          )}><span aria-hidden="true">×</span> Cancelar</Button
      >
      <Button size="sm" onclick={save} disabled={saving || loading || !canManage}
        ><span aria-hidden="true">{saving ? '◌' : '▣'}</span>
        {saving ? 'Guardando…' : mode === 'create' ? 'Guardar almacén' : 'Guardar cambios'}</Button
      >
    </div>
  </header>
  {#if pendingTarget}<div
      class="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm"
    >
      <span class="flex-1">Hay cambios sin guardar. ¿Desea descartarlos?</span><Button
        size="sm"
        variant="secondary"
        onclick={() => (pendingTarget = null)}>Continuar editando</Button
      ><Button
        size="sm"
        onclick={() => {
          const target = pendingTarget!;
          initialSnapshot = JSON.stringify(f);
          pendingTarget = null;
          void goto(target);
        }}>Descartar cambios</Button
      >
    </div>{/if}
  {#if error}<div
      class="mb-5 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>{/if}
  {#if loading}<div class="grid gap-4 lg:grid-cols-[220px_1fr]">
      <div class="h-72 rounded-xl skeleton"></div>
      <div class="h-[560px] rounded-xl skeleton"></div>
    </div>{:else}
    <div class="mx-auto grid max-w-[1440px] gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <EditorSectionNav {sections} {activeSection} onselect={scrollToSection} />
      <main class="min-w-0 space-y-6">
        <Card id="general" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Información general</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Identidad, clasificación y estado operativo.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="warehouse-code"
              label="Código"
              bind:value={f.code}
              error={errors.code}
              required
            /><FormField
              id="warehouse-name"
              label="Nombre"
              bind:value={f.name}
              error={errors.name}
              required
            />
            <SmartSelect
              id="warehouse-type"
              label="Tipo"
              bind:value={f.warehouse_type}
              options={enumOptions([
                ['general', 'General'],
                ['cold_storage', 'Refrigerado'],
                ['hazmat', 'Materiales peligrosos'],
                ['transit', 'Tránsito / cross-dock'],
                ['bonded', 'Aduanal'],
                ['automated', 'Automatizado']
              ])}
            />
            <SmartSelect
              id="warehouse-status"
              label="Estado operativo"
              bind:value={f.operational_status}
              options={enumOptions([
                ['active', 'Activo'],
                ['full', 'Lleno'],
                ['maintenance', 'Mantenimiento'],
                ['inactive', 'Inactivo']
              ])}
            />
            <div class="sm:col-span-2">
              <label for="warehouse-description" class="mb-1 block text-sm font-medium"
                >Descripción</label
              ><textarea
                id="warehouse-description"
                bind:value={f.description}
                rows="4"
                maxlength="4000"
                class="field"
              ></textarea>
            </div>
          </div></Card
        >

        <Card id="organization" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Organización</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Sucursal propietaria, categoría y referencia física.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <SmartSelect
              id="warehouse-branch"
              label="Sucursal"
              bind:value={f.branch_id}
              options={branchOptions}
              error={errors.branch_id}
              required
              onselect={(value) => void loadManagers(value)}
            />
            <SmartSelect
              id="warehouse-category"
              label="Categoría"
              bind:value={f.warehouse_category_id}
              options={categoryOptions}
              error={errors.warehouse_category_id}
              required
            />
            <div class="sm:col-span-2">
              <FormField
                id="warehouse-location"
                label="Ubicación física / referencia"
                bind:value={f.physical_location}
                placeholder="Ej. Edificio B, nivel 1"
              />
            </div>
            {#if mode === 'edit' && locations.length > 0}<p
                class="sm:col-span-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning"
              >
                Este almacén tiene ubicaciones activas. Para cambiarlo de sucursal primero debe
                desactivarlas.
              </p>{/if}
          </div></Card
        >

        <Card id="operation" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Responsable y operación</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            El responsable debe ser un empleado activo asignado a la sucursal.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <SmartSelect
              id="warehouse-manager"
              label="Responsable"
              bind:value={f.manager_employee_id}
              options={managerOptions}
              placeholder={loadingManagers ? 'Cargando empleados…' : 'Buscar empleado…'}
              disabled={loadingManagers || !f.branch_id}
            />
            <div>
              <span class="mb-2 block text-sm font-medium">Turnos habilitados</span>
              <div
                class="flex min-h-[42px] flex-wrap items-center gap-4 rounded-lg border border-border bg-surface px-3"
              >
                {#each SHIFT_OPTIONS as shift}<label class="flex items-center gap-2 text-sm"
                    ><input
                      type="checkbox"
                      checked={f.shifts.includes(shift[0])}
                      onchange={(event) => {
                        const checked = event.currentTarget.checked;
                        f.shifts = checked
                          ? [...f.shifts, shift[0]]
                          : f.shifts.filter((item) => item !== shift[0]);
                      }}
                    />{shift[1]}</label
                  >{/each}
              </div>
            </div>
          </div></Card
        >

        <Card id="capacity" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Dimensiones y capacidad</h2>
          <p class="mb-5 text-sm text-foreground-muted">Parámetros físicos y capacidad nominal.</p>
          <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <FormField
              id="warehouse-area"
              label="Área (m²)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.area}
            /><FormField
              id="warehouse-height"
              label="Altura (m)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.height}
            /><FormField
              id="warehouse-length"
              label="Largo (m)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.length}
            /><FormField
              id="warehouse-width"
              label="Ancho (m)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.width}
            /><FormField
              id="warehouse-shelves"
              label="Estanterías"
              type="number"
              min="0"
              bind:value={f.shelves_total}
            /><FormField
              id="warehouse-capacity"
              label="Capacidad (unidades)"
              type="number"
              min="1"
              bind:value={f.capacity}
              error={errors.capacity}
            />
          </div></Card
        >

        <Card id="security" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Seguridad</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Controles, vigilancia y protección contra incendios.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="warehouse-cameras"
              label="Cámaras CCTV"
              type="number"
              min="0"
              bind:value={f.cameras}
            /><SmartSelect
              id="warehouse-access"
              label="Control de acceso"
              bind:value={f.access_control}
              options={enumOptions([
                ['biometrico', 'Biométrico'],
                ['tarjetas', 'Tarjetas'],
                ['teclado', 'Teclado'],
                ['doble_llave', 'Doble llave'],
                ['sin_control', 'Sin control']
              ])}
            />
            <FormField
              id="warehouse-security-audit"
              label="Última auditoría de seguridad"
              type="date"
              bind:value={f.last_security_audit}
            />
            <div class="flex items-end pb-2">
              <label class="flex items-center gap-2 text-sm"
                ><input type="checkbox" bind:checked={f.has_alarm} /> Sistema de alarma activo</label
              >
            </div>
            <div class="sm:col-span-2">
              <ChipInput
                id="warehouse-fire-system"
                label="Sistemas contra incendios"
                bind:values={f.fire_system}
                suggestions={[
                  'Extintores',
                  'Rociadores',
                  'Detectores de humo',
                  'Gabinetes contra incendio'
                ]}
              />
            </div>
          </div></Card
        >

        <Card id="environment" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Condiciones ambientales</h2>
          <p class="mb-5 text-sm text-foreground-muted">Rangos de conservación y climatización.</p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="warehouse-temperature"
              label="Rango de temperatura"
              bind:value={f.temperature_range}
              placeholder="Ej. 18–24 °C"
            /><FormField
              id="warehouse-humidity"
              label="Rango de humedad"
              bind:value={f.humidity_range}
              placeholder="Ej. 40–60 %"
            />
            <SmartSelect
              id="warehouse-cooling"
              label="Climatización"
              bind:value={f.cooling}
              options={enumOptions([
                ['industrial_ac', 'Aire acondicionado industrial'],
                ['refrigeracion', 'Refrigeración'],
                ['ventilacion_natural', 'Ventilación natural'],
                ['mixto', 'Sistema mixto'],
                ['sin_climatizacion', 'Sin climatización']
              ])}
            />
            <div class="flex items-end pb-2">
              <label class="flex items-center gap-2 text-sm"
                ><input type="checkbox" bind:checked={f.has_ventilation} /> Cuenta con ventilación</label
              >
            </div>
          </div></Card
        >

        <Card id="maintenance" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Mantenimiento</h2>
          <p class="mb-5 text-sm text-foreground-muted">Historial y planificación preventiva.</p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="warehouse-last-maintenance"
              label="Último mantenimiento"
              type="date"
              bind:value={f.last_maintenance}
            /><FormField
              id="warehouse-next-maintenance"
              label="Próximo mantenimiento"
              type="date"
              bind:value={f.next_maintenance}
              error={errors.next_maintenance}
            />
            <div class="sm:col-span-2">
              <label for="warehouse-maintenance-notes" class="mb-1 block text-sm font-medium"
                >Notas de mantenimiento</label
              ><textarea
                id="warehouse-maintenance-notes"
                bind:value={f.maintenance_notes}
                rows="4"
                maxlength="4000"
                class="field"
              ></textarea>
            </div>
          </div></Card
        >

        <Card id="compliance" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Cumplimiento</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Permisos, inspecciones y certificaciones.
          </p>
          <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <FormField
              id="warehouse-sanitary-permit"
              label="Permiso sanitario"
              bind:value={f.sanitary_permit}
              error={errors.sanitary_permit}
            /><FormField
              id="warehouse-permit-expiry"
              label="Vencimiento del permiso"
              type="date"
              bind:value={f.sanitary_permit_expiry}
            /><FormField
              id="warehouse-inspection"
              label="Última inspección"
              type="date"
              bind:value={f.last_inspection}
            />
            <div class="sm:col-span-2 xl:col-span-3">
              <ChipInput
                id="warehouse-certifications"
                label="Certificaciones"
                bind:values={f.certifications}
                suggestions={['ISO 9001', 'ISO 14001', 'BPM', 'HACCP']}
              />
            </div>
          </div></Card
        >

        <Card id="gallery" class="scroll-mt-24 p-6"
          ><WarehouseImagesEditor bind:images={f.images} companyId={company.id ?? ''} /></Card
        >

        <Card id="locations" class="scroll-mt-24 p-6"
          ><div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 class="mb-1 text-base font-semibold">Ubicaciones físicas</h2>
              <p class="text-sm text-foreground-muted">
                Pasillos, racks, niveles y posiciones del almacén.
              </p>
            </div>
            {#if mode === 'edit' && warehouseId && canViewLocations}<Button
                variant="secondary"
                size="sm"
                onclick={() => requestLeave(`/warehouses/${warehouseId}/locations`)}
                >Administrar ubicaciones</Button
              >{/if}
          </div>
          <div class="mt-5 rounded-xl border border-border bg-surface-muted/30 p-4 text-sm">
            <p class="font-medium">
              {mode === 'create'
                ? 'Disponible después de guardar'
                : `${locations.length} ubicación(es) registrada(s)`}
            </p>
            <p class="mt-1 text-xs text-foreground-muted">
              {mode === 'create'
                ? 'Primero cree el almacén y luego configure su estructura interna.'
                : canViewLocations
                  ? 'La estructura se administra en su submódulo dedicado.'
                  : 'No tiene permisos para consultar las ubicaciones.'}
            </p>
          </div></Card
        >

        <Card id="review" class="scroll-mt-24 p-6"
          ><h2 class="mb-4 text-base font-semibold">Revisión</h2>
          <dl class="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-foreground-muted">Almacén</dt>
              <dd class="font-semibold">{f.code || 'Sin código'} · {f.name || 'Sin nombre'}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Sucursal</dt>
              <dd class="font-semibold">
                {branches.find((item) => item.id === f.branch_id)?.name ?? 'Sin seleccionar'}
              </dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Responsable</dt>
              <dd class="font-semibold">
                {managerOptions.find((item) => item.value === f.manager_employee_id)?.label ??
                  'Sin responsable'}
              </dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Galería</dt>
              <dd class="font-semibold">
                {f.images.filter((image) => image.url).length} imagen(es)
              </dd>
            </div>
          </dl></Card
        >
      </main>
    </div>
  {/if}
</div>

<style>
  .field {
    width: 100%;
    border-radius: 0.5rem;
    border: 1px solid rgb(var(--border));
    background: rgb(var(--surface));
    padding: 0.625rem 0.75rem;
    font-size: 0.875rem;
    color: rgb(var(--foreground));
    outline: none;
  }
  .field:focus {
    border-color: rgb(var(--primary));
    box-shadow: 0 0 0 1px rgb(var(--primary));
  }
</style>
