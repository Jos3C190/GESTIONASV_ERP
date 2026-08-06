<script lang="ts">
  import { onMount } from 'svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import Callout from '$lib/components/ui/Callout.svelte';
  import { suppliersApi } from '$lib/api/suppliers';
  import { catalogApi } from '$lib/api/catalog';
  import type { Supplier, SupplierContact } from '$lib/types/supplier';
  import type { Country } from '$lib/types/catalog';

  // Svelte 5 Runes State
  let suppliers = $state<Supplier[]>([]);
  let countries = $state<Country[]>([]);
  let loading = $state<boolean>(true);
  let errorMsg = $state<string | null>(null);

  // Search & Filter
  let search = $state<string>('');
  let selectedCountry = $state<number | undefined>(undefined);

  // Pagination
  let page = $state<number>(1);
  let totalPages = $state<number>(1);
  let totalItems = $state<number>(0);

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

  async function loadData() {
    loading = true;
    errorMsg = null;
    try {
      const [cRes, sRes] = await Promise.all([
        catalogApi.listCountries(true),
        suppliersApi.listSuppliers({
          country_id: selectedCountry,
          search: search.trim() || undefined,
          page,
          size: 10,
        }),
      ]);
      countries = cRes;
      suppliers = sRes.items;
      totalItems = sRes.meta.total;
      totalPages = sRes.meta.pages;
    } catch (err: any) {
      errorMsg = err.message || 'Error al cargar proveedores';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadData();
  });

  function handleSearch(e: Event) {
    e.preventDefault();
    page = 1;
    loadData();
  }

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
          is_active: formIsActive,
        });
      } else {
        await suppliersApi.createSupplier({
          code: formCode,
          name: formName,
          country: formCountry,
          address: formAddress,
          phone: formPhone,
          email: formEmail,
          website: formWebsite,
        });
      }
      showSupplierModal = false;
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Error al guardar el proveedor');
    } finally {
      savingSupplier = false;
    }
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
        email: contactEmail,
      });
      contactName = '';
      contactPhone = '';
      contactEmail = '';
      // Refresh supplier details
      const updated = await suppliersApi.getSupplier(selectedSupplier.id_supplier);
      selectedSupplier = updated;
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Error al agregar contacto');
    } finally {
      savingContact = false;
    }
  }

  async function handleDeleteContact(contactId: number) {
    if (!selectedSupplier || !confirm('¿Desea eliminar este contacto?')) return;
    try {
      await suppliersApi.deleteContact(contactId);
      const updated = await suppliersApi.getSupplier(selectedSupplier.id_supplier);
      selectedSupplier = updated;
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Error al eliminar contacto');
    }
  }

  function getCountryName(cId: number): string {
    const c = countries.find((item) => item.id_country === cId);
    return c ? `${c.name} (${c.iso_code_2})` : 'N/A';
  }
</script>

<svelte:head><title>Proveedores — ERP System</title></svelte:head>

<div class="flex flex-col gap-6 p-6 animate-fade-scale">
  <!-- Header -->
  <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
    <div>
      <h1 class="text-2xl font-bold text-foreground">Gestión de Proveedores</h1>
      <p class="mt-1 text-sm text-foreground-muted">
        Directorio de proveedores comerciales, ubicación por país y contactos directos.
      </p>
    </div>
    <div class="flex items-center gap-3">
      <Button variant="primary" onclick={openCreateSupplierModal}>
        <svg class="h-4 w-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Nuevo Proveedor
      </Button>
    </div>
  </div>

  <!-- Filters -->
  <Card class="p-4">
    <form onsubmit={handleSearch} class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="md:col-span-2">
        <input
          type="text"
          placeholder="Buscar por código, nombre o email..."
          bind:value={search}
          class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
      </div>
      <div>
        <select
          bind:value={selectedCountry}
          onchange={handleSearch}
          class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        >
          <option value={undefined}>Todos los países</option>
          {#each countries as country}
            <option value={country.id_country}>{country.name} ({country.iso_code_2})</option>
          {/each}
        </select>
      </div>
      <div>
        <Button type="submit" variant="secondary" class="w-full">Filtrar</Button>
      </div>
    </form>
  </Card>

  {#if errorMsg}
    <Callout variant="warning">{errorMsg}</Callout>
  {/if}

  <!-- Data Table -->
  <Card class="overflow-hidden p-0">
    {#if loading}
      <div class="p-8 space-y-4">
        {#each Array(5) as _}
          <div class="h-8 bg-surface-muted rounded animate-pulse"></div>
        {/each}
      </div>
    {:else if suppliers.length === 0}
      <div class="flex flex-col items-center justify-center p-12 text-center">
        <div class="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 mb-4">
          <svg class="h-8 w-8 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-foreground">No hay proveedores registrados</h3>
        <p class="text-sm text-foreground-muted mt-1">Registra nuevos proveedores comerciales para tu ERP.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm text-foreground">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted border-b border-border">
            <tr>
              <th class="px-4 py-3">Código</th>
              <th class="px-4 py-3">Proveedor</th>
              <th class="px-4 py-3">País</th>
              <th class="px-4 py-3">Teléfono / Email</th>
              <th class="px-4 py-3">Contactos</th>
              <th class="px-4 py-3">Estado</th>
              <th class="px-4 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each suppliers as sup}
              <tr class="hover:bg-surface-muted/50 transition-colors">
                <td class="px-4 py-3 font-mono font-semibold text-xs text-primary">{sup.code}</td>
                <td class="px-4 py-3">
                  <div class="font-medium text-foreground">{sup.name}</div>
                  {#if sup.address}
                    <div class="text-xs text-foreground-muted truncate max-w-xs">{sup.address}</div>
                  {/if}
                </td>
                <td class="px-4 py-3 text-foreground-muted">{getCountryName(sup.country)}</td>
                <td class="px-4 py-3 text-xs">
                  <div>{sup.phone || 'N/A'}</div>
                  <div class="text-foreground-muted">{sup.email || ''}</div>
                </td>
                <td class="px-4 py-3">
                  <button
                    onclick={() => openContactsModal(sup)}
                    class="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
                  >
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-2a4 4 0 100-8 4 4 0 000 8z" />
                    </svg>
                    {sup.contacts?.length || 0} Contacto(s)
                  </button>
                </td>
                <td class="px-4 py-3">
                  <Badge variant={sup.is_active ? 'success' : 'neutral'}>
                    {sup.is_active ? 'Activo' : 'Inactivo'}
                  </Badge>
                </td>
                <td class="px-4 py-3 text-right space-x-2">
                  <Button variant="ghost" size="sm" onclick={() => openEditSupplierModal(sup)}>Editar</Button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- Pagination Footer -->
      <div class="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-foreground-muted">
        <div>Mostrando {suppliers.length} de {totalItems} proveedores</div>
        <div class="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1}
            onclick={() => { page--; loadData(); }}
          >
            Anterior
          </Button>
          <span class="flex items-center px-2">Página {page} de {totalPages || 1}</span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= totalPages}
            onclick={() => { page++; loadData(); }}
          >
            Siguiente
          </Button>
        </div>
      </div>
    {/if}
  </Card>

  <!-- Supplier Form Modal -->
  {#if showSupplierModal}
    <Modal open={showSupplierModal} title={isEditingSupplier ? 'Editar Proveedor' : 'Nuevo Proveedor'} onclose={() => (showSupplierModal = false)}>
      <form onsubmit={handleSaveSupplier} class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="sup-code" class="block text-xs font-medium text-foreground-muted mb-1">Código *</label>
            <input id="sup-code" type="text" required bind:value={formCode} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="PROV-001" />
          </div>
          <div>
            <label for="sup-name" class="block text-xs font-medium text-foreground-muted mb-1">Nombre Comercial *</label>
            <input id="sup-name" type="text" required bind:value={formName} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="sup-country" class="block text-xs font-medium text-foreground-muted mb-1">País *</label>
            <select id="sup-country" required bind:value={formCountry} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
              {#each countries as c}
                <option value={c.id_country}>{c.name} ({c.iso_code_2})</option>
              {/each}
            </select>
          </div>
          <div>
            <label for="sup-phone" class="block text-xs font-medium text-foreground-muted mb-1">Teléfono Principal</label>
            <input id="sup-phone" type="text" bind:value={formPhone} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="+503 2200-0000" />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="sup-email" class="block text-xs font-medium text-foreground-muted mb-1">Correo Electrónico</label>
            <input id="sup-email" type="email" bind:value={formEmail} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
          </div>
          <div>
            <label for="sup-web" class="block text-xs font-medium text-foreground-muted mb-1">Sitio Web</label>
            <input id="sup-web" type="url" bind:value={formWebsite} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="https://proveedor.com" />
          </div>
        </div>

        <div>
          <label for="sup-addr" class="block text-xs font-medium text-foreground-muted mb-1">Dirección Física</label>
          <textarea id="sup-addr" rows="2" bind:value={formAddress} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"></textarea>
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
            <input type="text" required placeholder="Nombre completo *" bind:value={contactName} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground" />
            <input type="text" placeholder="Teléfono" bind:value={contactPhone} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground" />
            <input type="email" placeholder="Email" bind:value={contactEmail} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground" />
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
                  <Button variant="ghost" size="sm" class="text-danger hover:bg-danger/10" onclick={() => handleDeleteContact(contact.id_supplier_contact)}>
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
