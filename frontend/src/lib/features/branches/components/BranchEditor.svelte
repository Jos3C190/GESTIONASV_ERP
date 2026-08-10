<script lang="ts">
  import { beforeNavigate, goto } from '$app/navigation';
  import { onMount, tick } from 'svelte';
  import { api, HttpError, type EmployeeOut } from '$lib/api/client';
  import { getBranch } from '$lib/services/branches';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import SmartSelect from '$lib/components/ui/SmartSelect.svelte';
  import ChipInput from '$lib/components/ui/ChipInput.svelte';
  import EditorSectionNav from '$lib/components/editor/EditorSectionNav.svelte';
  import BranchImagesEditor from './BranchImagesEditor.svelte';
  import BranchLocationPicker from './BranchLocationPicker.svelte';
  import type { Branch, BranchImage, ScheduleDay } from '../types';

  interface Props {
    mode: 'create' | 'edit';
    branchId?: string;
  }
  let { mode, branchId }: Props = $props();
  const DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
  const emptySchedule = (): ScheduleDay[] => DAYS.map((day) => ({ day, open: null, close: null }));
  const empty = () => ({
    code: '',
    name: '',
    operational_status: 'active',
    opened_at: '',
    description: '',
    department_id: '',
    municipality_id: '',
    district_id: '',
    address: '',
    zone: '',
    latitude: '13.6929',
    longitude: '-89.2182',
    phone: '',
    email: '',
    website: '',
    manager_employee_id: '',
    schedule: emptySchedule(),
    area: '',
    area_built: '',
    area_unbuilt: '',
    floors: '',
    parking: '',
    people_capacity: '',
    offices: '',
    meeting_rooms: '',
    bathrooms: '',
    accesses: '',
    emergency_exits: '',
    property_type: 'alquilado',
    construction_type: 'concreto',
    construction_year: '',
    building_condition: 'bueno',
    services: [] as string[],
    facilities: [] as string[],
    accessibility: [] as string[],
    internet_provider: '',
    internet_type: 'fibra',
    water_source: 'red_publica',
    ac_system: 'mini_split',
    lighting: 'led',
    electrical_capacity_kva: '',
    cctv_cameras: '',
    access_control: 'sin_control',
    has_alarm: false,
    fire_system: [] as string[],
    has_backup_generator: false,
    has_ups: false,
    exterior_material: 'mixta',
    floor_material: 'porcelanato',
    roof_capacity_kg_m2: '',
    cadastral_code: '',
    permit_expiry: '',
    lease_expiry: '',
    landlord: '',
    appraised_value: '',
    monthly_maintenance: '',
    last_renovation: '',
    last_inspection: '',
    cleaning_provider: '',
    images: [] as BranchImage[]
  });
  let f = $state(empty());
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let errors = $state<Record<string, string>>({});
  let initialSnapshot = $state('');
  let pendingTarget = $state<string | null>(null);
  let departments = $state<{ id: string; name: string }[]>([]);
  let municipalities = $state<{ id: string; name: string }[]>([]);
  let districts = $state<{ id: string; name: string }[]>([]);
  let employees = $state<EmployeeOut[]>([]);
  let originalImages = $state<BranchImage[]>([]);
  let editorHeader: HTMLElement;
  let activeSection = $state('general');
  let canManage = $derived(
    permissions.hasPermission(mode === 'create' ? 'branches.create' : 'branches.update')
  );
  let dirty = $derived(!loading && initialSnapshot !== JSON.stringify(f));
  const sections = [
    ['general', 'Información general'],
    ['location', 'Ubicación'],
    ['schedule', 'Horarios'],
    ['infrastructure', 'Infraestructura'],
    ['services', 'Servicios'],
    ['security', 'Seguridad'],
    ['property', 'Propiedad'],
    ['gallery', 'Galería'],
    ['review', 'Revisión']
  ] as const;
  const options = (items: { id: string; name: string }[]) =>
    items.map((item) => ({ value: item.id, label: item.name }));
  const enumOptions = (items: [string, string][]) =>
    items.map(([value, label]) => ({ value, label }));
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
    const headerOffset = (editorHeader?.offsetHeight ?? 0) + 16;
    const requestedTop =
      scrollContainer.scrollTop + targetRect.top - containerRect.top - headerOffset;
    const maximumTop = Math.max(scrollContainer.scrollHeight - scrollContainer.clientHeight, 0);

    activeSection = id;
    scrollContainer.scrollTo({
      top: Math.min(Math.max(requestedTop, 0), maximumTop),
      behavior
    });
    history.replaceState(
      history.state,
      '',
      `${window.location.pathname}${window.location.search}#${id}`
    );
  }
  function fromBranch(branch: Branch) {
    f = {
      ...empty(),
      code: branch.code,
      name: branch.name,
      operational_status: branch.status,
      opened_at: dateValue(branch.openedAt),
      description: branch.description,
      department_id: branch.departmentId ?? '',
      municipality_id: branch.municipalityId ?? '',
      district_id: branch.districtId ?? '',
      address: branch.address,
      zone: branch.zone,
      latitude: String(branch.lat),
      longitude: String(branch.lng),
      phone: branch.phone,
      email: branch.email,
      website: branch.website,
      manager_employee_id: branch.managerEmployeeId ?? '',
      schedule: branch.scheduleDetail.length
        ? branch.scheduleDetail.map((day) => ({ ...day }))
        : emptySchedule(),
      area: String(branch.area || ''),
      area_built: String(branch.areaBuilt || ''),
      area_unbuilt: String(branch.areaUnbuilt || ''),
      floors: String(branch.floors || ''),
      parking: String(branch.parking || ''),
      people_capacity: String(branch.capacity || ''),
      offices: String(branch.offices || ''),
      meeting_rooms: String(branch.meetingRooms || ''),
      bathrooms: String(branch.bathrooms || ''),
      accesses: String(branch.accesses || ''),
      emergency_exits: String(branch.emergencyExits || ''),
      property_type: branch.propertyType,
      construction_type: branch.constructionType,
      construction_year: String(branch.constructionYear || ''),
      building_condition: branch.condition,
      services: [...branch.services],
      facilities: [...branch.facilities],
      accessibility: [...branch.accessibility],
      internet_provider: branch.internetProvider,
      internet_type: branch.internetType,
      water_source: branch.waterSource,
      ac_system: branch.acSystem,
      lighting: branch.lighting,
      electrical_capacity_kva: String(branch.electricalCapacityKVA || ''),
      cctv_cameras: String(branch.cctvCameras || ''),
      access_control: branch.accessControl,
      has_alarm: branch.hasAlarm,
      fire_system: [...branch.fireSystem],
      has_backup_generator: branch.hasBackupGenerator,
      has_ups: branch.hasUPS,
      exterior_material: branch.exteriorMaterial,
      floor_material: branch.floorMaterial,
      roof_capacity_kg_m2: String(branch.roofCapacityKgM2 || ''),
      cadastral_code: branch.cadastralCode,
      permit_expiry: dateValue(branch.permitExpiry),
      lease_expiry: dateValue(branch.leaseExpiry),
      landlord: branch.landlord ?? '',
      appraised_value: String(branch.appraisedValue || ''),
      monthly_maintenance: String(branch.monthlyMaintenance || ''),
      last_renovation: dateValue(branch.lastRenovation),
      last_inspection: dateValue(branch.lastInspection),
      cleaning_provider: branch.cleaningProvider,
      images: branch.images.map((image) => ({ ...image }))
    };
    originalImages = branch.images.map((image) => ({ ...image }));
  }
  async function loadMunicipalities(value = f.department_id) {
    f.municipality_id = '';
    f.district_id = '';
    districts = [];
    municipalities = value ? await api.geography.municipalities(value) : [];
  }
  async function loadDistricts(value = f.municipality_id) {
    f.district_id = '';
    districts = value ? await api.geography.districts(value) : [];
  }
  async function load() {
    loading = true;
    error = null;
    try {
      if (!company.id) throw new Error('Seleccione una empresa.');
      const [deps, employeePage] = await Promise.all([
        api.geography.departments(),
        api.employees.list({ size: 100, status: 'activo' })
      ]);
      departments = deps;
      employees = employeePage.items;
      if (mode === 'edit') {
        if (!branchId) throw new Error('Sucursal no válida.');
        const branch = await getBranch(branchId);
        fromBranch(branch);
        municipalities = await api.geography.municipalities(f.department_id);
        districts = await api.geography.districts(f.municipality_id);
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
    if (!f.department_id) next.department_id = 'Seleccione un departamento.';
    if (!f.municipality_id) next.municipality_id = 'Seleccione un municipio.';
    if (!f.district_id) next.district_id = 'Seleccione un distrito.';
    if (f.address.trim().length < 3) next.address = 'Ingrese la dirección.';
    if (Number(f.area_built || 0) > Number(f.area || 0))
      next.area_built = 'No puede superar el área total.';
    errors = next;
    if (Object.keys(next).length) {
      scrollToSection(next.code || next.name ? 'general' : 'location');
      return false;
    }
    return true;
  }
  function payload() {
    return {
      ...f,
      company_id: company.id,
      code: f.code.trim(),
      name: f.name.trim(),
      description: f.description || null,
      opened_at: f.opened_at || null,
      manager_employee_id: f.manager_employee_id || null,
      phone: f.phone || null,
      email: f.email || null,
      website: f.website || null,
      zone: f.zone || null,
      latitude: Number(f.latitude),
      longitude: Number(f.longitude),
      area: num(f.area),
      area_built: num(f.area_built),
      area_unbuilt: num(f.area_unbuilt),
      floors: num(f.floors),
      parking: num(f.parking),
      people_capacity: num(f.people_capacity),
      offices: num(f.offices),
      meeting_rooms: num(f.meeting_rooms),
      bathrooms: num(f.bathrooms),
      accesses: num(f.accesses),
      emergency_exits: num(f.emergency_exits),
      construction_year: num(f.construction_year),
      electrical_capacity_kva: num(f.electrical_capacity_kva),
      cctv_cameras: num(f.cctv_cameras),
      roof_capacity_kg_m2: num(f.roof_capacity_kg_m2),
      appraised_value: num(f.appraised_value),
      monthly_maintenance: num(f.monthly_maintenance),
      permit_expiry: f.permit_expiry || null,
      lease_expiry: f.lease_expiry || null,
      last_renovation: f.last_renovation || null,
      last_inspection: f.last_inspection || null,
      landlord: f.landlord || null,
      internet_provider: f.internet_provider || null,
      cleaning_provider: f.cleaning_provider || null,
      schedule: f.schedule.map((day) => ({
        day: day.day,
        open: day.open || null,
        close: day.close || null
      })),
      images: f.images.filter((image) => image.url)
    };
  }
  async function save() {
    if (!canManage) {
      error = 'No tiene permisos para guardar sucursales.';
      return;
    }
    if (!validate()) return;
    saving = true;
    error = null;
    try {
      let saved;
      if (mode === 'edit' && branchId) {
        saved = await api.branches.update(branchId, payload());
        const retained = new Set(f.images.map((image) => image.public_id).filter(Boolean));
        await Promise.allSettled(
          originalImages
            .filter((image) => image.public_id && !retained.has(image.public_id))
            .map((image) => api.media.deleteImage(company.id!, image.public_id!))
        );
      } else saved = await api.branches.create(payload());
      initialSnapshot = JSON.stringify(f);
      await goto(`/branches/${saved.id}`);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo guardar la sucursal.';
    } finally {
      saving = false;
    }
  }
  function requestLeave(target: string) {
    if (dirty) {
      pendingTarget = target;
      return;
    }
    void goto(target);
  }
  beforeNavigate((navigation) => {
    const from = navigation.from?.url;
    const to = navigation.to?.url;
    const isHashOnlyNavigation =
      from &&
      to &&
      from.pathname === to.pathname &&
      from.search === to.search &&
      from.hash !== to.hash;
    if (isHashOnlyNavigation) return;

    if (dirty && !saving && navigation.to?.url.pathname !== pendingTarget) {
      navigation.cancel();
      pendingTarget = navigation.to?.url.pathname ?? '/branches';
    }
  });
  onMount(() => {
    void load().then(async () => {
      await tick();
      const initialSection = window.location.hash.slice(1);
      if (sections.some(([id]) => id === initialSection)) {
        scrollToSection(initialSection, 'auto');
      }
    });
  });
</script>

<svelte:head
  ><title>{mode === 'create' ? 'Nueva sucursal' : 'Editar sucursal'} — GestionaSV</title
  ></svelte:head
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
        requestLeave(mode === 'edit' && branchId ? `/branches/${branchId}` : '/branches')}
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
        {mode === 'create' ? 'Nueva sucursal' : 'Editar sucursal'}
      </h1>
      <p class="text-sm text-foreground-muted">
        {mode === 'create'
          ? 'Información completa de la nueva sucursal.'
          : 'Actualiza la información completa de la sucursal.'}
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
          requestLeave(mode === 'edit' && branchId ? `/branches/${branchId}` : '/branches')}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
          ><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg
        >
        Cancelar
      </Button>
      <Button size="sm" onclick={save} disabled={saving || loading || !canManage}>
        {#if saving}
          <svg class="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
            ></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
            ></path>
          </svg>
        {:else}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
            ><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" /><polyline
              points="17 21 17 13 7 13 7 21"
            /><polyline points="7 3 7 8 15 8" /></svg
          >
        {/if}
        {saving ? 'Guardando…' : mode === 'create' ? 'Guardar sucursal' : 'Guardar cambios'}
      </Button>
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
            Identidad, responsable y contacto operativo.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="branch-code"
              label="Código"
              bind:value={f.code}
              error={errors.code}
              required
            /><FormField
              id="branch-name"
              label="Nombre"
              bind:value={f.name}
              error={errors.name}
              required
            /><SmartSelect
              id="branch-status"
              label="Estado operativo"
              bind:value={f.operational_status}
              options={enumOptions([
                ['active', 'Activa'],
                ['maintenance', 'Mantenimiento'],
                ['inactive', 'Inactiva']
              ])}
            /><FormField
              id="branch-opened"
              label="Fecha de apertura"
              type="date"
              bind:value={f.opened_at}
            /><SmartSelect
              id="branch-manager"
              label="Responsable"
              bind:value={f.manager_employee_id}
              options={[
                { value: '', label: 'Sin responsable' },
                ...employees.map((employee) => ({
                  value: employee.id,
                  label: `${employee.first_name} ${employee.last_name}`,
                  description: `${employee.employee_code} · ${employee.position ?? 'Sin cargo'}`
                }))
              ]}
            /><FormField id="branch-zone" label="Zona o referencia" bind:value={f.zone} /><FormField
              id="branch-phone"
              label="Teléfono"
              bind:value={f.phone}
            /><FormField id="branch-email" label="Correo" type="email" bind:value={f.email} />
            <div class="sm:col-span-2">
              <FormField id="branch-website" label="Sitio web" type="url" bind:value={f.website} />
            </div>
            <div class="sm:col-span-2">
              <label for="branch-description" class="mb-1 block text-sm font-medium"
                >Descripción</label
              ><textarea
                id="branch-description"
                bind:value={f.description}
                rows="4"
                maxlength="4000"
                class="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              ></textarea>
            </div>
          </div></Card
        >
        <Card id="location" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Dirección y ubicación</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Ubicación administrativa y coordenadas exactas.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <SmartSelect
              id="branch-department"
              label="Departamento"
              bind:value={f.department_id}
              error={errors.department_id}
              required
              options={options(departments)}
              onselect={(value) => {
                void loadMunicipalities(value);
              }}
            /><SmartSelect
              id="branch-municipality"
              label="Municipio"
              bind:value={f.municipality_id}
              error={errors.municipality_id}
              required
              options={options(municipalities)}
              disabled={!f.department_id}
              onselect={(value) => {
                void loadDistricts(value);
              }}
            /><SmartSelect
              id="branch-district"
              label="Distrito"
              bind:value={f.district_id}
              error={errors.district_id}
              required
              options={options(districts)}
              disabled={!f.municipality_id}
            />
            <div></div>
            <div class="sm:col-span-2">
              <FormField
                id="branch-address"
                label="Dirección completa"
                bind:value={f.address}
                error={errors.address}
                required
              />
            </div>
            <FormField
              id="branch-lat"
              label="Latitud"
              type="number"
              min="-90"
              max="90"
              step="0.000001"
              bind:value={f.latitude}
              required
            /><FormField
              id="branch-lng"
              label="Longitud"
              type="number"
              min="-180"
              max="180"
              step="0.000001"
              bind:value={f.longitude}
              required
            />
          </div>
          <div class="mt-4">
            <BranchLocationPicker
              latitude={f.latitude}
              longitude={f.longitude}
              onpositionchange={(position) => {
                f.latitude = position.latitude.toFixed(6);
                f.longitude = position.longitude.toFixed(6);
              }}
            />
          </div></Card
        >
        <Card id="schedule" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold">Horarios de operación</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Deje ambas horas vacías para marcar el día como cerrado.
          </p>
          <div class="space-y-2">
            {#each f.schedule as day, index (day.day)}<div
                class="grid items-center gap-3 rounded-lg border border-border p-3 sm:grid-cols-[1fr_150px_150px]"
              >
                <span class="text-sm font-medium">{day.day}</span><input
                  aria-label={`Apertura ${day.day}`}
                  type="time"
                  value={day.open ?? ''}
                  onchange={(event) => {
                    f.schedule[index]!.open =
                      (event.currentTarget as HTMLInputElement).value || null;
                  }}
                  class="rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                /><input
                  aria-label={`Cierre ${day.day}`}
                  type="time"
                  value={day.close ?? ''}
                  onchange={(event) => {
                    f.schedule[index]!.close =
                      (event.currentTarget as HTMLInputElement).value || null;
                  }}
                  class="rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                />
              </div>{/each}
          </div></Card
        >
        <Card id="infrastructure" class="scroll-mt-24 p-6"
          ><h2 class="mb-5 text-base font-semibold">Infraestructura y capacidad</h2>
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <FormField
              id="area"
              label="Área total (m²)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.area}
            /><FormField
              id="area-built"
              label="Área construida (m²)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.area_built}
              error={errors.area_built}
            /><FormField
              id="area-free"
              label="Área libre (m²)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.area_unbuilt}
            /><FormField
              id="floors"
              label="Pisos"
              type="number"
              min="0"
              bind:value={f.floors}
            /><FormField
              id="parking"
              label="Estacionamientos"
              type="number"
              min="0"
              bind:value={f.parking}
            /><FormField
              id="capacity"
              label="Capacidad de personas"
              type="number"
              min="0"
              bind:value={f.people_capacity}
            /><FormField
              id="offices"
              label="Oficinas"
              type="number"
              min="0"
              bind:value={f.offices}
            /><FormField
              id="meeting"
              label="Salas de reuniones"
              type="number"
              min="0"
              bind:value={f.meeting_rooms}
            /><FormField
              id="bathrooms"
              label="Baños"
              type="number"
              min="0"
              bind:value={f.bathrooms}
            /><FormField
              id="accesses"
              label="Accesos"
              type="number"
              min="0"
              bind:value={f.accesses}
            /><FormField
              id="emergency"
              label="Salidas de emergencia"
              type="number"
              min="0"
              bind:value={f.emergency_exits}
            /><FormField
              id="electrical"
              label="Capacidad eléctrica (kVA)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.electrical_capacity_kva}
            /><SmartSelect
              id="construction"
              label="Tipo de construcción"
              bind:value={f.construction_type}
              options={enumOptions([
                ['concreto', 'Concreto'],
                ['metalico', 'Metálico'],
                ['mixto', 'Mixto'],
                ['prefabricado', 'Prefabricado']
              ])}
            /><FormField
              id="construction-year"
              label="Año de construcción"
              type="number"
              min="1800"
              max="2200"
              bind:value={f.construction_year}
            /><SmartSelect
              id="condition"
              label="Estado del inmueble"
              bind:value={f.building_condition}
              options={enumOptions([
                ['excelente', 'Excelente'],
                ['bueno', 'Bueno'],
                ['regular', 'Regular'],
                ['malo', 'Malo']
              ])}
            />
          </div></Card
        >
        <Card id="services" class="scroll-mt-24 p-6"
          ><h2 class="mb-5 text-base font-semibold">Servicios y accesibilidad</h2>
          <div class="grid gap-4 sm:grid-cols-2">
            <ChipInput
              id="services-list"
              label="Servicios"
              bind:values={f.services}
              suggestions={['Punto de venta', 'Bodega', 'Servicio al cliente', 'Entregas']}
            /><ChipInput
              id="facilities-list"
              label="Facilidades"
              bind:values={f.facilities}
              suggestions={['Estacionamiento', 'WiFi', 'Ascensor', 'Cafetería']}
            />
            <div class="sm:col-span-2">
              <ChipInput
                id="accessibility-list"
                label="Accesibilidad"
                bind:values={f.accessibility}
                suggestions={[
                  'Rampas',
                  'Ascensor',
                  'Baño accesible',
                  'Estacionamiento preferencial'
                ]}
              />
            </div>
            <FormField
              id="internet-provider"
              label="Proveedor de internet"
              bind:value={f.internet_provider}
            /><SmartSelect
              id="internet-type"
              label="Tipo de internet"
              bind:value={f.internet_type}
              options={enumOptions([
                ['fibra', 'Fibra'],
                ['adsl', 'ADSL'],
                ['satelital', 'Satelital'],
                ['4g', '4G/5G']
              ])}
            /><SmartSelect
              id="water"
              label="Fuente de agua"
              bind:value={f.water_source}
              options={enumOptions([
                ['red_publica', 'Red pública'],
                ['pozo', 'Pozo'],
                ['cisterna', 'Cisterna'],
                ['mixta', 'Mixta']
              ])}
            /><SmartSelect
              id="ac"
              label="Climatización"
              bind:value={f.ac_system}
              options={enumOptions([
                ['central', 'Central'],
                ['individual', 'Individual'],
                ['mini_split', 'Mini split'],
                ['mixto', 'Mixto'],
                ['sin_ac', 'Sin A/C']
              ])}
            /><SmartSelect
              id="lighting"
              label="Iluminación"
              bind:value={f.lighting}
              options={enumOptions([
                ['led', 'LED'],
                ['fluorescente', 'Fluorescente'],
                ['mixta', 'Mixta']
              ])}
            /><FormField
              id="cleaning"
              label="Proveedor de limpieza"
              bind:value={f.cleaning_provider}
            />
          </div></Card
        >
        <Card id="security" class="scroll-mt-24 p-6"
          ><h2 class="mb-5 text-base font-semibold">Seguridad y emergencias</h2>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="cctv"
              label="Cámaras CCTV"
              type="number"
              min="0"
              bind:value={f.cctv_cameras}
            /><SmartSelect
              id="access-control"
              label="Control de acceso"
              bind:value={f.access_control}
              options={enumOptions([
                ['biometrico', 'Biométrico'],
                ['tarjetas', 'Tarjetas'],
                ['teclado', 'Teclado'],
                ['sin_control', 'Sin control']
              ])}
            />
            <div class="sm:col-span-2">
              <ChipInput
                id="fire-system"
                label="Sistemas contra incendios"
                bind:values={f.fire_system}
                suggestions={[
                  'Extintores ABC',
                  'Detectores de humo',
                  'Rociadores',
                  'Alarma central'
                ]}
              />
            </div>
            <FormField
              id="inspection"
              label="Última inspección"
              type="date"
              bind:value={f.last_inspection}
            /><FormField
              id="roof"
              label="Capacidad de techo (kg/m²)"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.roof_capacity_kg_m2}
            /><label class="flex items-center gap-2 text-sm"
              ><input type="checkbox" bind:checked={f.has_alarm} /> Sistema de alarma</label
            ><label class="flex items-center gap-2 text-sm"
              ><input type="checkbox" bind:checked={f.has_backup_generator} /> Generador eléctrico</label
            ><label class="flex items-center gap-2 text-sm"
              ><input type="checkbox" bind:checked={f.has_ups} /> UPS</label
            >
          </div></Card
        >
        <Card id="property" class="scroll-mt-24 p-6"
          ><h2 class="mb-5 text-base font-semibold">Propiedad y cumplimiento</h2>
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <SmartSelect
              id="property-type"
              label="Tipo de propiedad"
              bind:value={f.property_type}
              options={enumOptions([
                ['propio', 'Propio'],
                ['alquilado', 'Alquilado'],
                ['arrendado', 'Arrendado'],
                ['cedido', 'Cedido']
              ])}
            /><FormField
              id="cadastral"
              label="Código catastral"
              bind:value={f.cadastral_code}
            /><FormField id="landlord" label="Arrendador" bind:value={f.landlord} /><FormField
              id="permit"
              label="Vencimiento de permisos"
              type="date"
              bind:value={f.permit_expiry}
            /><FormField
              id="lease"
              label="Vencimiento de arrendamiento"
              type="date"
              bind:value={f.lease_expiry}
            /><FormField
              id="renovation"
              label="Última renovación"
              type="date"
              bind:value={f.last_renovation}
            /><FormField
              id="appraised"
              label="Valor de avalúo"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.appraised_value}
            /><FormField
              id="maintenance"
              label="Mantenimiento mensual"
              type="number"
              min="0"
              step="0.01"
              bind:value={f.monthly_maintenance}
            /><SmartSelect
              id="exterior"
              label="Material exterior"
              bind:value={f.exterior_material}
              options={enumOptions([
                ['cristal', 'Cristal'],
                ['alucobond', 'Alucobond'],
                ['concreto', 'Concreto'],
                ['mixta', 'Mixta']
              ])}
            /><SmartSelect
              id="floor-material"
              label="Material de piso"
              bind:value={f.floor_material}
              options={enumOptions([
                ['porcelanato', 'Porcelanato'],
                ['ceramico', 'Cerámico'],
                ['epoxico', 'Epóxico'],
                ['concreto_pulido', 'Concreto pulido'],
                ['cemento', 'Cemento']
              ])}
            />
          </div></Card
        >
        <Card id="gallery" class="scroll-mt-24 p-6"
          ><BranchImagesEditor bind:images={f.images} companyId={company.id ?? ''} /></Card
        >
        <Card id="review" class="scroll-mt-24 p-6"
          ><h2 class="mb-4 text-base font-semibold">Revisión</h2>
          <dl class="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-foreground-muted">Sucursal</dt>
              <dd class="font-medium">{f.code || '—'} · {f.name || '—'}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Ubicación</dt>
              <dd class="font-medium">{f.address || '—'}</dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Responsable</dt>
              <dd class="font-medium">
                {employees.find((employee) => employee.id === f.manager_employee_id)?.first_name ??
                  'Sin responsable'}
              </dd>
            </div>
            <div>
              <dt class="text-foreground-muted">Galería</dt>
              <dd class="font-medium">{f.images.filter((image) => image.url).length} imagen(es)</dd>
            </div>
          </dl></Card
        >
      </main>
    </div>{/if}
</div>
