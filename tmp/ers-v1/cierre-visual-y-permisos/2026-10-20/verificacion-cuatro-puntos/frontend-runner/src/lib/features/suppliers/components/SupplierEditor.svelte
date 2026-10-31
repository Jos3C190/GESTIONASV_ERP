<script lang="ts">
  import { beforeNavigate, goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import EditorSectionNav from '$lib/components/editor/EditorSectionNav.svelte';
  import SingleImageEditor from './SingleImageEditor.svelte';
  import { catalogApi } from '$lib/api/catalog';
  import { suppliersApi } from '$lib/api/suppliers';
  import { HttpError } from '$lib/api/client';
  import type { Country } from '$lib/types/catalog';
  import type {
    Currency,
    PaymentTerms,
    Supplier,
    SupplierGroup,
    SupplierImageDraft,
    SupplierStatus
  } from '$lib/types/supplier';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  interface Props {
    mode: 'create' | 'edit';
    supplierId?: number;
  }

  let { mode, supplierId }: Props = $props();

  type AddressType = 'fiscal' | 'billing' | 'delivery' | 'return' | 'office' | 'other';
  type FormState = {
    code: string;
    name: string;
    legalName: string;
    country: string;
    legacyAddress: string;
    phone: string;
    email: string;
    website: string;
    isActive: boolean;
    supplierGroupId: string;
    supplierStatus: SupplierStatus;
    holdReason: string;
    defaultCurrency: string;
    paymentTermsId: string;
    paymentMethod: string;
    externalReference: string;
    taxType: string;
    taxValue: string;
    taxPrimary: boolean;
    addressType: AddressType;
    addressLine1: string;
    addressCity: string;
    addressState: string;
    addressPostal: string;
    bankName: string;
    bankHolder: string;
    bankAccount: string;
    bankIban: string;
    bankPrimary: boolean;
    image: SupplierImageDraft | null;
  };

  const empty = (): FormState => ({
    code: '',
    name: '',
    legalName: '',
    country: '',
    legacyAddress: '',
    phone: '',
    email: '',
    website: '',
    isActive: true,
    supplierGroupId: '',
    supplierStatus: 'approved',
    holdReason: '',
    defaultCurrency: '',
    paymentTermsId: '',
    paymentMethod: '',
    externalReference: '',
    taxType: '',
    taxValue: '',
    taxPrimary: true,
    addressType: 'fiscal',
    addressLine1: '',
    addressCity: '',
    addressState: '',
    addressPostal: '',
    bankName: '',
    bankHolder: '',
    bankAccount: '',
    bankIban: '',
    bankPrimary: true,
    image: null
  });

  const sections = [
    ['identity', 'Identidad'],
    ['classification', 'Clasificación'],
    ['tax', 'Fiscalidad'],
    ['addresses', 'Direcciones'],
    ['banking', 'Banca protegida'],
    ['image', 'Imagen corporativa'],
    ['review', 'Revisión']
  ] as const;

  let f = $state<FormState>(empty());
  let countries = $state<Country[]>([]);
  let currencies = $state<Currency[]>([]);
  let supplierGroups = $state<SupplierGroup[]>([]);
  let paymentTerms = $state<PaymentTerms[]>([]);
  let existing = $state<Supplier | null>(null);
  let taxId = $state<string | null>(null);
  let addressId = $state<string | null>(null);
  let bankId = $state<string | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
  let initialSnapshot = $state('');
  let pendingTarget = $state<string | null>(null);
  let activeSection = $state('identity');
  let editorHeader: HTMLElement;

  let canManage = $derived(permissions.hasPermission('suppliers:manage'));
  let canEditImages = $derived(permissions.hasPermission('suppliers:images'));
  let canUploadImages = $derived(permissions.hasPermission('media.upload'));
  let canManageTax = $derived(permissions.hasPermission('suppliers:tax_identifiers'));
  let canManageAddresses = $derived(permissions.hasPermission('suppliers:addresses'));
  let canManageBanks = $derived(permissions.hasPermission('suppliers:bank_accounts'));
  let dirty = $derived(!loading && initialSnapshot !== JSON.stringify(f));

  const countryOptions = $derived(
    countries.map((country) => ({
      value: String(country.id_country),
      label: `${country.name} (${country.iso_code_2})`
    }))
  );
  const groupOptions = $derived([
    { value: '', label: 'Sin grupo' },
    ...supplierGroups.map((group) => ({ value: group.id, label: group.name }))
  ]);
  const currencyOptions = $derived([
    { value: '', label: 'Sin moneda predeterminada' },
    ...currencies.map((currency) => ({
      value: currency.code,
      label: `${currency.code} — ${currency.name}`
    }))
  ]);
  const termsOptions = $derived([
    { value: '', label: 'Sin términos de pago' },
    ...paymentTerms.map((terms) => ({
      value: terms.id,
      label: `${terms.name} (${terms.net_days} días)`
    }))
  ]);

  function imageDraft(image: Supplier['logo_image']): SupplierImageDraft | null {
    return image
      ? {
          id: image.id,
          source_type: image.source_type,
          url: image.url,
          media_asset_id: image.media_asset_id ?? null,
          alt_text: image.alt_text ?? null
        }
      : null;
  }

  function fromSupplier(supplier: Supplier) {
    existing = supplier;
    const firstTax = supplier.tax_identifiers?.[0];
    const firstAddress =
      supplier.addresses?.find((item) => item.is_primary) ?? supplier.addresses?.[0];
    const firstBank =
      supplier.bank_accounts?.find((item) => item.is_primary) ?? supplier.bank_accounts?.[0];
    taxId = firstTax?.id ?? null;
    addressId = firstAddress?.id ?? null;
    bankId = firstBank?.id ?? null;
    f = {
      ...empty(),
      code: supplier.code,
      name: supplier.name,
      legalName: supplier.legal_name ?? '',
      country: String(supplier.country),
      legacyAddress: supplier.address ?? '',
      phone: supplier.phone ?? '',
      email: supplier.email ?? '',
      website: supplier.website ?? '',
      isActive: supplier.is_active,
      supplierGroupId: supplier.supplier_group_id ?? '',
      supplierStatus: supplier.supplier_status ?? (supplier.is_active ? 'approved' : 'retired'),
      holdReason: supplier.hold_reason ?? '',
      defaultCurrency: supplier.default_currency_code ?? '',
      paymentTermsId: supplier.payment_terms_id ?? '',
      paymentMethod: supplier.default_payment_method ?? '',
      externalReference: supplier.external_reference ?? '',
      taxType: firstTax?.identifier_type ?? '',
      taxValue: firstTax?.value ?? '',
      taxPrimary: firstTax?.is_primary ?? true,
      addressType: firstAddress?.address_type ?? 'fiscal',
      addressLine1: firstAddress?.line1 ?? '',
      addressCity: firstAddress?.city ?? '',
      addressState: firstAddress?.state_region ?? '',
      addressPostal: firstAddress?.postal_code ?? '',
      bankName: firstBank?.bank_name ?? '',
      bankHolder: firstBank?.account_holder ?? '',
      bankAccount: '',
      bankIban: '',
      bankPrimary: firstBank?.is_primary ?? true,
      image: imageDraft(supplier.logo_image)
    };
  }

  async function load() {
    loading = true;
    error = null;
    try {
      const [countryData, currencyData, groupData, termsData] = await Promise.all([
        catalogApi.listCountries(true),
        suppliersApi.currencies(),
        suppliersApi.groups(),
        suppliersApi.paymentTerms()
      ]);
      countries = countryData;
      currencies = currencyData;
      supplierGroups = groupData;
      paymentTerms = termsData;
      if (mode === 'edit') {
        if (!supplierId) throw new Error('Proveedor no válido.');
        fromSupplier(await suppliersApi.getSupplier(supplierId));
      } else {
        f.country = countries[0] ? String(countries[0].id_country) : '';
      }
      initialSnapshot = JSON.stringify(f);
    } catch (err: unknown) {
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

  function scrollToSection(id: string, behavior: ScrollBehavior = 'smooth') {
    const target = document.getElementById(id);
    const container = target?.closest<HTMLElement>('[data-app-scroll-container]');
    if (!target || !container) return;
    const containerRect = container.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const offset = (editorHeader?.offsetHeight ?? 0) + 16;
    activeSection = id;
    container.scrollTo({
      top: Math.max(container.scrollTop + targetRect.top - containerRect.top - offset, 0),
      behavior
    });
  }

  function validate() {
    const next: Record<string, string> = {};
    if (f.code.trim().length < 2) next.code = 'Ingrese un código válido.';
    if (f.name.trim().length < 2) next.name = 'Ingrese el nombre comercial.';
    if (!f.country) next.country = 'Seleccione el país del proveedor.';
    if (f.email && !/^\S+@\S+\.\S+$/.test(f.email)) next.email = 'Ingrese un correo válido.';
    if (f.supplierStatus === 'on_hold' && !f.holdReason.trim())
      next.holdReason = 'Explique el motivo de bloqueo.';
    if (f.taxType.trim() && !f.taxValue.trim())
      next.taxValue = 'Ingrese el número del identificador.';
    if (f.taxValue.trim() && !f.taxType.trim()) next.taxType = 'Ingrese el tipo de identificador.';
    validation = next;
    if (Object.keys(next).length) {
      scrollToSection(next.code || next.name || next.country ? 'identity' : 'classification');
      return false;
    }
    return true;
  }

  async function save() {
    if (!canManage) {
      error = 'No tiene permiso para administrar proveedores.';
      return;
    }
    if (!validate() || !f.country) return;
    saving = true;
    error = null;
    try {
      const master = {
        code: f.code.trim(),
        name: f.name.trim(),
        country: Number(f.country),
        address: f.legacyAddress.trim() || null,
        phone: f.phone.trim() || null,
        email: f.email.trim() || null,
        website: f.website.trim() || null,
        legal_name: f.legalName.trim() || null,
        supplier_group_id: f.supplierGroupId || null,
        supplier_status: f.supplierStatus,
        hold_reason: f.holdReason.trim() || null,
        default_currency_code: f.defaultCurrency || null,
        payment_terms_id: f.paymentTermsId || null,
        default_payment_method: f.paymentMethod || null,
        external_reference: f.externalReference.trim() || null,
        ...(canEditImages ? { image: f.image } : {})
      };
      const saved =
        mode === 'edit' && supplierId
          ? await suppliersApi.updateSupplier(supplierId, { ...master, is_active: f.isActive })
          : await suppliersApi.createSupplier(master);
      const id = saved.id_supplier;
      if (canManageTax && f.taxType.trim() && f.taxValue.trim()) {
        const taxData = {
          country_id: Number(f.country),
          identifier_type: f.taxType.trim(),
          value: f.taxValue.trim(),
          is_primary: f.taxPrimary,
          is_verified: false
        };
        if (taxId) await suppliersApi.updateTaxIdentifier(id, taxId, taxData);
        else await suppliersApi.addTaxIdentifier(id, taxData);
      }
      if (canManageAddresses && f.addressLine1.trim()) {
        const addressData = {
          address_type: f.addressType,
          line1: f.addressLine1.trim(),
          city: f.addressCity.trim() || null,
          state_region: f.addressState.trim() || null,
          postal_code: f.addressPostal.trim() || null,
          country_id: Number(f.country),
          is_primary: true
        };
        if (addressId) await suppliersApi.updateAddress(id, addressId, addressData);
        else await suppliersApi.addAddress(id, addressData);
      }
      if (canManageBanks && f.bankName.trim() && f.bankHolder.trim() && f.bankAccount.trim()) {
        const bankData = {
          bank_name: f.bankName.trim(),
          account_holder: f.bankHolder.trim(),
          account_number: f.bankAccount.trim(),
          iban: f.bankIban.trim() || null,
          country_id: Number(f.country),
          currency_code: f.defaultCurrency || null,
          is_primary: f.bankPrimary,
          is_verified: false,
          status: 'active' as const
        };
        if (bankId) await suppliersApi.updateBankAccount(id, bankId, bankData);
        else await suppliersApi.addBankAccount(id, bankData);
      }
      initialSnapshot = JSON.stringify(f);
      await goto(`/suppliers/${id}`);
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo guardar el proveedor.';
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
      pendingTarget = navigation.to?.url.pathname ?? '/suppliers';
    }
  });

  onMount(() => void load());
</script>

<svelte:head
  ><title>{mode === 'create' ? 'Nuevo proveedor' : 'Editar proveedor'} — GestionaSV</title
  ></svelte:head
>

<div class="min-h-full bg-background px-4 pb-8 sm:px-6 md:px-8">
  <header
    bind:this={editorHeader}
    class="sticky top-0 z-30 mb-6 flex items-center gap-3 border-b border-border bg-background/95 pb-3 pt-5 backdrop-blur md:pt-8"
  >
    <button
      type="button"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver"
      onclick={() =>
        requestLeave(mode === 'edit' && supplierId ? `/suppliers/${supplierId}` : '/suppliers')}
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
        {mode === 'create' ? 'Nuevo proveedor' : 'Editar proveedor'}
      </h1>
      <p class="text-sm text-foreground-muted">
        {mode === 'create'
          ? 'Registra la identidad, fiscalidad y condiciones comerciales.'
          : 'Actualiza la información completa del proveedor.'}
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
          requestLeave(mode === 'edit' && supplierId ? `/suppliers/${supplierId}` : '/suppliers')}
        >Cancelar</Button
      >
      <Button size="sm" onclick={save} disabled={saving || loading || !canManage}
        >{saving ? 'Guardando…' : mode === 'create' ? 'Crear proveedor' : 'Guardar cambios'}</Button
      >
    </div>
  </header>

  {#if pendingTarget}
    <div
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
    </div>
  {/if}
  {#if !canManage && !loading}<div
      class="mb-5 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning"
      role="alert"
    >
      Esta vista está en modo lectura. Se requiere <strong>suppliers:manage</strong> para guardar cambios.
    </div>{/if}
  {#if error}<div
      class="mb-5 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>{/if}

  {#if loading}
    <div class="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
      <div class="h-72 rounded-xl skeleton"></div>
      <div class="h-[620px] rounded-xl skeleton"></div>
    </div>
  {:else}
    <div class="mx-auto grid max-w-[1280px] gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <EditorSectionNav {sections} {activeSection} onselect={scrollToSection} />
      <main class="min-w-0 space-y-6">
        <Card id="identity" class="scroll-mt-24 p-6">
          <h2 class="text-base font-semibold text-foreground">Identidad comercial y legal</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Los datos legales son opcionales y funcionan para proveedores locales e internacionales.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="supplier-code"
              label="Código"
              bind:value={f.code}
              required
              disabled={!canManage}
              error={validation.code}
              placeholder="PROV-001"
            /><FormField
              id="supplier-name"
              label="Nombre comercial"
              bind:value={f.name}
              required
              disabled={!canManage}
              error={validation.name}
            /><FormField
              id="supplier-legal-name"
              label="Razón social legal"
              bind:value={f.legalName}
              disabled={!canManage}
              placeholder="Opcional"
            /><FormField
              id="supplier-external-ref"
              label="Referencia externa"
              bind:value={f.externalReference}
              disabled={!canManage}
              placeholder="Código en otro ERP"
            /><FormField
              id="supplier-country"
              label="País"
              bind:value={f.country}
              options={countryOptions}
              required
              disabled={!canManage}
              error={validation.country}
            /><FormField
              id="supplier-phone"
              label="Teléfono"
              bind:value={f.phone}
              disabled={!canManage}
            /><FormField
              id="supplier-email"
              label="Correo electrónico"
              type="email"
              bind:value={f.email}
              disabled={!canManage}
              error={validation.email}
            /><FormField
              id="supplier-website"
              label="Sitio web"
              type="url"
              bind:value={f.website}
              disabled={!canManage}
              placeholder="https://..."
            />
          </div>
        </Card>

        <Card id="classification" class="scroll-mt-24 p-6"
          ><h2 class="text-base font-semibold text-foreground">Clasificación y condiciones</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Organiza el proveedor y define las condiciones predeterminadas de compra.
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField
              id="supplier-group"
              label="Grupo de proveedor"
              bind:value={f.supplierGroupId}
              options={groupOptions}
              disabled={!canManage}
            /><FormField
              id="supplier-currency"
              label="Moneda predeterminada"
              bind:value={f.defaultCurrency}
              options={currencyOptions}
              disabled={!canManage}
            /><FormField
              id="supplier-terms"
              label="Términos de pago"
              bind:value={f.paymentTermsId}
              options={termsOptions}
              disabled={!canManage}
            /><FormField
              id="supplier-method"
              label="Método de pago"
              bind:value={f.paymentMethod}
              options={[
                { value: '', label: 'Sin definir' },
                { value: 'bank_transfer', label: 'Transferencia bancaria' },
                { value: 'cash', label: 'Efectivo' },
                { value: 'card', label: 'Tarjeta' },
                { value: 'check', label: 'Cheque' }
              ]}
              disabled={!canManage}
            /><FormField
              id="supplier-status"
              label="Estado"
              bind:value={f.supplierStatus}
              options={[
                { value: 'pending_review', label: 'Pendiente de revisión' },
                { value: 'approved', label: 'Aprobado' },
                { value: 'on_hold', label: 'En espera' },
                { value: 'suspended', label: 'Suspendido' },
                { value: 'rejected', label: 'Rechazado' },
                { value: 'retired', label: 'Retirado' }
              ]}
              disabled={!canManage}
            /><FormField
              id="supplier-address"
              label="Dirección heredada"
              bind:value={f.legacyAddress}
              disabled={!canManage}
            />
          </div>
          {#if f.supplierStatus === 'on_hold'}<div class="mt-4 max-w-xl">
              <FormField
                id="supplier-hold-reason"
                label="Motivo de bloqueo"
                bind:value={f.holdReason}
                disabled={!canManage}
                error={validation.holdReason}
                placeholder="Explique por qué queda en espera"
              />
            </div>{/if}<label class="mt-5 flex items-center gap-2 text-sm text-foreground-muted"
            ><input
              type="checkbox"
              bind:checked={f.isActive}
              disabled={!canManage}
              class="rounded border-border text-primary"
            /> Proveedor activo en la operación</label
          ></Card
        >

        <Card id="tax" class="scroll-mt-24 p-6"
          ><h2 class="text-base font-semibold text-foreground">Información fiscal internacional</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            El Salvador puede usar NIT/NRC; otros países pueden usar VAT, EIN, RFC u otro tipo
            local. Nunca es obligatorio.
          </p>
          {#if canManageTax}<div class="grid gap-4 sm:grid-cols-[.7fr_1.3fr]">
              <FormField
                id="supplier-tax-type"
                label="Tipo de identificación"
                bind:value={f.taxType}
                disabled={!canManage}
                error={validation.taxType}
                placeholder="NIT, NRC, VAT, EIN…"
              /><FormField
                id="supplier-tax-value"
                label="Número o valor"
                bind:value={f.taxValue}
                disabled={!canManage}
                error={validation.taxValue}
                placeholder="Identificador fiscal"
              />
            </div>
            <label class="mt-4 flex items-center gap-2 text-sm text-foreground-muted"
              ><input
                type="checkbox"
                bind:checked={f.taxPrimary}
                disabled={!canManage}
                class="rounded border-border text-primary"
              /> Identificador principal del país</label
            >{:else if existing}<div class="space-y-2">
              {#each existing.tax_identifiers ?? [] as tax}<div
                  class="rounded-lg border border-border bg-surface-muted/30 px-3 py-2 text-sm text-foreground"
                >
                  <span class="font-medium">{tax.identifier_type}:</span>
                  {tax.value}{tax.is_primary ? ' · Principal' : ''}
                </div>{/each}{#if !existing.tax_identifiers?.length}<p
                  class="text-sm text-foreground-muted"
                >
                  Sin identificadores fiscales registrados.
                </p>{/if}
            </div>{/if}</Card
        >

        <Card id="addresses" class="scroll-mt-24 p-6"
          ><h2 class="text-base font-semibold text-foreground">Direcciones</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            La dirección heredada se conserva; esta dirección estructurada sirve para facturación y
            entregas.
          </p>
          {#if canManageAddresses}<div class="grid gap-4 sm:grid-cols-2">
              <FormField
                id="supplier-address-type"
                label="Tipo de dirección"
                bind:value={f.addressType}
                options={[
                  { value: 'fiscal', label: 'Fiscal' },
                  { value: 'billing', label: 'Facturación' },
                  { value: 'delivery', label: 'Entrega' },
                  { value: 'return', label: 'Devolución' },
                  { value: 'office', label: 'Oficina' },
                  { value: 'other', label: 'Otra' }
                ]}
                disabled={!canManage}
              /><FormField
                id="supplier-address-line1"
                label="Línea principal"
                bind:value={f.addressLine1}
                disabled={!canManage}
                placeholder="Calle, número y referencia"
              /><FormField
                id="supplier-address-city"
                label="Ciudad"
                bind:value={f.addressCity}
                disabled={!canManage}
              /><FormField
                id="supplier-address-state"
                label="Estado / departamento"
                bind:value={f.addressState}
                disabled={!canManage}
              /><FormField
                id="supplier-address-postal"
                label="Código postal"
                bind:value={f.addressPostal}
                disabled={!canManage}
              />
            </div>{:else if existing}<div class="space-y-2">
              {#each existing.addresses ?? [] as address}<div
                  class="rounded-lg border border-border bg-surface-muted/30 px-3 py-2 text-sm text-foreground"
                >
                  <span class="font-medium">{address.address_type}:</span>
                  {address.line1}{address.city ? ` · ${address.city}` : ''}{address.is_primary
                    ? ' · Principal'
                    : ''}
                </div>{/each}{#if !existing.addresses?.length}<p
                  class="text-sm text-foreground-muted"
                >
                  Sin direcciones estructuradas registradas.
                </p>{/if}
            </div>{/if}</Card
        >

        <Card id="banking" class="scroll-mt-24 p-6"
          ><h2 class="text-base font-semibold text-foreground">Cuentas bancarias protegidas</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            La cuenta se cifra al guardar. La API y el detalle solo muestran los últimos cuatro
            dígitos.
          </p>
          {#if canManageBanks}<div class="grid gap-4 sm:grid-cols-2">
              <FormField
                id="supplier-bank-name"
                label="Banco"
                bind:value={f.bankName}
                disabled={!canManage}
              /><FormField
                id="supplier-bank-holder"
                label="Titular"
                bind:value={f.bankHolder}
                disabled={!canManage}
              /><FormField
                id="supplier-bank-account"
                label={bankId ? 'Nueva cuenta (opcional)' : 'Número de cuenta'}
                bind:value={f.bankAccount}
                disabled={!canManage}
                type="password"
              /><FormField
                id="supplier-bank-iban"
                label="IBAN (opcional)"
                bind:value={f.bankIban}
                disabled={!canManage}
                type="password"
              />
            </div>
            <label class="mt-4 flex items-center gap-2 text-sm text-foreground-muted"
              ><input
                type="checkbox"
                bind:checked={f.bankPrimary}
                disabled={!canManage}
                class="rounded border-border text-primary"
              /> Cuenta principal</label
            >{:else}<p
              class="rounded-lg border border-border bg-surface-muted/30 px-3 py-3 text-sm text-foreground-muted"
            >
              Vista restringida. Se requiere <strong>suppliers:bank_accounts</strong> para consultar cuentas
              bancarias.
            </p>{/if}</Card
        >

        <Card id="image" class="scroll-mt-24 p-6"
          ><h2 class="mb-1 text-base font-semibold text-foreground">Imagen corporativa</h2>
          <p class="mb-5 text-sm text-foreground-muted">
            Logo principal del proveedor. Las imágenes externas deben usar HTTPS.
          </p>
          <SingleImageEditor
            bind:image={f.image}
            companyId={company.id ?? ''}
            purpose="supplier_logo"
            label="Logo del proveedor"
            emptyLabel="Añade un logo o imagen principal."
            altFallback={`Logo de ${f.name || 'proveedor'}`}
            editable={canEditImages}
            canUpload={canUploadImages}
          /></Card
        >

        <Card id="review" class="scroll-mt-24 p-6"
          ><h2 class="text-base font-semibold text-foreground">Revisión</h2>
          <p class="mb-4 text-sm text-foreground-muted">Verifica estos datos antes de guardar.</p>
          <div class="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <span class="text-foreground-muted">Nombre comercial</span>
              <p class="font-medium text-foreground">{f.name || '—'}</p>
            </div>
            <div>
              <span class="text-foreground-muted">País</span>
              <p class="font-medium text-foreground">
                {countryOptions.find((item) => item.value === f.country)?.label ?? '—'}
              </p>
            </div>
            <div>
              <span class="text-foreground-muted">Estado</span>
              <p class="font-medium text-foreground">{f.supplierStatus}</p>
            </div>
            <div>
              <span class="text-foreground-muted">Moneda</span>
              <p class="font-medium text-foreground">{f.defaultCurrency || '—'}</p>
            </div>
          </div></Card
        >
      </main>
    </div>
  {/if}
</div>
