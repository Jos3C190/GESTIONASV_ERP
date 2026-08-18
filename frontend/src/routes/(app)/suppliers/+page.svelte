<script lang="ts">
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { api, HttpError } from '$lib/api/client';
  import { suppliersApi, type SupplierStats } from '$lib/api/suppliers';
  import { catalogApi } from '$lib/api/catalog';
  import type { Currency, PaymentTerms, Supplier, SupplierGroup } from '$lib/types/supplier';
  import type { Country } from '$lib/types/catalog';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  let suppliers = $state<Supplier[]>([]);
  let countries = $state<Country[]>([]);
  let currencies = $state<Currency[]>([]);
  let supplierGroups = $state<SupplierGroup[]>([]);
  let paymentTerms = $state<PaymentTerms[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let selectedCountry = $state('');
  let page = $state(1);
  let totalPages = $state(1);
  let totalItems = $state(0);
  let stats = $state<SupplierStats>({ total: 0, active: 0, inactive: 0, countries: 0 });
  let dataGeneration = 0;

  async function loadData() {
    const generation = ++dataGeneration;
    loading = true;
    error = null;
    try {
      const [countryData, list, supplierStats, currencyData, groupData, termsData] =
        await Promise.all([
          countries.length ? Promise.resolve(countries) : catalogApi.listCountries(true),
          suppliersApi.listSuppliers({
            country_id: selectedCountry ? Number(selectedCountry) : undefined,
            search: globalSearch.query.trim() || undefined,
            active_only: false,
            page: untrack(() => page),
            size: 10
          }),
          suppliersApi.stats(),
          currencies.length ? Promise.resolve(currencies) : suppliersApi.currencies(),
          supplierGroups.length ? Promise.resolve(supplierGroups) : suppliersApi.groups(),
          paymentTerms.length ? Promise.resolve(paymentTerms) : suppliersApi.paymentTerms()
        ]);
      if (generation !== dataGeneration) return;
      countries = countryData;
      suppliers = list.items;
      totalItems = list.meta.total;
      totalPages = list.meta.pages;
      stats = supplierStats;
      currencies = currencyData;
      supplierGroups = groupData;
      paymentTerms = termsData;
    } catch (err: unknown) {
      if (generation === dataGeneration)
        error =
          err instanceof HttpError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'No se pudieron cargar los proveedores.';
    } finally {
      if (generation === dataGeneration) loading = false;
    }
  }

  $effect(() => {
    const query = globalSearch.query;
    const country = selectedCountry;
    untrack(() => {
      void query;
      void country;
      page = 1;
      void loadData();
    });
  });

  function countryName(id: number) {
    const country = countries.find((item) => item.id_country === id);
    return country ? `${country.name} (${country.iso_code_2})` : '—';
  }

  function pageTo(next: number) {
    if (next < 1 || next > totalPages) return;
    page = next;
    void loadData();
  }

  function toggleSupplier(supplier: Supplier) {
    const activate = !supplier.is_active;
    confirmation.request({
      kind: 'deactivate',
      title: `${activate ? 'Activar' : 'Desactivar'} proveedor`,
      description: activate
        ? 'El proveedor volverá a estar disponible para operaciones.'
        : 'El proveedor dejará de estar disponible para nuevas operaciones.',
      resourceName: supplier.name,
      confirmLabel: activate ? 'Activar proveedor' : 'Desactivar proveedor',
      execute: async () => {
        await suppliersApi.updateSupplier(supplier.id_supplier, { is_active: activate });
        success = `Proveedor ${activate ? 'activado' : 'desactivado'} correctamente.`;
        await loadData();
      }
    });
  }

  function deleteSupplier(supplier: Supplier) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar proveedor',
      description:
        'El proveedor se enviará a la Papelera y dejará de aparecer en la operación diaria.',
      resourceName: supplier.name,
      confirmLabel: 'Eliminar proveedor',
      requireReason: true,
      reasonLabel: 'Motivo de eliminación',
      execute: async (reason) => {
        if (!reason) return;
        await api.lifecycle.delete('suppliers', String(supplier.id_supplier), reason);
        success = 'Proveedor enviado a la Papelera.';
        await loadData();
      }
    });
  }

  function menuItems(supplier: Supplier): KebabItem[] {
    const items: KebabItem[] = [
      {
        id: 'detail',
        label: 'Ver detalle',
        icon: 'detail',
        onClick: () => void goto(`/suppliers/${supplier.id_supplier}`)
      },
      {
        id: 'contacts',
        label: 'Gestionar contactos',
        icon: 'detail',
        onClick: () => void goto(`/suppliers/${supplier.id_supplier}/contacts`)
      }
    ];
    if (permissions.hasPermission('suppliers:manage')) {
      items.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => void goto(`/suppliers/${supplier.id_supplier}/edit`)
      });
      items.push({
        id: 'status',
        label: supplier.is_active ? 'Desactivar' : 'Activar',
        icon: supplier.is_active ? 'delete' : 'power',
        variant: supplier.is_active ? 'danger' : 'default',
        onClick: () => toggleSupplier(supplier)
      });
    }
    if (permissions.hasPermission('suppliers:delete'))
      items.push({
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => deleteSupplier(supplier)
      });
    return items;
  }

  const activeRatio = $derived(
    stats.total > 0 ? Math.round((stats.active / stats.total) * 100) : 0
  );
</script>

<svelte:head><title>Proveedores — GestionaSV</title></svelte:head>

<div class="min-h-full bg-background px-4 pb-8 sm:px-6 md:px-8">
  <header
    class="mb-5 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center sm:gap-4"
  >
    <p class="text-sm text-foreground-muted">
      {totalItems} proveedor(es) registrados · Maestro comercial y operativo
    </p>
    <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto">
      <select
        aria-label="Filtrar por país"
        value={selectedCountry}
        onchange={(event) => {
          selectedCountry = (event.currentTarget as HTMLSelectElement).value;
        }}
        class="h-9 rounded-md border border-border bg-surface px-3 text-xs font-medium text-foreground focus:border-primary focus:outline-none"
        ><option value="">Todos los países</option>{#each countries as country}<option
            value={country.id_country}>{country.name} ({country.iso_code_2})</option
          >{/each}</select
      >{#if permissions.hasPermission('suppliers:manage')}<Button
          size="sm"
          class="whitespace-nowrap"
          onclick={() => goto('/suppliers/new')}
          ><svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg
          >Nuevo proveedor</Button
        >{/if}
    </div>
  </header>

  <div class="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
    <Card class="flex h-[120px] flex-col justify-between p-4"
      ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
        Total proveedores
      </p>
      <div>
        <p class="font-mono text-2xl font-bold text-foreground">{loading ? '—' : stats.total}</p>
        <p class="mt-1 text-xs text-foreground-subtle">Registrados en el sistema</p>
      </div></Card
    ><Card class="flex h-[120px] flex-col justify-between p-4"
      ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">Activos</p>
      <div>
        <p class="font-mono text-2xl font-bold text-success">{loading ? '—' : stats.active}</p>
        <p class="mt-1 text-xs text-foreground-subtle">{activeRatio}% del total</p>
      </div></Card
    ><Card class="flex h-[120px] flex-col justify-between p-4"
      ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
        Inactivos
      </p>
      <div>
        <p class="font-mono text-2xl font-bold text-foreground">{loading ? '—' : stats.inactive}</p>
        <p class="mt-1 text-xs text-foreground-subtle">Sin operación activa</p>
      </div></Card
    ><Card class="flex h-[120px] flex-col justify-between p-4"
      ><p class="text-[10px] font-bold uppercase tracking-wider text-foreground-subtle">
        Países de origen
      </p>
      <div>
        <p class="font-mono text-2xl font-bold text-foreground">
          {loading ? '—' : stats.countries}
        </p>
        <p class="mt-1 text-xs text-foreground-subtle">Proveedores internacionales incluidos</p>
      </div></Card
    >
  </div>

  {#if error}<div
      class="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>{/if}{#if success}<div
      class="mb-4 rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
      role="status"
    >
      {success}
    </div>{/if}

  <Card class="overflow-hidden p-0"
    ><div class="flex items-center justify-between border-b border-border px-4 py-3">
      <div>
        <h2 class="text-sm font-semibold text-foreground">Directorio de proveedores</h2>
        <p class="mt-1 text-xs text-foreground-muted">
          {loading ? 'Cargando…' : `${totalItems} proveedor(es)`}
        </p>
      </div>
    </div>
    {#if loading}<div class="flex items-center justify-center py-20">
        <div class="flex flex-col items-center gap-3">
          <svg
            class="h-5 w-5 animate-spin text-primary"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
            ><circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            /><path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            /></svg
          >
          <p class="text-xs text-foreground-muted">Cargando proveedores…</p>
        </div>
      </div>{:else if suppliers.length === 0}<div
        class="flex flex-col items-center justify-center px-5 py-20 text-center"
      >
        <p class="text-sm font-medium text-foreground">No se encontraron proveedores</p>
        <p class="mt-1 text-xs text-foreground-muted">
          Prueba con otro país o registra un nuevo proveedor.
        </p>
        {#if permissions.hasPermission('suppliers:manage')}<Button
            class="mt-4"
            size="sm"
            onclick={() => goto('/suppliers/new')}>Nuevo proveedor</Button
          >{/if}
      </div>{:else}<div class="overflow-x-auto">
        <table class="w-full min-w-[860px] text-sm">
          <thead class="border-b border-border bg-surface-muted"
            ><tr
              ><th class="px-4 py-3 text-left font-semibold text-foreground">Código</th><th
                class="px-4 py-3 text-left font-semibold text-foreground">Proveedor</th
              ><th class="px-4 py-3 text-left font-semibold text-foreground">País</th><th
                class="px-4 py-3 text-left font-semibold text-foreground">Contacto</th
              ><th class="px-4 py-3 text-left font-semibold text-foreground">Contactos</th><th
                class="px-4 py-3 text-left font-semibold text-foreground">Estado</th
              ><th class="w-11 px-2 py-3"></th></tr
            ></thead
          ><tbody class="divide-y divide-border"
            >{#each suppliers as supplier (supplier.id_supplier)}<tr
                class="transition-colors hover:bg-surface-muted"
                ><td class="px-4 py-3 font-mono text-xs text-foreground"
                  ><a
                    class="hover:text-primary hover:underline"
                    href={`/suppliers/${supplier.id_supplier}`}>{supplier.code}</a
                  ></td
                ><td class="px-4 py-3"
                  ><a href={`/suppliers/${supplier.id_supplier}`} class="flex items-center gap-3"
                    ><div
                      class="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border bg-surface-muted text-xs font-semibold text-foreground-muted"
                    >
                      {#if supplier.logo_image?.url}<img
                          src={supplier.logo_image.url}
                          alt={supplier.logo_image.alt_text || `Logo de ${supplier.name}`}
                          loading="lazy"
                          referrerpolicy="no-referrer"
                          class="h-full w-full object-cover"
                        />{:else}{supplier.name.slice(0, 2).toUpperCase()}{/if}
                    </div>
                    <div class="min-w-0">
                      <p class="font-medium text-foreground">{supplier.name}</p>
                      {#if supplier.legal_name}<p
                          class="max-w-xs truncate text-xs text-foreground-muted"
                        >
                          {supplier.legal_name}
                        </p>{/if}
                    </div></a
                  ></td
                ><td class="px-4 py-3 text-foreground-muted">{countryName(supplier.country)}</td><td
                  class="px-4 py-3 text-xs text-foreground-muted"
                  ><p>{supplier.phone || '—'}</p>
                  <p>{supplier.email || '—'}</p></td
                ><td class="px-4 py-3"
                  ><a
                    href={`/suppliers/${supplier.id_supplier}/contacts`}
                    class="text-xs text-primary hover:underline"
                    >{supplier.contacts?.length ?? 0} contacto(s)</a
                  ></td
                ><td class="px-4 py-3"
                  ><span
                    class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium {supplier.is_active
                      ? 'bg-success/10 text-success'
                      : 'bg-surface-muted text-foreground-muted'}"
                    ><span class="h-1.5 w-1.5 rounded-full bg-current"></span>{supplier.is_active
                      ? 'Activo'
                      : 'Inactivo'}</span
                  ></td
                ><td class="px-2 py-3 text-center"
                  ><KebabMenu
                    items={menuItems(supplier)}
                    ariaLabel={`Acciones de ${supplier.name}`}
                  /></td
                ></tr
              >{/each}</tbody
          >
        </table>
      </div>{/if}</Card
  >

  {#if totalPages > 1}<div
      class="mt-4 flex items-center justify-between text-xs text-foreground-muted"
    >
      <span>Página {page} de {totalPages}</span>
      <div class="flex gap-2">
        <Button variant="secondary" size="sm" onclick={() => pageTo(page - 1)} disabled={page <= 1}
          >Anterior</Button
        ><Button
          variant="secondary"
          size="sm"
          onclick={() => pageTo(page + 1)}
          disabled={page >= totalPages}>Siguiente</Button
        >
      </div>
    </div>{/if}
</div>
