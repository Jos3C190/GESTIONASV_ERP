<script lang="ts">
  import { untrack } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import { fleetApi, type FleetVehicleType } from './api';
  import {
    BASE_IMAGE_KEYS,
    BASE_IMAGES,
    LICENSE_LABELS,
    type BaseImage,
    type LicenseClass,
    type MeterUnit
  } from './catalog';

  let {
    item = null,
    onsaved,
    oncancel
  }: {
    item?: FleetVehicleType | null;
    onsaved: (saved: FleetVehicleType) => void;
    oncancel: () => void;
  } = $props();

  type Role = 'none' | 'tow' | 'towable';
  const initial = untrack(() => item);
  let name = $state(initial?.name ?? '');
  let plural = $state(initial?.plural ?? '');
  let licenses = $state<LicenseClass[]>(initial ? [...initial.license_classes] : []);
  let image = $state<BaseImage | ''>(initial?.base_image ?? '');
  let hasPlate = $state(initial?.requires_plate ?? true);
  let hasCapacity = $state(initial?.requires_capacity ?? true);
  let meter = $state<MeterUnit>(initial?.meter_unit ?? 'km');
  let usesFuel = $state(initial?.fuel_applicable ?? true);
  let role = $state<Role>(initial?.can_tow ? 'tow' : initial?.is_towable ? 'towable' : 'none');
  let saving = $state(false);
  let error = $state<string | null>(null);
  let nameError = $state<string | null>(null);

  const licenseOptions = Object.keys(LICENSE_LABELS) as LicenseClass[];
  const inUse = $derived((item?.usage_count ?? 0) > 0);
  const imageOptions = [
    { value: '', label: 'Sin imagen' },
    ...BASE_IMAGE_KEYS.map((value) => ({ value, label: BASE_IMAGES[value].label }))
  ];
  const meterOptions = [
    { value: 'km', label: 'Kilómetros' },
    { value: 'hours', label: 'Horas de uso' }
  ];
  const roleOptions = [
    { value: 'none', label: 'Unidad completa' },
    { value: 'tow', label: 'Cabezal: remolca otra unidad' },
    { value: 'towable', label: 'Remolque: no lleva conductor' }
  ];

  function toggleLicense(value: LicenseClass) {
    licenses = licenses.includes(value)
      ? licenses.filter((entry) => entry !== value)
      : [...licenses, value];
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    nameError = name.trim().length < 2 ? 'Indique el nombre del tipo.' : null;
    if (nameError) return;
    saving = true;
    error = null;
    const data = {
      name: name.trim(),
      plural: plural.trim() || name.trim(),
      license_classes: licenses,
      base_image: image || null,
      requires_plate: hasPlate,
      requires_capacity: hasCapacity,
      meter_unit: meter,
      fuel_applicable: usesFuel,
      can_tow: role === 'tow',
      is_towable: role === 'towable'
    };
    try {
      onsaved(
        item
          ? await fleetApi.updateVehicleType(item.id, { ...data, is_active: item.is_active })
          : await fleetApi.createVehicleType(data)
      );
    } catch (err) {
      if (err instanceof HttpError && err.code === 'vehicle_type_duplicate') {
        nameError = err.message;
      } else {
        error = err instanceof HttpError ? err.message : 'No se pudo guardar el tipo.';
      }
    } finally {
      saving = false;
    }
  }
</script>

<form class="type-form" onsubmit={submit} novalidate>
  <FormField
    id="vehicle-type-name"
    label="Nombre"
    bind:value={name}
    required
    maxlength={60}
    placeholder="Ej. Camión grúa"
    error={nameError ?? undefined}
  />
  <FormField
    id="vehicle-type-plural"
    label="Plural (opcional)"
    bind:value={plural}
    maxlength={60}
    placeholder="Ej. Camiones grúa"
  />

  <fieldset>
    <legend>Licencias que permiten conducirlo</legend>
    <div class="chips">
      {#each licenseOptions as value (value)}
        <label class="chip" class:selected={licenses.includes(value)}>
          <input
            type="checkbox"
            checked={licenses.includes(value)}
            onchange={() => toggleLicense(value)}
          />
          {LICENSE_LABELS[value]}
        </label>
      {/each}
    </div>
    <p class="hint">
      {licenses.length
        ? 'Un conductor con otra licencia no podrá salir con este vehículo sin una excepción.'
        : 'Sin selección, no se exige licencia. Úselo para equipos que no salen a la vía pública.'}
    </p>
  </fieldset>

  <fieldset>
    <legend>Qué se le exige</legend>
    <label class="check">
      <input type="checkbox" bind:checked={hasPlate} />
      <span>
        <strong>Circula por la vía pública</strong>
        <small>Exige placa y documentos de circulación.</small>
      </span>
    </label>
    <label class="check">
      <input type="checkbox" bind:checked={hasCapacity} />
      <span>
        <strong>Transporta carga</strong>
        <small>Exige capacidad en kg.</small>
      </span>
    </label>
    <label class="check">
      <input type="checkbox" bind:checked={usesFuel} />
      <span>
        <strong>Consume combustible</strong>
        <small>Sin esto, se oculta la pestaña Combustible.</small>
      </span>
    </label>
  </fieldset>

  <div class="selects">
    <FormField
      id="vehicle-type-meter"
      label="Cómo se mide su uso"
      type="select"
      bind:value={meter}
      options={meterOptions}
      disabled={inUse}
    />
    <FormField
      id="vehicle-type-role"
      label="Enganche"
      type="select"
      bind:value={role}
      options={roleOptions}
    />
    <FormField
      id="vehicle-type-image"
      label="Imagen"
      type="select"
      bind:value={image}
      options={imageOptions}
    />
  </div>
  {#if inUse}
    <p class="hint">La medida de uso no cambia porque hay vehículos registrados con este tipo.</p>
  {/if}

  {#if error}<p class="error" role="alert">{error}</p>{/if}
  <div class="actions">
    <Button type="button" variant="ghost" size="lg" onclick={oncancel}>Cancelar</Button>
    <Button type="submit" size="lg" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
  </div>
</form>

<style>
  .type-form {
    display: grid;
    gap: 14px;
  }
  fieldset {
    display: grid;
    gap: 8px;
    margin: 0;
    padding: 0;
    border: 0;
  }
  legend {
    margin-bottom: 8px;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 500;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .chip {
    position: relative;
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    padding: 0 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 999px;
    color: rgb(var(--foreground));
    font-size: 14px;
    cursor: pointer;
  }
  .chip.selected {
    border-color: rgb(var(--foreground));
    box-shadow: inset 0 0 0 1px rgb(var(--foreground));
  }
  .chip:focus-within {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  .chip input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
  }
  .check {
    display: flex;
    min-height: 44px;
    align-items: flex-start;
    gap: 10px;
    cursor: pointer;
  }
  .check input {
    width: 18px;
    height: 18px;
    flex: none;
    margin-top: 2px;
  }
  .check strong {
    display: block;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 500;
  }
  .check small {
    display: block;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .selects {
    display: grid;
    gap: 4px 14px;
  }
  .hint {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .error {
    margin: 0;
    color: rgb(var(--danger));
    font-size: 14px;
  }
  .actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding-top: 12px;
    border-top: 1px solid rgb(var(--border));
  }
  @media (min-width: 640px) {
    .selects {
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    }
    .actions {
      display: flex;
      justify-content: flex-end;
    }
  }
</style>
