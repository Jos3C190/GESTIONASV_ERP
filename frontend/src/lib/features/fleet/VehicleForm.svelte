<script lang="ts">
  import { goto } from '$app/navigation';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { fleetApi, type FleetSupplier, type FleetVehicle, type FleetVehicleType } from './api';
  import {
    FUEL_LABELS,
    isBlank,
    localDate,
    meterName,
    meterShort,
    OWNERSHIP_LABELS,
    type FuelType,
    type Ownership
  } from './catalog';
  import VehicleTypeForm from './VehicleTypeForm.svelte';
  import VehicleImage from './VehicleImage.svelte';

  interface Props {
    mode: 'create' | 'edit';
    vehicle?: FleetVehicle | null;
  }
  let { mode, vehicle = null }: Props = $props();

  const currentYear = new Date().getFullYear();
  let code = $state('');
  let plate = $state('');
  let vin = $state('');
  let chassisNumber = $state('');
  let engineNumber = $state('');
  let kind = $state('cargo_van');
  let types = $state<FleetVehicleType[]>([]);
  let typesError = $state<string | null>(null);
  let creatingType = $state(false);
  let brand = $state('');
  let model = $state('');
  let year = $state(String(currentYear));
  let color = $state('');
  let capacity = $state('');
  let fuelType = $state<FuelType>('diesel');
  let tank = $state('');
  let odometer = $state('0');
  let branchId = $state(branch.id ?? branch.branches[0]?.id ?? '');
  let notes = $state('');
  let ownership = $state<Ownership>('owned');
  let ownerSupplier = $state('');
  let contractReference = $state('');
  let contractEnds = $state('');
  let monthlyFee = $state('');
  let suppliers = $state<FleetSupplier[]>([]);
  let suppliersFailed = $state(false);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let fieldErrors = $state<Record<string, string>>({});
  let initialized = false;

  $effect(() => {
    if (initialized || !vehicle) return;
    initialized = true;
    code = vehicle.code;
    plate = vehicle.plate ?? '';
    vin = vehicle.vin ?? '';
    chassisNumber = vehicle.chassis_number ?? '';
    engineNumber = vehicle.engine_number ?? '';
    kind = vehicle.kind;
    brand = vehicle.brand;
    model = vehicle.model;
    year = String(vehicle.year);
    color = vehicle.color ?? '';
    capacity = vehicle.capacity_kg ? String(Number(vehicle.capacity_kg)) : '';
    fuelType = vehicle.fuel_type;
    tank = vehicle.tank_liters ? String(Number(vehicle.tank_liters)) : '';
    branchId = vehicle.branch_id;
    notes = vehicle.notes ?? '';
    ownership = vehicle.ownership ?? 'owned';
    ownerSupplier = vehicle.owner_supplier_id ? String(vehicle.owner_supplier_id) : '';
    contractReference = vehicle.contract_reference ?? '';
    contractEnds = vehicle.contract_ends_on ?? '';
    monthlyFee = vehicle.monthly_fee ? String(Number(vehicle.monthly_fee)) : '';
  });

  async function loadSuppliers() {
    try {
      suppliers = await fleetApi.suppliers();
    } catch {
      suppliers = [];
      suppliersFailed = true;
    }
  }

  async function loadTypes() {
    typesError = null;
    try {
      types = await fleetApi.vehicleTypes(mode === 'edit');
    } catch (err) {
      typesError = err instanceof HttpError ? err.message : 'No se pudieron cargar los tipos.';
    }
  }

  $effect(() => {
    void loadTypes();
    void loadSuppliers();
  });

  const canManageTypes = $derived(permissions.hasPermission('fleet:manage_types'));
  // Al editar sigue visible el tipo actual aunque se haya desactivado.
  const kindOptions = $derived(
    types
      .filter((item) => item.is_active || item.code === vehicle?.kind)
      .map((item) => ({ value: item.code, label: item.name }))
  );
  const currentType = $derived(types.find((item) => item.code === kind) ?? null);
  const fuelOptions = (Object.keys(FUEL_LABELS) as FuelType[])
    .filter((value) => value !== 'none')
    .map((value) => ({ value, label: FUEL_LABELS[value] }));
  const branchOptions = $derived(
    branch.branches.map((item) => ({ value: item.id, label: item.name }))
  );
  const ownershipOptions = (Object.keys(OWNERSHIP_LABELS) as Ownership[]).map((value) => ({
    value,
    label: OWNERSHIP_LABELS[value]
  }));
  // Al editar sigue visible el propietario actual aunque ya no esté activo.
  const ownerOptions = $derived([
    { value: '', label: 'Sin indicar' },
    ...(vehicle?.owner_supplier_id &&
    vehicle.owner_supplier_name &&
    !suppliers.some((item) => item.id === vehicle?.owner_supplier_id)
      ? [{ value: String(vehicle.owner_supplier_id), label: vehicle.owner_supplier_name }]
      : []),
    ...suppliers.map((item) => ({ value: String(item.id), label: item.name }))
  ]);
  const today = localDate(new Date());
  const soonLimit = localDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000));
  const contractNote = $derived(
    contractEnds && contractEnds < today
      ? { warn: true, text: 'Este contrato ya venció: no se despachará sin una autorización.' }
      : contractEnds && contractEnds <= soonLimit
        ? { warn: true, text: 'Este contrato vence en menos de 30 días.' }
        : {
            warn: false,
            text: 'Se avisará 30 días antes del fin del contrato. Ya vencido, no se despacha sin una autorización.'
          }
  );
  const droppingContract = $derived(
    mode === 'edit' && ownership === 'owned' && vehicle?.ownership !== 'owned'
  );

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (mode === 'create' && !/^[A-Za-z0-9][A-Za-z0-9 _-]{0,31}$/.test(code.trim()))
      errors.code = 'Use letras, números y guiones (máx. 32).';
    if (
      plate.trim()
        ? !/^[A-Za-z0-9][A-Za-z0-9 -]{1,15}$/.test(plate.trim())
        : currentType?.requires_plate
    )
      errors.plate = 'Indique la placa: letras, números, espacios y guiones.';
    if (!brand.trim()) errors.brand = 'Indique la marca.';
    if (!model.trim()) errors.model = 'Indique el modelo.';
    const yearNumber = Number(year);
    if (!Number.isInteger(yearNumber) || yearNumber < 1950 || yearNumber > currentYear + 1)
      errors.year = `Año entre 1950 y ${currentYear + 1}.`;
    if (capacity ? !(Number(capacity) > 0) : currentType?.requires_capacity)
      errors.capacity = 'Capacidad mayor que cero.';
    if (mode === 'create' && !(Number(odometer) >= 0)) errors.odometer = 'Lectura no válida.';
    if (mode === 'create' && !branchId) errors.branch = 'Seleccione la sucursal base.';
    if (vin.trim() && !/^[A-HJ-NPR-Za-hj-npr-z0-9]{11,17}$/.test(vin.trim()))
      errors.vin = 'VIN de 11 a 17 caracteres (sin I, O ni Q).';
    if (
      ownership !== 'owned' &&
      !isBlank(monthlyFee) &&
      !/^\d{1,7}(\.\d{1,2})?$/.test(String(monthlyFee))
    )
      errors.monthlyFee = 'Cuota de hasta 9,999,999 con 2 decimales.';
    fieldErrors = errors;
    return Object.keys(errors).length === 0;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    error = null;
    if (!validate()) return;
    saving = true;
    const fields = {
      plate: plate.trim() || null,
      vin: vin.trim() || null,
      chassis_number: chassisNumber.trim() || null,
      engine_number: engineNumber.trim() || null,
      kind,
      brand: brand.trim(),
      model: model.trim(),
      year: Number(year),
      color: color.trim() || null,
      capacity_kg: capacity ? String(Number(capacity)) : null,
      fuel_type: fuelType,
      tank_liters: tank && currentType?.fuel_applicable !== false ? String(Number(tank)) : null,
      notes: notes.trim() || null,
      ownership,
      owner_supplier_id: ownership !== 'owned' && ownerSupplier ? Number(ownerSupplier) : null,
      contract_reference: ownership !== 'owned' ? contractReference.trim() || null : null,
      contract_ends_on: ownership !== 'owned' ? contractEnds || null : null,
      monthly_fee: ownership !== 'owned' && !isBlank(monthlyFee) ? String(Number(monthlyFee)) : null
    };
    try {
      const saved =
        mode === 'create'
          ? await fleetApi.create({
              ...fields,
              code: code.trim(),
              branch_id: branchId,
              odometer_km: String(Number(odometer))
            })
          : await fleetApi.update(vehicle!.id, fields);
      await goto(`/fleet/${saved.id}`);
    } catch (err) {
      // Lo repetido se corrige en su campo, y el resto del formulario sigue a la vista.
      const taken =
        err instanceof HttpError ? err.code.match(/^vehicle_(code|plate|vin)_taken$/)?.[1] : null;
      if (taken) fieldErrors = { ...fieldErrors, [taken]: (err as HttpError).message };
      else error = err instanceof HttpError ? err.message : 'No se pudo guardar el vehículo.';
    } finally {
      saving = false;
    }
  }
</script>

<form class="vehicle-form" onsubmit={submit} novalidate>
  <Card class="form-card">
    <div class="preview">
      <VehicleImage
        image={currentType?.base_image ?? null}
        typeName={currentType?.name ?? ''}
        label={currentType?.name ?? ''}
        large
      />
      <p>La imagen base del tipo se personaliza con el logo de tu empresa.</p>
    </div>
    <div class="fields">
      <h2>Identificación</h2>
      <div class="grid">
        <FormField
          id="vehicle-code"
          label="Código interno"
          bind:value={code}
          required
          disabled={mode === 'edit'}
          maxlength={32}
          placeholder="FL-014"
          error={fieldErrors.code}
        />
        <FormField
          id="vehicle-plate"
          label={currentType?.requires_plate === false ? 'Placa (opcional)' : 'Placa'}
          bind:value={plate}
          required={currentType?.requires_plate !== false}
          maxlength={16}
          placeholder="C 123-456"
          error={fieldErrors.plate}
        />
        <FormField
          id="vehicle-vin"
          label="VIN (opcional)"
          bind:value={vin}
          maxlength={17}
          error={fieldErrors.vin}
        />
        <FormField
          id="vehicle-chassis"
          label="Chasis (opcional)"
          bind:value={chassisNumber}
          maxlength={32}
        />
        <FormField
          id="vehicle-engine"
          label="Motor (opcional)"
          bind:value={engineNumber}
          maxlength={32}
        />
        {#if mode === 'create'}
          <FormField
            id="vehicle-branch"
            label="Sucursal base"
            type="select"
            bind:value={branchId}
            options={branchOptions}
            required
            error={fieldErrors.branch}
          />
        {/if}
      </div>
      <h2>Características</h2>
      <div class="grid">
        <div class="kind-field">
          <FormField
            id="vehicle-kind"
            label="Tipo de vehículo"
            type="select"
            bind:value={kind}
            options={kindOptions}
            required
            error={typesError ?? undefined}
          />
          {#if canManageTypes}
            <button type="button" class="new-type" onclick={() => (creatingType = true)}>
              ¿No está en la lista? Crear un tipo
            </button>
          {/if}
        </div>
        <FormField
          id="vehicle-brand"
          label="Marca"
          bind:value={brand}
          required
          maxlength={60}
          error={fieldErrors.brand}
        />
        <FormField
          id="vehicle-model"
          label="Modelo"
          bind:value={model}
          required
          maxlength={80}
          error={fieldErrors.model}
        />
        <FormField
          id="vehicle-year"
          label="Año"
          type="number"
          bind:value={year}
          required
          min="1950"
          max={String(currentYear + 1)}
          error={fieldErrors.year}
        />
        <FormField id="vehicle-color" label="Color" bind:value={color} maxlength={40} />
        <FormField
          id="vehicle-capacity"
          label={currentType?.requires_capacity === false
            ? 'Capacidad de carga (kg, opcional)'
            : 'Capacidad de carga (kg)'}
          type="number"
          bind:value={capacity}
          required={currentType?.requires_capacity !== false}
          min="1"
          step="0.01"
          error={fieldErrors.capacity}
        />
        {#if currentType?.fuel_applicable !== false}
          <FormField
            id="vehicle-fuel"
            label="Combustible"
            type="select"
            bind:value={fuelType}
            options={fuelOptions}
            required
          />
          <FormField
            id="vehicle-tank"
            label="Tanque (litros, opcional)"
            type="number"
            bind:value={tank}
            min="1"
            step="0.01"
          />
        {/if}
        {#if mode === 'create'}
          <FormField
            id="vehicle-odometer"
            label={`${meterName(currentType?.meter_unit ?? 'km')} actual (${meterShort(currentType?.meter_unit ?? 'km')})`}
            type="number"
            bind:value={odometer}
            min="0"
            step="0.1"
            error={fieldErrors.odometer}
          />
        {/if}
      </div>
      <h2>Propiedad</h2>
      <div class="grid">
        <FormField
          id="vehicle-ownership"
          label="El vehículo es"
          type="select"
          bind:value={ownership}
          options={ownershipOptions}
          required
        />
        {#if ownership !== 'owned'}
          <FormField
            id="vehicle-owner"
            label="Propietario (opcional)"
            type="select"
            bind:value={ownerSupplier}
            options={ownerOptions}
          />
          <FormField
            id="vehicle-contract"
            label="Referencia del contrato (opcional)"
            bind:value={contractReference}
            maxlength={80}
          />
          <FormField
            id="vehicle-contract-ends"
            label="Fin del contrato (opcional)"
            type="date"
            bind:value={contractEnds}
          />
          <FormField
            id="vehicle-fee"
            label="Cuota mensual en USD (opcional)"
            type="number"
            bind:value={monthlyFee}
            min="0"
            step="0.01"
            error={fieldErrors.monthlyFee}
          />
        {/if}
      </div>
      {#if ownership !== 'owned'}
        <p class="hint contract-hint" class:warn={contractNote.warn}>{contractNote.text}</p>
        {#if suppliersFailed}
          <p class="hint contract-hint warn">
            No se pudieron cargar los proveedores; el propietario se puede indicar después.
          </p>
        {/if}
      {:else if droppingContract}
        <p class="hint contract-hint warn">Al guardar se borrarán los datos del contrato.</p>
      {/if}
      <label class="notes" for="vehicle-notes">
        <span>Notas</span>
        <textarea id="vehicle-notes" bind:value={notes} maxlength="2000" rows="3"></textarea>
      </label>
      {#if mode === 'edit'}
        <p class="hint">
          El código no se modifica porque identifica al vehículo en traslados e inventario. La
          sucursal, el estado y el odómetro se gestionan desde la ficha.
        </p>
      {/if}
      {#if error}<p class="error" role="alert">{error}</p>{/if}
      <div class="actions">
        <Button
          variant="secondary"
          type="button"
          onclick={() => goto(vehicle ? `/fleet/${vehicle.id}` : '/fleet')}>Cancelar</Button
        >
        <Button type="submit" disabled={saving}
          >{saving
            ? 'Guardando…'
            : mode === 'create'
              ? 'Registrar vehículo'
              : 'Guardar cambios'}</Button
        >
      </div>
    </div>
  </Card>
</form>

<Modal
  open={creatingType}
  title="Nuevo tipo de vehículo"
  size="md"
  mobileFullScreen
  onclose={() => (creatingType = false)}
>
  {#if creatingType}
    <VehicleTypeForm
      oncancel={() => (creatingType = false)}
      onsaved={(saved) => {
        types = [...types, saved];
        kind = saved.code;
        creatingType = false;
      }}
    />
  {/if}
</Modal>

<style>
  .vehicle-form :global(.form-card) {
    display: grid;
    grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
    gap: 28px;
    padding: 24px;
  }
  .preview {
    align-self: start;
    position: sticky;
    top: 20px;
    padding: 16px;
    border-radius: 12px;
    background: rgb(var(--surface-muted));
  }
  .preview p {
    margin-top: 10px;
    font-size: 11px;
    line-height: 1.5;
    color: rgb(var(--foreground-muted));
    text-align: center;
  }
  h2 {
    margin: 12px 0 12px;
    font-size: 14px;
    font-weight: 600;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px 14px;
    margin-bottom: 14px;
  }
  .grid :global(input),
  .grid :global(select) {
    border-color: rgb(var(--control-border));
    font-size: 16px;
  }
  @media (min-width: 768px) {
    .grid :global(input),
    .grid :global(select) {
      font-size: 13px;
    }
  }
  .new-type {
    display: block;
    min-height: 44px;
    margin-top: -6px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
    text-align: left;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .contract-hint {
    margin: -6px 0 14px;
    font-size: 12px;
  }
  .warn {
    color: rgb(var(--warning));
  }
  .notes {
    display: grid;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
  }
  textarea {
    padding: 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .hint {
    margin-top: 10px;
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .error {
    margin-top: 12px;
    padding: 10px 12px;
    border: 1px solid rgb(var(--danger) / 0.3);
    border-radius: 8px;
    background: rgb(var(--danger) / 0.07);
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 18px;
  }
  @media (max-width: 860px) {
    .vehicle-form :global(.form-card) {
      grid-template-columns: 1fr;
    }
    .preview {
      position: static;
    }
  }
</style>
