<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '#lib/api/client.ts';
  import type { GeographyInput } from '#lib/types/customer.ts';

  interface Props {
    idPrefix: string;
    value: GeographyInput | null;
    disabled?: boolean;
    required?: boolean;
    onchange: (value: GeographyInput | null) => void;
  }

  let { idPrefix, value, disabled = false, required = false, onchange }: Props = $props();

  const selectClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  type Option = { id: string; name: string };
  let departments = $state<Option[]>([]);
  let municipalities = $state<Option[]>([]);
  let districts = $state<Option[]>([]);
  let department = $state('');
  let municipality = $state('');
  let district = $state('');
  let loadError = $state<string | null>(null);

  async function loadMunicipalities(departmentId: string) {
    municipalities = departmentId ? await api.geography.municipalities(departmentId) : [];
  }

  async function loadDistricts(municipalityId: string) {
    districts = municipalityId ? await api.geography.districts(municipalityId) : [];
  }

  onMount(async () => {
    try {
      departments = await api.geography.departments();
      if (value) {
        department = value.department_id;
        municipality = value.municipality_id;
        district = value.district_id;
        await Promise.all([loadMunicipalities(department), loadDistricts(municipality)]);
      }
    } catch {
      loadError = 'No se pudo cargar la división territorial.';
    }
  });

  function emit() {
    onchange(
      department && municipality && district
        ? { department_id: department, municipality_id: municipality, district_id: district }
        : null
    );
  }

  async function changeDepartment() {
    municipality = '';
    district = '';
    districts = [];
    await loadMunicipalities(department);
    emit();
  }

  async function changeMunicipality() {
    district = '';
    await loadDistricts(municipality);
    emit();
  }
</script>

{#if loadError}
  <p class="text-sm text-danger" role="alert">{loadError}</p>
{/if}
<div class="grid gap-4 sm:grid-cols-3">
  <div>
    <label for="{idPrefix}-department" class="mb-1 block text-sm font-medium text-foreground">
      Departamento
    </label>
    <select
      id="{idPrefix}-department"
      bind:value={department}
      onchange={() => void changeDepartment()}
      {disabled}
      {required}
      class={selectClass}
    >
      <option value="">Selecciona…</option>
      {#each departments as item (item.id)}
        <option value={item.id}>{item.name}</option>
      {/each}
    </select>
  </div>
  <div>
    <label for="{idPrefix}-municipality" class="mb-1 block text-sm font-medium text-foreground">
      Municipio
    </label>
    <select
      id="{idPrefix}-municipality"
      bind:value={municipality}
      onchange={() => void changeMunicipality()}
      disabled={disabled || !department}
      required={required || Boolean(department)}
      class={selectClass}
    >
      <option value="">Selecciona…</option>
      {#each municipalities as item (item.id)}
        <option value={item.id}>{item.name}</option>
      {/each}
    </select>
  </div>
  <div>
    <label for="{idPrefix}-district" class="mb-1 block text-sm font-medium text-foreground">
      Distrito
    </label>
    <select
      id="{idPrefix}-district"
      bind:value={district}
      onchange={emit}
      disabled={disabled || !municipality}
      required={required || Boolean(department)}
      class={selectClass}
    >
      <option value="">Selecciona…</option>
      {#each districts as item (item.id)}
        <option value={item.id}>{item.name}</option>
      {/each}
    </select>
  </div>
</div>
