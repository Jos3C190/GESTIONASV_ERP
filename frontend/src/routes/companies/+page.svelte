<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { api, HttpError, type CompanyOut } from '$lib/api/client';
  import { session } from '$lib/stores/session.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { clearPrivateQueryCache } from '$lib/services/query-client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import ImageUpload from '$lib/components/ui/ImageUpload.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';

  let companies = $state<CompanyOut[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let modalOpen = $state(false);
  let editing = $state<CompanyOut | null>(null);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let departments = $state<{ id: string; name: string }[]>([]);
  let municipalities = $state<{ id: string; department_id: string; name: string }[]>([]);
  let districts = $state<{ id: string; municipality_id: string; name: string }[]>([]);
  let f = $state({
    name: '',
    commercial_name: '',
    nit: '',
    nrc: '',
    commercial_line_1: '',
    address: '',
    department_id: '',
    municipality_id: '',
    district_id: '',
    phone: '',
    email: '',
    web_site: '',
    logo: '',
    description: ''
  });

  async function load() {
    loading = true;
    error = null;
    try {
      if (!session.isAuthenticated) {
        await goto('/login');
        return;
      }
      const p = await api.auth.myPermissions();
      permissions.set(p.permissions, p.is_superuser);
      [companies, departments] = await Promise.all([
        api.companies.accessible(),
        api.geography.departments()
      ]);
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron cargar las empresas.';
    } finally {
      loading = false;
    }
  }

  async function selectCompany(item: CompanyOut) {
    if (!item.is_active) return;
    error = null;
    try {
      await clearPrivateQueryCache();
      branch.clear();
      company.select({
        id: item.id,
        name: item.name,
        commercial_name: item.commercial_name,
        logo: item.logo
      });
      const context = await api.operationalContext.get(item.id);
      branch.configure(context);
      if (!context.access_all_branches && context.branches.length === 0) {
        throw new Error('No tiene sucursales autorizadas en esta empresa.');
      }
      await goto('/dashboard');
    } catch (err) {
      branch.clear();
      company.clear();
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo abrir la empresa.';
    }
  }

  async function loadMunicipalities() {
    f.municipality_id = '';
    f.district_id = '';
    districts = [];
    municipalities = f.department_id ? await api.geography.municipalities(f.department_id) : [];
  }
  async function loadDistricts() {
    f.district_id = '';
    districts = f.municipality_id ? await api.geography.districts(f.municipality_id) : [];
  }

  async function openCreate() {
    editing = null;
    formError = null;
    f = {
      name: '',
      commercial_name: '',
      nit: '',
      nrc: '',
      commercial_line_1: '',
      address: '',
      department_id: '',
      municipality_id: '',
      district_id: '',
      phone: '',
      email: '',
      web_site: '',
      logo: '',
      description: ''
    };
    municipalities = [];
    districts = [];
    modalOpen = true;
  }
  async function openEdit(item: CompanyOut) {
    editing = item;
    formError = null;
    f = {
      name: item.name,
      commercial_name: item.commercial_name,
      nit: item.nit,
      nrc: item.nrc,
      commercial_line_1: item.commercial_line_1 ?? '',
      address: item.address,
      department_id: item.department_id,
      municipality_id: item.municipality_id,
      district_id: item.district_id,
      phone: item.phone ?? '',
      email: item.email ?? '',
      web_site: item.web_site ?? '',
      logo: item.logo ?? '',
      description: item.description ?? ''
    };
    municipalities = await api.geography.municipalities(f.department_id);
    districts = await api.geography.districts(f.municipality_id);
    modalOpen = true;
  }
  async function save() {
    saving = true;
    formError = null;
    try {
      const payload = {
        ...f,
        commercial_line_1: f.commercial_line_1 || null,
        phone: f.phone || null,
        email: f.email || null,
        web_site: f.web_site || null,
        logo: f.logo || null,
        description: f.description || null
      };
      if (editing) {
        await api.companies.update(editing.id, payload);
        if (editing.logo && editing.logo !== f.logo) {
          await api.media.deleteImageByUrl(editing.id, editing.logo).catch(() => undefined);
        }
      } else await api.companies.create(payload);
      modalOpen = false;
      await load();
    } catch (err) {
      formError = err instanceof HttpError ? err.message : 'No se pudo guardar la empresa.';
    } finally {
      saving = false;
    }
  }
  async function toggleActive(item: CompanyOut) {
    if (item.is_active) {
      confirmation.request({
        kind: 'deactivate',
        title: 'Desactivar empresa',
        description:
          'La empresa dejará de estar disponible para nuevas operaciones. Sus datos se conservarán.',
        resourceName: item.commercial_name,
        confirmLabel: 'Desactivar',
        execute: async () => {
          await api.companies.deactivate(item.id);
          await load();
        }
      });
      return;
    }
    try {
      await api.companies.activate(item.id);
      await load();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo cambiar el estado.';
    }
  }

  function companyActions(item: CompanyOut): KebabItem[] {
    const actions: KebabItem[] = [];
    if (permissions.hasPermission('companies.update')) {
      actions.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => void openEdit(item)
      });
    }
    if (permissions.hasPermission(item.is_active ? 'companies.deactivate' : 'companies.activate')) {
      actions.push({
        id: 'state',
        label: item.is_active ? 'Desactivar' : 'Activar',
        icon: 'power',
        variant: item.is_active ? 'danger' : 'default',
        onClick: () => void toggleActive(item)
      });
    }
    return actions;
  }

  onMount(load);
</script>

<svelte:head><title>Seleccionar empresa — ERP System</title></svelte:head>

<main class="min-h-screen bg-surface px-6 py-10 text-foreground">
  <div class="mx-auto max-w-6xl">
    <header class="mb-10 flex items-center justify-between gap-4">
      <div>
        <p class="text-sm font-semibold text-primary">ERP System</p>
        <h1 class="mt-1 text-3xl font-bold tracking-tight">¿En qué empresa trabajará?</h1>
        <p class="mt-2 text-sm text-foreground-muted">
          Seleccione el contexto operativo para continuar.
        </p>
      </div>
      <div class="flex gap-2">
        {#if permissions.hasPermission('companies.create')}<Button onclick={openCreate}
            >Agregar empresa</Button
          >{/if}
        <Button
          variant="secondary"
          onclick={() => {
            session.clear();
            permissions.clear();
            goto('/login');
          }}>Salir</Button
        >
      </div>
    </header>

    {#if error}<div
        class="mb-6 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
        role="alert"
      >
        {error}
      </div>{/if}
    {#if loading}
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {#each Array(4) as _}<div
            class="aspect-square rounded-2xl border border-border skeleton"
          ></div>{/each}
      </div>
    {:else if companies.length === 0}
      <div class="rounded-3xl border border-dashed border-border p-16 text-center">
        <p class="text-foreground-muted">No tiene empresas disponibles.</p>
        {#if permissions.hasPermission('companies.create')}<div class="mt-5">
            <Button onclick={openCreate}>Crear primera empresa</Button>
          </div>{/if}
      </div>
    {:else}
      <div class="grid grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {#each companies as item (item.id)}
          <article class="group relative min-w-0 {item.is_active ? '' : 'opacity-65'}">
            {#if companyActions(item).length > 0}
              <div
                class="absolute right-2 top-2 z-10 rounded-lg border border-white/10 bg-black/60 p-0.5 opacity-100 shadow-md backdrop-blur-md transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
              >
                <KebabMenu
                  items={companyActions(item)}
                  orientation="horizontal"
                  ariaLabel={`Acciones de ${item.commercial_name}`}
                  triggerClass="!text-white hover:!bg-white/15 hover:!text-white"
                />
              </div>
            {/if}
            <button
              class="block w-full text-left disabled:cursor-not-allowed"
              disabled={!item.is_active}
              onclick={() => selectCompany(item)}
            >
              <div
                class="relative flex aspect-square items-center justify-center overflow-hidden rounded-2xl border border-border bg-surface-elevated shadow-soft transition-all duration-200 group-hover:-translate-y-0.5 group-hover:border-border-strong group-hover:shadow-lifted group-focus-within:border-primary/50 {item.is_active
                  ? ''
                  : 'grayscale'}"
              >
                {#if item.logo}<img
                    src={item.logo}
                    alt="Logo de {item.commercial_name}"
                    class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.025]"
                  />{:else}<div
                    class="flex h-full w-full items-center justify-center bg-gradient-to-br from-primary/15 to-accent/10"
                  >
                    <span class="text-4xl font-semibold tracking-tight text-primary"
                      >{item.commercial_name.slice(0, 1).toUpperCase()}</span
                    >
                  </div>{/if}
                <span
                  class="absolute bottom-2 left-2 inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-black/60 px-2 py-1 text-[10px] font-medium text-white backdrop-blur-md"
                >
                  <span
                    class="h-1.5 w-1.5 rounded-full {item.is_active
                      ? 'bg-success'
                      : 'bg-foreground-subtle'}"
                  ></span>
                  {item.is_active ? 'Activa' : 'Inactiva'}
                </span>
              </div>
              <h2 class="mt-3 truncate text-sm font-semibold text-foreground">
                {item.commercial_name}
              </h2>
              <p class="mt-0.5 truncate text-xs text-foreground-muted">{item.name}</p>
            </button>
          </article>
        {/each}
      </div>
    {/if}
  </div>
</main>

<Modal
  open={modalOpen}
  title={editing ? 'Editar empresa' : 'Nueva empresa'}
  onclose={() => (modalOpen = false)}
  size="lg"
>
  <form
    class="grid gap-4 sm:grid-cols-2"
    onsubmit={(e) => {
      e.preventDefault();
      save();
    }}
  >
    {#if formError}<div
        class="sm:col-span-2 rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
      >
        {formError}
      </div>{/if}
    <FormField id="company-name" label="Razón social" bind:value={f.name} required />
    <FormField
      id="company-commercial"
      label="Nombre comercial"
      bind:value={f.commercial_name}
      required
    />
    <FormField id="company-nit" label="NIT" bind:value={f.nit} required />
    <FormField id="company-nrc" label="NRC" bind:value={f.nrc} required />
    <FormField
      id="company-line"
      label="Giro comercial principal"
      bind:value={f.commercial_line_1}
    />
    <FormField id="company-phone" label="Teléfono" bind:value={f.phone} />
    <FormField id="company-email" label="Correo" type="email" bind:value={f.email} />
    <FormField id="company-web" label="Sitio web" bind:value={f.web_site} />
    <div class="sm:col-span-2">
      <ImageUpload
        id="company-logo"
        label="Logotipo de la empresa"
        purpose="company_logo"
        companyId={editing?.id ?? null}
        bind:value={f.logo}
        alt={`Logotipo de ${f.commercial_name || 'la empresa'}`}
      />
    </div>
    <FormField id="company-address" label="Dirección" bind:value={f.address} required />
    <FormField
      id="company-dept"
      label="Departamento"
      bind:value={f.department_id}
      oninput={loadMunicipalities}
      required
      options={[
        { value: '', label: 'Seleccione…' },
        ...departments.map((x) => ({ value: x.id, label: x.name }))
      ]}
    />
    <FormField
      id="company-muni"
      label="Municipio"
      bind:value={f.municipality_id}
      oninput={loadDistricts}
      required
      options={[
        { value: '', label: 'Seleccione…' },
        ...municipalities.map((x) => ({ value: x.id, label: x.name }))
      ]}
    />
    <FormField
      id="company-district"
      label="Distrito"
      bind:value={f.district_id}
      required
      options={[
        { value: '', label: 'Seleccione…' },
        ...districts.map((x) => ({ value: x.id, label: x.name }))
      ]}
    />
    <div class="sm:col-span-2">
      <FormField id="company-description" label="Descripción" bind:value={f.description} />
    </div>
    <div class="sm:col-span-2 flex justify-end gap-2 pt-2">
      <Button variant="secondary" onclick={() => (modalOpen = false)}>Cancelar</Button><Button
        type="submit"
        disabled={saving}>{saving ? 'Guardando…' : 'Guardar empresa'}</Button
      >
    </div>
  </form>
</Modal>
