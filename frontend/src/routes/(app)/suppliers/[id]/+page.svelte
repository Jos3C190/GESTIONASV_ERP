<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import { suppliersApi } from '$lib/api/suppliers';
  import { catalogApi } from '$lib/api/catalog';
  import { HttpError } from '$lib/api/client';
  import type { Country } from '$lib/types/catalog';
  import type { Supplier } from '$lib/types/supplier';
  import { permissions } from '$lib/stores/permissions.svelte';

  let supplier = $state<Supplier | null>(null);
  let countries = $state<Country[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let supplierId = $derived(Number(page.params.id));

  const statusLabels: Record<string, string> = {
    pending_review: 'Pendiente de revisión',
    approved: 'Aprobado',
    on_hold: 'En espera',
    suspended: 'Suspendido',
    rejected: 'Rechazado',
    retired: 'Retirado'
  };

  let canManage = $derived(permissions.hasPermission('suppliers:manage'));
  let canViewBanks = $derived(permissions.hasPermission('suppliers:bank_accounts'));

  async function load() {
    loading = true;
    error = null;
    try {
      const [detail, countryData] = await Promise.all([
        suppliersApi.getSupplier(supplierId),
        catalogApi.listCountries(true)
      ]);
      supplier = detail;
      countries = countryData;
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo cargar el proveedor.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (supplierId > 0) void load();
  });

  function countryName(id: number | undefined) {
    const country = countries.find((item) => item.id_country === id);
    return country ? `${country.name} (${country.iso_code_2})` : '—';
  }

  function statusVariant(status: string | undefined): 'success' | 'warning' | 'danger' | 'neutral' {
    if (status === 'approved') return 'success';
    if (status === 'on_hold' || status === 'pending_review') return 'warning';
    if (status === 'suspended' || status === 'rejected') return 'danger';
    return 'neutral';
  }
</script>

<svelte:head
  ><title>{supplier ? `${supplier.name} — Proveedores` : 'Detalle de proveedor — GestionaSV'}</title
  ></svelte:head
>

<div class="min-h-full bg-background px-4 pb-8 sm:px-6 md:px-8">
  <header class="mb-6 flex items-center gap-3 border-b border-border pb-4 pt-5 md:pt-8">
    <button
      type="button"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver a proveedores"
      onclick={() => goto('/suppliers')}
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
      <h1 class="text-xl font-bold text-foreground">Detalle del proveedor</h1>
      <p class="text-sm text-foreground-muted">
        Información comercial, fiscal y operativa completa.
      </p>
    </div>
    {#if supplier}<div class="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onclick={() => goto(`/suppliers/${supplierId}/contacts`)}>Contactos</Button
        >{#if canManage}<Button size="sm" onclick={() => goto(`/suppliers/${supplierId}/edit`)}
            >Editar</Button
          >{/if}
      </div>{/if}
  </header>

  {#if loading}
    <div class="space-y-5">
      <div class="h-36 rounded-xl skeleton"></div>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="h-28 rounded-xl skeleton"></div>
        <div class="h-28 rounded-xl skeleton"></div>
        <div class="h-28 rounded-xl skeleton"></div>
        <div class="h-28 rounded-xl skeleton"></div>
      </div>
      <div class="h-80 rounded-xl skeleton"></div>
    </div>
  {:else if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if supplier}
    <div class="space-y-5">
      <Card class="p-5 sm:p-6"
        ><div class="flex flex-col gap-5 sm:flex-row sm:items-center">
          <div
            class="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-border bg-surface-muted text-xl font-semibold text-foreground-muted"
          >
            {#if supplier.logo_image?.url}<img
                src={supplier.logo_image.url}
                alt={supplier.logo_image.alt_text || `Logo de ${supplier.name}`}
                loading="lazy"
                referrerpolicy="no-referrer"
                class="h-full w-full object-cover"
              />{:else}{supplier.name.slice(0, 2).toUpperCase()}{/if}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-3">
              <h2 class="text-xl font-bold text-foreground">{supplier.name}</h2>
              <Badge variant={statusVariant(supplier.supplier_status)}
                >{statusLabels[supplier.supplier_status ?? 'approved'] ??
                  supplier.supplier_status}</Badge
              >
            </div>
            <p class="mt-1 text-sm text-foreground-muted">
              {supplier.legal_name || 'Sin razón social legal registrada'}
            </p>
            <div class="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-foreground-muted">
              <span class="font-mono">{supplier.code}</span><span
                >{countryName(supplier.country)}</span
              >{#if supplier.external_reference}<span>Ref. {supplier.external_reference}</span>{/if}
            </div>
          </div>
          <div class="text-left sm:text-right">
            <p class="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
              Operación
            </p>
            <p
              class="mt-1 text-lg font-bold {supplier.is_active
                ? 'text-success'
                : 'text-foreground-muted'}"
            >
              {supplier.is_active ? 'Activo' : 'Inactivo'}
            </p>
          </div>
        </div></Card
      >

      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card class="p-4"
          ><p class="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
            Contactos
          </p>
          <p class="mt-2 font-mono text-2xl font-bold text-foreground">
            {supplier.contacts?.length ?? 0}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">Personas registradas</p></Card
        ><Card class="p-4"
          ><p class="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
            Identificadores fiscales
          </p>
          <p class="mt-2 font-mono text-2xl font-bold text-foreground">
            {supplier.tax_identifiers?.length ?? 0}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">Opcionales por país</p></Card
        ><Card class="p-4"
          ><p class="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
            Moneda
          </p>
          <p class="mt-2 font-mono text-2xl font-bold text-foreground">
            {supplier.default_currency_code || '—'}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">Predeterminada</p></Card
        ><Card class="p-4"
          ><p class="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
            Términos
          </p>
          <p class="mt-2 text-lg font-bold text-foreground">
            {supplier.payment_terms_id ? 'Configurados' : 'Sin definir'}
          </p>
          <p class="mt-1 text-xs text-foreground-muted">Condiciones de pago</p></Card
        >
      </div>

      <div class="grid gap-5 xl:grid-cols-2">
        <Card class="p-5"
          ><div class="mb-4 flex items-center justify-between">
            <div>
              <h2 class="text-base font-semibold text-foreground">Identidad y clasificación</h2>
              <p class="text-sm text-foreground-muted">
                Datos comerciales y condiciones generales.
              </p>
            </div>
          </div>
          <dl class="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-xs text-foreground-muted">Razón social legal</dt>
              <dd class="mt-1 text-foreground">{supplier.legal_name || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Referencia externa</dt>
              <dd class="mt-1 text-foreground">{supplier.external_reference || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Método de pago</dt>
              <dd class="mt-1 text-foreground">{supplier.default_payment_method || '—'}</dd>
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Dirección heredada</dt>
              <dd class="mt-1 text-foreground">{supplier.address || '—'}</dd>
            </div>
          </dl></Card
        >
        <Card class="p-5"
          ><h2 class="text-base font-semibold text-foreground">Identificación fiscal</h2>
          <p class="mb-4 text-sm text-foreground-muted">
            Registros genéricos, sin asumir formatos locales.
          </p>
          {#if supplier.tax_identifiers?.length}<div class="space-y-2">
              {#each supplier.tax_identifiers as tax}<div
                  class="flex items-center justify-between rounded-lg border border-border bg-surface-muted/30 px-3 py-2 text-sm"
                >
                  <span
                    ><span class="font-medium text-foreground">{tax.identifier_type}</span><span
                      class="ml-2 text-foreground-muted">{tax.value}</span
                    ></span
                  >{#if tax.is_primary}<span
                      class="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary"
                      >Principal</span
                    >{/if}
                </div>{/each}
            </div>{:else}<div
              class="rounded-lg border border-dashed border-border px-3 py-5 text-center text-sm text-foreground-muted"
            >
              No hay identificadores fiscales registrados.
            </div>{/if}</Card
        >
        <Card class="p-5"
          ><h2 class="text-base font-semibold text-foreground">Direcciones</h2>
          <p class="mb-4 text-sm text-foreground-muted">Direcciones estructuradas del proveedor.</p>
          {#if supplier.addresses?.length}<div class="space-y-2">
              {#each supplier.addresses as address}<div
                  class="rounded-lg border border-border bg-surface-muted/30 px-3 py-2 text-sm"
                >
                  <div class="flex items-center justify-between">
                    <span class="font-medium capitalize text-foreground"
                      >{address.address_type}</span
                    >{#if address.is_primary}<span class="text-[11px] text-primary">Principal</span
                      >{/if}
                  </div>
                  <p class="mt-1 text-foreground-muted">
                    {address.line1}{address.city ? ` · ${address.city}` : ''}{address.state_region
                      ? ` · ${address.state_region}`
                      : ''}
                  </p>
                </div>{/each}
            </div>{:else}<div
              class="rounded-lg border border-dashed border-border px-3 py-5 text-center text-sm text-foreground-muted"
            >
              No hay direcciones estructuradas registradas.
            </div>{/if}</Card
        >
        <Card class="p-5"
          ><h2 class="text-base font-semibold text-foreground">Cuentas bancarias</h2>
          <p class="mb-4 text-sm text-foreground-muted">Información protegida y enmascarada.</p>
          {#if canViewBanks}{#if supplier.bank_accounts?.length}<div class="space-y-2">
                {#each supplier.bank_accounts as account}<div
                    class="flex items-center justify-between rounded-lg border border-border bg-surface-muted/30 px-3 py-2 text-sm"
                  >
                    <div>
                      <p class="font-medium text-foreground">{account.bank_name}</p>
                      <p class="text-xs text-foreground-muted">
                        •••• {account.last_four} · {account.currency_code || 'Moneda no definida'}
                      </p>
                    </div>
                    {#if account.is_primary}<span class="text-[11px] text-primary">Principal</span
                      >{/if}
                  </div>{/each}
              </div>{:else}<div
                class="rounded-lg border border-dashed border-border px-3 py-5 text-center text-sm text-foreground-muted"
              >
                No hay cuentas bancarias registradas.
              </div>{/if}{:else}<div
              class="rounded-lg border border-border bg-surface-muted/30 px-3 py-5 text-center text-sm text-foreground-muted"
            >
              Información restringida por permisos.
            </div>{/if}</Card
        >
      </div>

      <Card class="p-5"
        ><div class="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold text-foreground">Contactos del proveedor</h2>
            <p class="text-sm text-foreground-muted">
              Personas autorizadas para la relación comercial.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onclick={() => goto(`/suppliers/${supplierId}/contacts`)}>Gestionar contactos</Button
          >
        </div>
        {#if supplier.contacts?.length}<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {#each supplier.contacts as contact}<div
                class="flex items-center gap-3 rounded-lg border border-border bg-surface-muted/30 p-3"
              >
                <div
                  class="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-surface-muted text-xs font-semibold text-foreground-muted"
                >
                  {#if contact.avatar_image?.url}<img
                      src={contact.avatar_image.url}
                      alt={contact.avatar_image.alt_text || contact.full_name}
                      loading="lazy"
                      referrerpolicy="no-referrer"
                      class="h-full w-full object-cover"
                    />{:else}{contact.full_name.slice(0, 1).toUpperCase()}{/if}
                </div>
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium text-foreground">{contact.full_name}</p>
                  <p class="truncate text-xs text-foreground-muted">
                    {contact.email || contact.phone || 'Sin datos de contacto'}
                  </p>
                </div>
              </div>{/each}
          </div>{:else}<div
            class="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-foreground-muted"
          >
            Aún no hay contactos registrados.
          </div>{/if}</Card
      >
    </div>
  {/if}
</div>
