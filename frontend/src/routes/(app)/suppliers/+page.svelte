<script lang="ts">
  import { untrack } from 'svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { api } from '$lib/api/client';
  import { suppliersApi } from '$lib/api/suppliers';
  import { catalogApi } from '$lib/api/catalog';
  import type { Currency, PaymentTerms, Supplier, SupplierContact, SupplierGroup, SupplierImageDraft, SupplierStatus } from '$lib/types/supplier';
  import SingleImageEditor from '$lib/features/suppliers/components/SingleImageEditor.svelte';
  import type { Country } from '$lib/types/catalog';
  import { company } from '$lib/stores/company.svelte';
  import { search as globalSearch } from '$lib/stores/search.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  // Svelte 5 Runes State
  let suppliers = $state<Supplier[]>([]);
  let countries = $state<Country[]>([]);
  let currencies = $state<Currency[]>([]);
  let supplierGroups = $state<SupplierGroup[]>([]);
  let paymentTerms = $state<PaymentTerms[]>([]);
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
  let editingSupplierDetail = $state<Supplier | null>(null);
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
  let formImage = $state<SupplierImageDraft | null>(null);
  let formLegalName = $state<string>('');
  let formSupplierGroupId = $state<string>('');
  let formSupplierStatus = $state<SupplierStatus>('approved');
  let formHoldReason = $state<string>('');
  let formDefaultCurrency = $state<string>('');
  let formPaymentTermsId = $state<string>('');
  let formPaymentMethod = $state<string>('');
  let formExternalReference = $state<string>('');
  let formTaxType = $state<string>('');
  let formTaxValue = $state<string>('');
  let formTaxPrimary = $state<boolean>(true);
  let formTaxId = $state<string | null>(null);
  let formAddressType = $state<'fiscal' | 'billing' | 'delivery' | 'return' | 'office' | 'other'>('fiscal');
  let formAddressLine1 = $state<string>('');
  let formAddressCity = $state<string>('');
  let formAddressState = $state<string>('');
  let formAddressPostal = $state<string>('');
  let formAddressId = $state<string | null>(null);
  let formBankName = $state<string>('');
  let formBankHolder = $state<string>('');
  let formBankAccount = $state<string>('');
  let formBankIban = $state<string>('');
  let formBankPrimary = $state<boolean>(true);
  let formBankId = $state<string | null>(null);

  // Contacts Modal State
  let showContactModal = $state<boolean>(false);
  let selectedSupplier = $state<Supplier | null>(null);
  let contactName = $state<string>('');
  let contactPhone = $state<string>('');
  let contactEmail = $state<string>('');
  let contactImage = $state<SupplierImageDraft | null>(null);
  let editingContactId = $state<number | null>(null);
  let savingContact = $state<boolean>(false);

  let canEditImages = $derived(permissions.hasPermission('suppliers:images'));
  let canUploadImages = $derived(permissions.hasPermission('media.upload'));
  let canManageTax = $derived(permissions.hasPermission('suppliers:tax_identifiers'));
  let canManageAddresses = $derived(permissions.hasPermission('suppliers:addresses'));
  let canManageBanks = $derived(permissions.hasPermission('suppliers:bank_accounts'));

  let dataGeneration = 0;

  async function loadData() {
    const generation = ++dataGeneration;
    loading = true;
    errorMsg = null;
    try {
      const [cRes, sRes, stats, currencyRes, groupRes, paymentRes] = await Promise.all([
        catalogApi.listCountries(true),
        suppliersApi.listSuppliers({
          country_id: selectedCountry,
          search: globalSearch.query.trim() || undefined,
          active_only: false,
          page: untrack(() => page),
          size: 10
        }),
        suppliersApi.stats(),
        suppliersApi.currencies(),
        suppliersApi.groups(),
        suppliersApi.paymentTerms()
      ]);

      if (generation !== dataGeneration) return;

      countries = cRes;
      currencies = currencyRes;
      supplierGroups = groupRes;
      paymentTerms = paymentRes;
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
    editingSupplierDetail = null;
    formCode = '';
    formName = '';
    formCountry = countries[0]?.id_country;
    formAddress = '';
    formPhone = '';
    formEmail = '';
    formWebsite = '';
    formIsActive = true;
    formImage = null;
    formLegalName = '';
    formSupplierGroupId = '';
    formSupplierStatus = 'approved';
    formHoldReason = '';
    formDefaultCurrency = '';
    formPaymentTermsId = '';
    formPaymentMethod = '';
    formExternalReference = '';
    formTaxType = '';
    formTaxValue = '';
    formTaxPrimary = true;
    formTaxId = null;
    formAddressType = 'fiscal';
    formAddressLine1 = '';
    formAddressCity = '';
    formAddressState = '';
    formAddressPostal = '';
    formAddressId = null;
    formBankName = '';
    formBankHolder = '';
    formBankAccount = '';
    formBankIban = '';
    formBankPrimary = true;
    formBankId = null;
    showSupplierModal = true;
  }

  async function openEditSupplierModal(sup: Supplier) {
    const detail = await suppliersApi.getSupplier(sup.id_supplier);
    editingSupplierDetail = detail;
    isEditingSupplier = true;
    editingSupplierId = sup.id_supplier;
    formCode = detail.code;
    formName = detail.name;
    formCountry = detail.country;
    formAddress = detail.address ?? '';
    formPhone = detail.phone ?? '';
    formEmail = detail.email ?? '';
    formWebsite = detail.website ?? '';
    formIsActive = detail.is_active;
    formLegalName = detail.legal_name ?? '';
    formSupplierGroupId = detail.supplier_group_id ?? '';
    formSupplierStatus = detail.supplier_status ?? 'approved';
    formHoldReason = detail.hold_reason ?? '';
    formDefaultCurrency = detail.default_currency_code ?? '';
    formPaymentTermsId = detail.payment_terms_id ?? '';
    formPaymentMethod = detail.default_payment_method ?? '';
    formExternalReference = detail.external_reference ?? '';
    const firstTax = detail.tax_identifiers?.[0];
    formTaxId = firstTax?.id ?? null;
    formTaxType = firstTax?.identifier_type ?? '';
    formTaxValue = firstTax?.value ?? '';
    const firstAddress = detail.addresses?.find((address) => address.is_primary) ?? detail.addresses?.[0];
    formAddressId = firstAddress?.id ?? null;
    formAddressType = firstAddress?.address_type ?? 'fiscal';
    formAddressLine1 = firstAddress?.line1 ?? '';
    formAddressCity = firstAddress?.city ?? '';
    formAddressState = firstAddress?.state_region ?? '';
    formAddressPostal = firstAddress?.postal_code ?? '';
    const firstBank = detail.bank_accounts?.find((account) => account.is_primary) ?? detail.bank_accounts?.[0];
    formBankId = firstBank?.id ?? null;
    formBankName = firstBank?.bank_name ?? '';
    formBankHolder = firstBank?.account_holder ?? '';
    formBankAccount = '';
    formBankIban = '';
    formBankPrimary = firstBank?.is_primary ?? true;
    formImage = detail.logo_image
      ? {
          id: detail.logo_image.id,
          source_type: detail.logo_image.source_type,
          url: detail.logo_image.url,
          media_asset_id: detail.logo_image.media_asset_id ?? null,
          alt_text: detail.logo_image.alt_text ?? detail.name
        }
      : null;
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
          legal_name: formLegalName || null,
          supplier_group_id: formSupplierGroupId || null,
          supplier_status: formSupplierStatus,
          hold_reason: formHoldReason || null,
          default_currency_code: formDefaultCurrency || null,
          payment_terms_id: formPaymentTermsId || null,
          default_payment_method: formPaymentMethod || null,
          external_reference: formExternalReference || null,
          is_active: formIsActive,
          ...(canEditImages ? { image: formImage } : {})
        });
        if (canManageTax && formTaxType.trim() && formTaxValue.trim()) {
          const taxData = { country_id: formCountry, identifier_type: formTaxType, value: formTaxValue, is_primary: formTaxPrimary, is_verified: false };
          if (formTaxId) await suppliersApi.updateTaxIdentifier(editingSupplierId, formTaxId, taxData);
          else await suppliersApi.addTaxIdentifier(editingSupplierId, taxData);
        }
        if (canManageAddresses && formAddressLine1.trim()) {
          const addressData = { address_type: formAddressType, line1: formAddressLine1, city: formAddressCity || null, state_region: formAddressState || null, postal_code: formAddressPostal || null, country_id: formCountry, is_primary: true };
          if (formAddressId) await suppliersApi.updateAddress(editingSupplierId, formAddressId, addressData);
          else await suppliersApi.addAddress(editingSupplierId, addressData);
        }
        if (canManageBanks && formBankName.trim() && formBankHolder.trim() && formBankAccount.trim()) {
          const bankData = { bank_name: formBankName, account_holder: formBankHolder, account_number: formBankAccount, iban: formBankIban || null, country_id: formCountry, currency_code: formDefaultCurrency || null, is_primary: formBankPrimary, is_verified: false, status: 'active' as const };
          if (formBankId) await suppliersApi.updateBankAccount(editingSupplierId, formBankId, bankData);
          else await suppliersApi.addBankAccount(editingSupplierId, bankData);
        }
        successMsg = 'Proveedor actualizado exitosamente.';
      } else {
        const createdSupplier = await suppliersApi.createSupplier({
          code: formCode,
          name: formName,
          country: formCountry,
          address: formAddress,
          phone: formPhone,
          email: formEmail,
          website: formWebsite,
          legal_name: formLegalName || undefined,
          supplier_group_id: formSupplierGroupId || undefined,
          supplier_status: formSupplierStatus,
          hold_reason: formHoldReason || undefined,
          default_currency_code: formDefaultCurrency || undefined,
          payment_terms_id: formPaymentTermsId || undefined,
          default_payment_method: formPaymentMethod || undefined,
          external_reference: formExternalReference || undefined,
          ...(canEditImages ? { image: formImage } : {})
        });
        if (canManageTax && formTaxType.trim() && formTaxValue.trim()) {
          await suppliersApi.addTaxIdentifier(createdSupplier.id_supplier, { country_id: formCountry, identifier_type: formTaxType, value: formTaxValue, is_primary: formTaxPrimary, is_verified: false });
        }
        if (canManageAddresses && formAddressLine1.trim()) {
          await suppliersApi.addAddress(createdSupplier.id_supplier, { address_type: formAddressType, line1: formAddressLine1, city: formAddressCity || null, state_region: formAddressState || null, postal_code: formAddressPostal || null, country_id: formCountry, is_primary: true });
        }
        if (canManageBanks && formBankName.trim() && formBankHolder.trim() && formBankAccount.trim()) {
          await suppliersApi.addBankAccount(createdSupplier.id_supplier, { bank_name: formBankName, account_holder: formBankHolder, account_number: formBankAccount, iban: formBankIban || null, country_id: formCountry, currency_code: formDefaultCurrency || null, is_primary: formBankPrimary, is_verified: false, status: 'active' });
        }
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
    editingContactId = null;
    contactName = '';
    contactPhone = '';
    contactEmail = '';
    contactImage = null;
    showContactModal = true;
  }

  function openEditContact(contact: SupplierContact) {
    editingContactId = contact.id_supplier_contact;
    contactName = contact.full_name;
    contactPhone = contact.phone ?? '';
    contactEmail = contact.email ?? '';
    contactImage = contact.avatar_image
      ? {
          id: contact.avatar_image.id,
          source_type: contact.avatar_image.source_type,
          url: contact.avatar_image.url,
          media_asset_id: contact.avatar_image.media_asset_id ?? null,
          alt_text: contact.avatar_image.alt_text ?? contact.full_name
        }
      : null;
  }

  function resetContactForm() {
    editingContactId = null;
    contactName = '';
    contactPhone = '';
    contactEmail = '';
    contactImage = null;
  }

  async function handleAddContact(e: SubmitEvent) {
    e.preventDefault();
    if (!selectedSupplier) return;
    savingContact = true;
    try {
      if (editingContactId) {
        await suppliersApi.updateContact(editingContactId, {
          full_name: contactName,
          phone: contactPhone,
          email: contactEmail,
          ...(canEditImages ? { image: contactImage } : {})
        });
      } else {
        await suppliersApi.addContact(selectedSupplier.id_supplier, {
          full_name: contactName,
          phone: contactPhone,
          email: contactEmail,
          ...(canEditImages ? { image: contactImage } : {})
        });
      }
      resetContactForm();
      const updated = await suppliersApi.getSupplier(selectedSupplier.id_supplier);
      selectedSupplier = updated;
      await loadData();
    } catch (err: unknown) {
      errorMsg = err instanceof Error ? err.message : 'Error al agregar contacto';
    } finally {
      savingContact = false;
    }
  }

  async function refreshSelectedSupplier() {
    if (!selectedSupplier) return;
    selectedSupplier = await suppliersApi.getSupplier(selectedSupplier.id_supplier);
    await loadData();
  }

  async function toggleContact(contact: SupplierContact) {
    if (!contact.is_active) {
      try {
        await suppliersApi.updateContact(contact.id_supplier_contact, { is_active: true });
        await refreshSelectedSupplier();
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'No se pudo activar el contacto.';
      }
      return;
    }
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar contacto',
      description:
        'El contacto dejará de estar disponible para nuevas gestiones con el proveedor. Su historial se conservará.',
      resourceName: contact.full_name,
      confirmLabel: 'Desactivar contacto',
      execute: async () => {
        await suppliersApi.deactivateContact(contact.id_supplier_contact);
        await refreshSelectedSupplier();
      }
    });
  }

  function handleDeleteContact(contactId: number, name: string) {
    if (!selectedSupplier) return;
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar contacto',
      description: `¿Está seguro de eliminar el contacto "${name}"?`,
      resourceName: name,
      confirmLabel: 'Eliminar contacto',
      requireReason: true,
      execute: async (reason) => {
        if (!reason) throw new Error('Indique el motivo de eliminación.');
        await api.lifecycle.delete('supplier_contacts', String(contactId), reason);
        await refreshSelectedSupplier();
      }
    });
  }

  function contactMenuItems(contact: SupplierContact): KebabItem[] {
    const items: KebabItem[] = [];
    if (permissions.hasPermission('suppliers:manage')) {
      items.push({
        id: 'edit',
        label: 'Editar',
        icon: 'edit',
        onClick: () => openEditContact(contact)
      });
      items.push({
        id: 'status',
        label: contact.is_active ? 'Desactivar' : 'Activar',
        icon: 'power',
        variant: contact.is_active ? 'danger' : 'default',
        onClick: () => void toggleContact(contact)
      });
    }
    if (permissions.hasPermission('suppliers:delete')) {
      items.push({
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => handleDeleteContact(contact.id_supplier_contact, contact.full_name)
      });
    }
    return items;
  }

  function deleteSupplier(sup: Supplier) {
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar proveedor',
      description:
        'El proveedor desaparecerá de la operación diaria y quedará disponible en la Papelera. La eliminación se bloqueará mientras conserve contactos u otras dependencias.',
      resourceName: sup.name,
      confirmLabel: 'Eliminar proveedor',
      requireReason: true,
      execute: async (reason) => {
        if (!reason) throw new Error('Indique el motivo de eliminación.');
        await api.lifecycle.delete('suppliers', String(sup.id_supplier), reason);
        if (selectedSupplier?.id_supplier === sup.id_supplier) {
          selectedSupplier = null;
          showContactModal = false;
        }
        successMsg = 'Proveedor enviado a la Papelera.';
        await loadData();
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
    if (permissions.hasPermission('suppliers:delete')) {
      items.push({
        id: 'delete',
        label: 'Eliminar',
        icon: 'delete',
        variant: 'danger',
        onClick: () => deleteSupplier(sup)
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
                  <div class="flex items-center gap-3">
                    <div class="h-9 w-9 flex-none overflow-hidden rounded-lg border border-border bg-surface-muted">
                      {#if sup.logo_image?.url}
                        <img
                          src={sup.logo_image.url}
                          alt={sup.logo_image.alt_text || `Logo de ${sup.name}`}
                          loading="lazy"
                          referrerpolicy="no-referrer"
                          class="h-full w-full object-cover"
                        />
                      {:else}
                        <div class="flex h-full items-center justify-center text-xs font-semibold text-foreground-muted">
                          {sup.name.slice(0, 2).toUpperCase()}
                        </div>
                      {/if}
                    </div>
                    <div class="min-w-0">
                      <div class="font-medium text-foreground">{sup.name}</div>
                      {#if sup.address}
                        <div class="max-w-xs truncate text-xs text-foreground-muted">{sup.address}</div>
                      {/if}
                    </div>
                  </div>
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

        <div class="border-t border-border pt-4 space-y-3">
          <div>
            <h4 class="text-sm font-semibold text-foreground">Identidad legal y clasificación</h4>
            <p class="text-xs text-foreground-muted">Los identificadores fiscales se registran por país y tipo; ninguno es obligatorio.</p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label for="sup-legal-name" class="block text-xs font-medium text-foreground-muted mb-1">Razón social legal</label>
              <input id="sup-legal-name" bind:value={formLegalName} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" placeholder="Opcional para proveedores internacionales" />
            </div>
            <div>
              <label for="sup-external-reference" class="block text-xs font-medium text-foreground-muted mb-1">Referencia externa</label>
              <input id="sup-external-reference" bind:value={formExternalReference} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" placeholder="Código en otro ERP" />
            </div>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label for="sup-group" class="block text-xs font-medium text-foreground-muted mb-1">Grupo de proveedor</label>
              <select id="sup-group" bind:value={formSupplierGroupId} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
                <option value="">Sin grupo</option>
                {#each supplierGroups as group}<option value={group.id}>{group.name}</option>{/each}
              </select>
            </div>
            <div>
              <label for="sup-currency" class="block text-xs font-medium text-foreground-muted mb-1">Moneda predeterminada</label>
              <select id="sup-currency" bind:value={formDefaultCurrency} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
                <option value="">Sin definir</option>
                {#each currencies as currency}<option value={currency.code}>{currency.code} — {currency.name}</option>{/each}
              </select>
            </div>
            <div>
              <label for="sup-terms" class="block text-xs font-medium text-foreground-muted mb-1">Términos de pago</label>
              <select id="sup-terms" bind:value={formPaymentTermsId} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
                <option value="">Sin definir</option>
                {#each paymentTerms as terms}<option value={terms.id}>{terms.name} ({terms.net_days} días)</option>{/each}
              </select>
            </div>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label for="sup-payment-method" class="block text-xs font-medium text-foreground-muted mb-1">Método de pago predeterminado</label>
              <select id="sup-payment-method" bind:value={formPaymentMethod} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
                <option value="">Sin definir</option><option value="bank_transfer">Transferencia bancaria</option><option value="cash">Efectivo</option><option value="card">Tarjeta</option><option value="check">Cheque</option>
              </select>
            </div>
            <div>
              <label for="sup-status" class="block text-xs font-medium text-foreground-muted mb-1">Estado del proveedor</label>
              <select id="sup-status" bind:value={formSupplierStatus} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none">
                <option value="pending_review">Pendiente de revisión</option><option value="approved">Aprobado</option><option value="on_hold">En espera</option><option value="suspended">Suspendido</option><option value="rejected">Rechazado</option><option value="retired">Retirado</option>
              </select>
            </div>
          </div>
          {#if formSupplierStatus === 'on_hold'}
            <div>
              <label for="sup-hold-reason" class="block text-xs font-medium text-foreground-muted mb-1">Motivo de bloqueo</label>
              <textarea id="sup-hold-reason" rows="2" bind:value={formHoldReason} class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none" placeholder="Explique por qué queda en espera"></textarea>
            </div>
          {/if}
        </div>

        {#if canManageTax}
          <div class="border-t border-border pt-4 space-y-3">
            <div><h4 class="text-sm font-semibold text-foreground">Información fiscal internacional</h4><p class="text-xs text-foreground-muted">Para El Salvador puede usar NIT/NRC; para otros países use VAT, EIN, RFC u otro tipo local.</p></div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <input id="sup-tax-type" bind:value={formTaxType} aria-label="Tipo de identificación fiscal" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="NIT, VAT, EIN..." />
              <input id="sup-tax-value" bind:value={formTaxValue} aria-label="Número de identificación fiscal" class="md:col-span-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Identificador fiscal opcional" />
            </div>
            <label class="flex items-center gap-2 text-xs text-foreground-muted"><input type="checkbox" bind:checked={formTaxPrimary} class="rounded border-border text-primary" /> Identificador principal del país</label>
          </div>
        {:else if isEditingSupplier}
          <div class="border-t border-border pt-4 space-y-2">
            <div><h4 class="text-sm font-semibold text-foreground">Información fiscal internacional</h4><p class="text-xs text-foreground-muted">Solo lectura. Se requiere suppliers:tax_identifiers para administrar estos registros.</p></div>
            {#if editingSupplierDetail?.tax_identifiers?.length}
              {#each editingSupplierDetail.tax_identifiers as tax}
                <div class="rounded-lg border border-border bg-surface-muted/30 px-3 py-2 text-sm text-foreground"><span class="font-medium">{tax.identifier_type}:</span> {tax.value}{tax.is_primary ? ' · Principal' : ''}</div>
              {/each}
            {:else}<p class="text-xs text-foreground-muted">Sin identificadores fiscales registrados.</p>{/if}
          </div>
        {/if}

        {#if canManageAddresses}
          <div class="border-t border-border pt-4 space-y-3">
            <div><h4 class="text-sm font-semibold text-foreground">Dirección principal</h4><p class="text-xs text-foreground-muted">La dirección heredada se conserva; este registro estructurado permite facturación y entrega.</p></div>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              <select bind:value={formAddressType} aria-label="Tipo de dirección" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"><option value="fiscal">Fiscal</option><option value="billing">Facturación</option><option value="delivery">Entrega</option><option value="office">Oficina</option><option value="other">Otra</option></select>
              <input bind:value={formAddressLine1} aria-label="Línea de dirección" class="md:col-span-3 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Línea principal de dirección" />
              <input bind:value={formAddressCity} aria-label="Ciudad" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Ciudad" />
              <input bind:value={formAddressState} aria-label="Estado o departamento" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Estado / departamento" />
              <input bind:value={formAddressPostal} aria-label="Código postal" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Código postal" />
            </div>
          </div>
        {:else if isEditingSupplier}
          <div class="border-t border-border pt-4 space-y-2">
            <div><h4 class="text-sm font-semibold text-foreground">Direcciones</h4><p class="text-xs text-foreground-muted">Solo lectura. Se requiere suppliers:addresses para administrar direcciones.</p></div>
            {#if editingSupplierDetail?.addresses?.length}
              {#each editingSupplierDetail.addresses as address}
                <div class="rounded-lg border border-border bg-surface-muted/30 px-3 py-2 text-sm text-foreground"><span class="font-medium">{address.address_type}:</span> {address.line1}{address.city ? ` · ${address.city}` : ''}{address.is_primary ? ' · Principal' : ''}</div>
              {/each}
            {:else}<p class="text-xs text-foreground-muted">Sin direcciones estructuradas registradas.</p>{/if}
          </div>
        {/if}

        {#if canManageBanks}
          <div class="border-t border-border pt-4 space-y-3">
            <div><h4 class="text-sm font-semibold text-foreground">Cuenta bancaria protegida</h4><p class="text-xs text-foreground-muted">Se cifra al guardar y solo se muestran los últimos cuatro dígitos. Déjela vacía para conservar cuentas existentes.</p></div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input bind:value={formBankName} aria-label="Banco" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Banco" />
              <input bind:value={formBankHolder} aria-label="Titular de la cuenta" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Titular de la cuenta" />
              <input bind:value={formBankAccount} aria-label="Número de cuenta" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="Número de cuenta" autocomplete="off" />
              <input bind:value={formBankIban} aria-label="IBAN" class="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" placeholder="IBAN opcional" autocomplete="off" />
            </div>
            <label class="flex items-center gap-2 text-xs text-foreground-muted"><input type="checkbox" bind:checked={formBankPrimary} class="rounded border-border text-primary" /> Cuenta principal</label>
          </div>
        {:else if isEditingSupplier}
          <div class="border-t border-border pt-4 space-y-2">
            <div><h4 class="text-sm font-semibold text-foreground">Cuentas bancarias protegidas</h4><p class="text-xs text-foreground-muted">Solo lectura. Se requiere suppliers:bank_accounts para consultar o administrar cuentas.</p></div>
            <p class="text-xs text-foreground-muted">Los datos bancarios completos nunca se muestran.</p>
          </div>
        {/if}

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

        <SingleImageEditor
          bind:image={formImage}
          companyId={company.id ?? ''}
          purpose="supplier_logo"
          label="Imagen corporativa"
          emptyLabel="Logo o imagen principal del proveedor."
          altFallback={`Logo de ${formName || 'proveedor'}`}
          editable={canEditImages}
          canUpload={canUploadImages}
        />

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
        {#if permissions.hasPermission('suppliers:manage')}
          <form onsubmit={handleAddContact} class="bg-surface-muted/50 p-4 rounded-lg space-y-3">
            <div class="flex items-center justify-between gap-3">
              <h4 class="text-xs font-semibold uppercase text-foreground-muted">
                {editingContactId ? 'Editar Contacto' : 'Agregar Nuevo Contacto'}
              </h4>
              {#if editingContactId}
                <button type="button" class="text-xs text-foreground-muted hover:underline" onclick={resetContactForm}>
                  Nuevo contacto
                </button>
              {/if}
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input type="text" required placeholder="Nombre completo *" bind:value={contactName} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground focus:border-primary focus:outline-none" />
              <input type="text" placeholder="Teléfono" bind:value={contactPhone} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground focus:border-primary focus:outline-none" />
              <input type="email" placeholder="Email" bind:value={contactEmail} class="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-foreground focus:border-primary focus:outline-none" />
            </div>
            <SingleImageEditor
              bind:image={contactImage}
              companyId={company.id ?? ''}
              purpose="supplier_contact_avatar"
              label="Fotografía del contacto"
              emptyLabel="Avatar opcional para identificar al contacto."
              altFallback={contactName || 'Contacto del proveedor'}
              editable={canEditImages}
              canUpload={canUploadImages}
            />
            <div class="flex justify-end">
              <Button type="submit" size="sm" variant="primary" disabled={savingContact}>
                {savingContact ? 'Guardando...' : editingContactId ? 'Guardar cambios' : '+ Agregar Contacto'}
              </Button>
            </div>
          </form>
        {/if}

        <!-- Contacts List -->
        <div class="space-y-2">
          <h4 class="text-xs font-semibold uppercase text-foreground-muted">Contactos Registrados</h4>
          {#if selectedSupplier.contacts.length === 0}
            <p class="text-xs text-foreground-muted py-3 text-center">No hay contactos registrados aún.</p>
          {:else}
            <div class="divide-y divide-border border border-border rounded-lg">
              {#each selectedSupplier.contacts as contact}
                <div class="flex items-center justify-between p-3">
                  <div class="flex min-w-0 items-center gap-3">
                    <div class="h-9 w-9 flex-none overflow-hidden rounded-full border border-border bg-surface-muted">
                      {#if contact.avatar_image?.url}
                        <img
                          src={contact.avatar_image.url}
                          alt={contact.avatar_image.alt_text || contact.full_name}
                          loading="lazy"
                          referrerpolicy="no-referrer"
                          class="h-full w-full object-cover"
                        />
                      {:else}
                        <div class="flex h-full items-center justify-center text-xs font-semibold text-foreground-muted">
                          {contact.full_name.slice(0, 1).toUpperCase()}
                        </div>
                      {/if}
                    </div>
                    <div class="min-w-0">
                    <div class="flex items-center gap-2">
                      <div class="truncate font-medium text-sm text-foreground">{contact.full_name}</div>
                      <span class="rounded-md px-1.5 py-0.5 text-[10px] font-medium {contact.is_active ? 'bg-success/10 text-success' : 'bg-surface-muted text-foreground-subtle'}">
                        {contact.is_active ? 'Activo' : 'Inactivo'}
                      </span>
                    </div>
                    <div class="text-xs text-foreground-muted">
                      {contact.phone || 'Sin tel'} {contact.email ? ` | ${contact.email}` : ''}
                    </div>
                  </div>
                  </div>
                  {#if contactMenuItems(contact).length > 0}
                    <KebabMenu items={contactMenuItems(contact)} ariaLabel={`Acciones de ${contact.full_name}`} />
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    </Modal>
  {/if}
</div>
