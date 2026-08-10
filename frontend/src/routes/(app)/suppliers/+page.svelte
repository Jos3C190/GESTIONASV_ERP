<script lang="ts">
  import { untrack } from 'svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { suppliersApi } from '$lib/api/suppliers';
  import { catalogApi } from '$lib/api/catalog';
  import type { Supplier } from '$lib/types/supplier';
  import type { Country } from '$lib/types/catalog';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  // Svelte 5 Runes State
  let suppliers = $state<Supplier[]>([]);
  let countries = $state<Country[]>([]);
  let loading = $state<boolean>(true);
  let errorMsg = $state<string | null>(null);
  let successMsg = $state<string | null>(null);

  // Filters
  let selectedCountry = $state<number | undefined>(undefined);

  // Pagination
  let page = $state<number>(1);
  let totalPages = $state<number>(1);
  let totalItems = $state<number>(0);

  // KPI Stats
  let kpiTotal = $state<number>(0);
  let kpiActive = $state<number>(0);
  let kpiInactive = $state<number>(0);
  let kpiCountriesCount = $state<number>(0);

  // Supplier Modal State
  let showSupplierModal = $state<boolean>(false);
  let isEditingSupplier = $state<boolean>(false);
  let editingSupplierId = $state<number | null>(null);
  let savingSupplier = $state<boolean>(false);

  // Supplier Form
  let formCode = $state<string>('');
  let formName = $state<string>('');
  let formCountry = $state<number | undefined>(undefined);
  let formAddress = $state<string>('');
  let formPhone = $state<string>('');
  let formEmail = $state<string>('');
  let formWebsite = $state<string>('');
  let formIsActive = $state<boolean>(true);

  // Contacts Modal State
  let showContactModal = $state<boolean>(false);
  let selectedSupplier = $state<Supplier | null>(null);
  let contactName = $state<string>('');
  let contactPhone = $state<string>('');
  let contactEmail = $state<string>('');
  let savingContact = $state<boolean>(false);

  let dataGeneration = 0;

  async function loadData() {
    const generation = ++dataGeneration;
    loading = true;
    errorMsg = null;
    try {
      const [cRes, sRes, stats] = await Promise.all([
        catalogApi.listCountries(true),
        suppliersApi.listSuppliers({
          country_id: selectedCountry,
          search: globalSearch.query.trim() || undefined,
          active_only: false,
          page: untrack(() => page),
          size: 10
        }),
        suppliersApi.stats()
      ]);

      if (generation !== dataGeneration) return;

      countries = cRes;
      suppliers = sRes.items;
      totalItems = sRes.meta.total;
      totalPages = sRes.meta.pages;

      // KPIs
      kpiTotal = stats.total;
      kpiActive = stats.active;
      kpiInactive = stats.inactive;
      kpiCountriesCount = stats.countries;
    } catch (err: unknown) {
      if (generation !== dataGeneration) return;
      errorMsg = err instanceof Error ? err.message : 'Error al cargar proveedores';
    } finally {
      if (generation === dataGeneration) loading = false;
    }
  }

  function goToPage(p: number) {
    if (p < 1 || p > totalPages) return;
    page = p;
    loadData();
  }

  $effect(() => {
    const _q = globalSearch.query;
    const _c = selectedCountry;
    untrack(() => {
      page = 1;
      loadData();
    });
  });

  function openCreateSupplierModal() {
    isEditingSupplier = false;
    editingSupplierId = null;
    formCode = '';
    formName = '';
    formCountry = countries[0]?.id_country;
    formAddress = '';
    formPhone = '';
    formEmail = '';
    formWebsite = '';
    formIsActive = true;
    showSupplierModal = true;
  }

  function openEditSupplierModal(sup: Supplier) {
    isEditingSupplier = true;
    editingSupplierId = sup.id_supplier;
    formCode = sup.code;
    formName = sup.name;
    formCountry = sup.country;
    formAddress = sup.address ?? '';
    formPhone = sup.phone ?? '';
    formEmail = sup.email ?? '';
    formWebsite = sup.website ?? '';
    formIsActive = sup.is_active;
    showSupplierModal = true;
  }

  async function handleSaveSupplier(e: SubmitEvent) {
    e.preventDefault();
    if (!formCountry) return;
    savingSupplier = true;
    errorMsg = null;
    successMsg = null;
    try {
      if (isEditingSupplier && editingSupplierId) {
        await suppliersApi.updateSupplier(editingSupplierId, {
          code: formCode,
          name: formName,
          country: formCountry,
          address: formAddress,
          phone: formPhone,
          email: formEmail,
          website: formWebsite,
          is_active: formIsActive
        });
        successMsg = 'Proveedor actualizado exitosamente.';
      } else {
        await suppliersApi.createSupplier({
          code: formCode,
          name: formName,
          country: formCountry,
          address: formAddress,
          phone: formPhone,
          email: formEmail,
          website: formWebsite
        });
        successMsg = 'Proveedor creado exitosamente.';
      }
      showSupplierModal = false;
      await loadData();
    } catch (err: unknown) {
      errorMsg = err instanceof Error ? err.message : 'Error al guardar el proveedor';
    } finally {
      savingSupplier = false;
    }
  }

  function toggleSupplierStatus(sup: Supplier) {
    const actionText = sup.is_active ? 'desactivar' : 'activar';
    confirmation.request({
      kind: sup.is_active ? 'deactivate' : 'deactivate',
      title: `${sup.is_active ? 'Desactivar' : 'Activar'} proveedor`,
      description: `¿Está seguro de que desea ${actionText} a "${sup.name}"?`,
      resourceName: sup.name,
      confirmLabel: sup.is_active ? 'Desactivar' : 'Activar',
      execute: async () => {
        try {
          await suppliersApi.updateSupplier(sup.id_supplier, { is_active: !sup.is_active });
          successMsg = `Proveedor ${sup.is_active ? 'desactivado' : 'activado'} correctamente.`;
          await loadData();
        } catch (err: unknown) {
          errorMsg = err instanceof Error ? err.message : 'Error al cambiar estado del proveedor';
        }
      }
    });
  }

  function openContactsModal(sup: Supplier) {
    selectedSupplier = sup;
    contactName = '';
    contactPhone = '';
    contactEmail = '';
    showContactModal = true;
  }

  async function handleAddContact(e: SubmitEvent) {
    e.preventDefault();
    if (!selectedSupplier) return;
    savingContact = true;
    try {
      await suppliersApi.addContact(selectedSupplier.id_supplier, {
        full_name: contactName,
        phone: contactPhone,
        email: contactEmail
      });
      contactName = '';
      contactPhone = '';
      contactEmail = '';
      const updated = await suppliersApi.getSupplier(selectedSupplier.id_supplier);
      selectedSupplier = updated;
      await loadData();
    } catch (err: unknown) {
      errorMsg = err instanceof Error ? err.message : 'Error al agregar contacto';
    } finally {
      savingContact = false;
    }
  }

  function handleDeleteContact(contactId: number, name: string) {
    if (!selectedSupplier) return;
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar contacto',
      description: `¿Está seguro de eliminar el contacto "${name}"?`,
      resourceName: name,
      confirmLabel: 'Eliminar contacto',
      execute: async () => {
        try {
          await suppliersApi.deleteContact(contactId);
          if (selectedSupplier) {
            const updated = await suppliersApi.getSupplier(selectedSupplier.id_supplier);
            selectedSupplier = updated;
          }
          await loadData();
        } catch (err: unknown) {
          errorMsg = err instanceof Error ? err.message : 'Error al eliminar contacto';
        }
      }
    });
  }

  function menuItems(sup: Supplier): KebabItem[] {
    const items: KebabItem[] = [
      {
        id: 'contacts',
        label: 'Ver contactos',
        icon: 'detail',
        onClick: () => openContactsModal(sup)
      }
    ];

    if (permissions.hasPermission('suppliers:manage')) {
      items.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => openEditSupplierModal(sup)
      });
      items.push({
        id: 'toggle-status',
        label: sup.is_active ? 'Desactivar' : 'Activar',
        icon: sup.is_active ? 'delete' : 'edit',
        variant: sup.is_active ? 'danger' : 'default',
        onClick: () => toggleSupplierStatus(sup)
      });
    }
    return items;
  }

  function getCountryName(cId: number): string {
    const c = countries.find((item) => item.id_country === cId);
    return c ? `${c.name} (${c.iso_code_2})` : '—';
  }

  // Ring geometry calculation
  const ringR = 16;
  const ringC = 2 * Math.PI * ringR;
  let ringOffset = $derived(kpiTotal > 0 ? ringC - (kpiActive / kpiTotal) * ringC : ringC);
  let activeRatio = $derived(kpiTotal > 0 ? Math.round((kpiActive / kpiTotal) * 100) : 0);
</script>

<svelte:head><title>Proveedores — GestionaSV</title></svelte:head>

<div class="p-6 md:p-8">
  <!-- Header -->
  <div class="mb-5 flex items-center justify-between gap-4">
    <p class="text-sm text-foreground-muted">
      {loading ? 'Cargando...' : `${totalItems} proveedor(es)`}
    </p>
    <div class="flex items-center gap-2">
      <select
        bind:value={selectedCountry}
        onchange={() => {
          page = 1;
        }}
        class="h-8 rounded-md border border-border bg-surface-muted px-2.5 text-[13px] text-foreground focus:border-primary focus:shadow-glow focus:outline-none"
      >
        <option value={undefined}>Todos los países</option>
        {#each countries as country}
          <option value={country.id_country}>{country.name} ({country.iso_code_2})</option>
        {/each}
      </select>

      {#if permissions.hasPermission('suppliers:manage')}
        <Button size="sm" onclick={openCreateSupplierModal}>
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

  <!-- KPI CARDS GRID -->
  <div class="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <!-- KPI 1: Total Proveedores -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Total proveedores</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            ><path d="M19 21V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v16" /><line x1="1" y1="21" x2="23" y2="21" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-16 rounded skeleton"></span>{:else}{kpiTotal}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Registrados en el sistema</p>
      </div>
    </div>

    <!-- KPI 2: Proveedores Activos -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Activos</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-success/10 text-success">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            ><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-10 rounded skeleton"></span>{:else}{kpiActive}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Operativos actualmente</p>
      </div>
    </div>

    <!-- KPI 3: Inactivos -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Inactivos</span
        >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-danger/10 text-danger">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            ><circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" /></svg
          >
        </div>
      </div>
      <div>
        <div class="font-mono text-2xl font-bold tabular-nums text-foreground">
          {#if loading}<span class="inline-block h-7 w-8 rounded skeleton"></span>{:else}{kpiInactive}{/if}
        </div>
        <p class="text-[11px] text-foreground-subtle mt-1">Sin operación activa</p>
      </div>
    </div>

    <!-- KPI 4: Países Registrados + Mini Ring -->
    <div
      class="rounded-xl border border-border bg-surface-elevated p-4 md:p-5 shadow-sm flex flex-col justify-between h-[120px]"
    >
      <div class="flex items-center justify-between">
        <span class="text-[10.5px] font-bold uppercase tracking-wider text-foreground-subtle"
          >Países de Origen</span
        >
        <div class="font-mono text-lg font-bold text-foreground">
          {#if loading}<span class="inline-block h-5 w-12 rounded skeleton"></span>{:else}{kpiCountriesCount}
            <span class="text-xs font-normal text-foreground-subtle">países</span>{/if}
        </div>
      </div>
      <div class="flex items-center gap-3">
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
          <p><strong class="font-semibold text-foreground">{activeRatio}%</strong> activos</p>
          <p>
            <strong class="font-semibold text-foreground-subtle">{kpiTotal - kpiActive}</strong> inactivos
          </p>
        </div>
      </div>
    </div>
  </div>

  {#if errorMsg}
    <div class="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
      {errorMsg}
    </div>
  {/if}
  {#if successMsg}
    <div class="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success" role="status">
      {successMsg}
    </div>
  {/if}

  <!-- Data Table -->
  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="flex items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">Cargando...</p>
      </div>
    {:else if suppliers.length === 0}
      <div class="flex flex-col items-center justify-center py-16">
        <p class="text-sm text-foreground-muted">No se encontraron proveedores.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border bg-surface-muted">
            <tr>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Código</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Proveedor</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">País</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Contacto / Email</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Contactos</th>
              <th class="px-4 py-3 text-left font-semibold text-foreground">Estado</th>
              <th class="px-2 py-3 text-center font-semibold text-foreground w-11"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each suppliers as sup (sup.id_supplier)}
              <tr class="hover:bg-surface-muted">
                <td class="px-4 py-3 font-mono text-foreground">{sup.code}</td>
                <td class="px-4 py-3">
                  <div class="font-medium text-foreground">{sup.name}</div>
                  {#if sup.address}
                    <div class="text-xs text-foreground-muted truncate max-w-xs">{sup.address}</div>
                  {/if}
                </td>
                <td class="px-4 py-3 text-foreground-muted">{getCountryName(sup.country)}</td>
                <td class="px-4 py-3 text-foreground-muted text-xs">
                  <div>{sup.phone || '—'}</div>
                  <div>{sup.email || ''}</div>
                </td>
                <td class="px-4 py-3">
                  <button
                    onclick={() => openContactsModal(sup)}
                    class="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
                  >
                    <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-2a4 4 0 100-8 4 4 0 000 8z" />
                    </svg>
                    {sup.contacts?.length || 0} contacto(s)
                  </button>
                </td>
                <td class="px-4 py-3">
                  <span
                    class="{sup.is_active ? 'badge-success' : 'badge-neutral'} inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium"
                  >
                    <span class="h-1.5 w-1.5 rounded-full bg-current"></span>
                    {sup.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td class="px-2 py-3 text-center">
                  <KebabMenu items={menuItems(sup)} />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </Card>

  <!-- Pagination -->
  {#if totalPages > 1}
    <div class="mt-4 flex items-center justify-between">
      <p class="text-xs text-foreground-muted">Página {page} de {totalPages}</p>
      <div class="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onclick={() => goToPage(page - 1)}
          disabled={page <= 1}>Anterior</Button
        >
        <Button
          variant="secondary"
          size="sm"
          onclick={() => goToPage(page + 1)}
          disabled={page >= totalPages}>Siguiente</Button
        >
      </div>
    </div>
  {/if}

  <!-- Supplier Form Modal -->
  {#if showSupplierModal}
    <Modal open={showSupplierModal} title={isEditingSupplier ? 'Editar Proveedor' : 'Nuevo Proveedor'} onclose={() => (showSupplierModal = false)}>
      <form onsubmit={handleSaveSupplier} class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="sup-code" class="block text-xs font-medium text-foreground-muted mb-1">Código *</label>
            <input id="sup-code" type="text" required bind:value={formCode} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" placeholder="PROV-001" />
          </div>
          <div>
            <label for="sup-name" class="block text-xs font-medium text-foreground-muted mb-1">Nombre Comercial *</label>
            <input id="sup-name" type="text" required bind:value={formName} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="sup-country" class="block text-xs font-medium text-foreground-muted mb-1">País *</label>
            <select id="sup-country" required bind:value={formCountry} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
              {#each countries as c}
                <option value={c.id_country}>{c.name} ({c.iso_code_2})</option>
              {/each}
            </select>
          </div>
          <div>
            <label for="sup-phone" class="block text-xs font-medium text-foreground-muted mb-1">Teléfono Principal</label>
            <input id="sup-phone" type="text" bind:value={formPhone} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" placeholder="+503 2200-0000" />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="sup-email" class="block text-xs font-medium text-foreground-muted mb-1">Correo Electrónico</label>
            <input id="sup-email" type="email" bind:value={formEmail} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" />
          </div>
          <div>
            <label for="sup-web" class="block text-xs font-medium text-foreground-muted mb-1">Sitio Web</label>
            <input id="sup-web" type="url" bind:value={formWebsite} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" placeholder="https://proveedor.com" />
          </div>
        </div>

        <div>
          <label for="sup-addr" class="block text-xs font-medium text-foreground-muted mb-1">Dirección Física</label>
          <textarea id="sup-addr" rows="2" bind:value={formAddress} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"></textarea>
        </div>

        {#if isEditingSupplier}
          <div class="flex items-center gap-2">
            <input type="checkbox" id="sup-active" bind:checked={formIsActive} class="rounded border-border text-primary" />
            <label for="sup-active" class="text-sm font-medium text-foreground">Proveedor Activo</label>
          </div>
        {/if}

        <div class="flex justify-end gap-3 pt-4 border-t border-border">
          <Button type="button" variant="secondary" onclick={() => (showSupplierModal = false)}>Cancelar</Button>
          <Button type="submit" variant="primary" disabled={savingSupplier}>
            {savingSupplier ? 'Guardando...' : 'Guardar Proveedor'}
          </Button>
        </div>
      </form>
    </Modal>
  {/if}

  <!-- Contacts Modal -->
  {#if showContactModal && selectedSupplier}
    <Modal open={showContactModal} title={`Contactos — ${selectedSupplier.name}`} onclose={() => (showContactModal = false)}>
      <div class="space-y-6">
        <!-- Add Contact Form -->
        <form onsubmit={handleAddContact} class="bg-surface-muted/50 p-4 rounded-lg space-y-3">
          <h4 class="text-xs font-semibold uppercase text-foreground-muted">Agregar Nuevo Contacto</h4>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input type="text" required placeholder="Nombre completo *" bind:value={contactName} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground focus:border-primary focus:outline-none" />
            <input type="text" placeholder="Teléfono" bind:value={contactPhone} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground focus:border-primary focus:outline-none" />
            <input type="email" placeholder="Email" bind:value={contactEmail} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground focus:border-primary focus:outline-none" />
          </div>
          <div class="flex justify-end">
            <Button type="submit" size="sm" variant="primary" disabled={savingContact}>
              {savingContact ? 'Agregando...' : '+ Agregar Contacto'}
            </Button>
          </div>
        </form>

        <!-- Contacts List -->
        <div class="space-y-2">
          <h4 class="text-xs font-semibold uppercase text-foreground-muted">Contactos Registrados</h4>
          {#if selectedSupplier.contacts.length === 0}
            <p class="text-xs text-foreground-muted py-3 text-center">No hay contactos registrados aún.</p>
          {:else}
            <div class="divide-y divide-border border border-border rounded-lg">
              {#each selectedSupplier.contacts as contact}
                <div class="flex items-center justify-between p-3">
                  <div>
                    <div class="font-medium text-sm text-foreground">{contact.full_name}</div>
                    <div class="text-xs text-foreground-muted">
                      {contact.phone || 'Sin tel'} {contact.email ? ` | ${contact.email}` : ''}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" class="text-danger hover:bg-danger/10" onclick={() => handleDeleteContact(contact.id_supplier_contact, contact.full_name)}>
                    Eliminar
                  </Button>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    </Modal>
  {/if}
</div>
