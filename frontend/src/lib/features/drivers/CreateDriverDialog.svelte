<script lang="ts">
  import { untrack } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { LICENSE_LABELS, type LicenseClass } from '$lib/features/fleet/catalog';
  import { branch } from '$lib/stores/branch.svelte';
  import { driversApi, type Driver, type DriverCandidate } from './api';
  let {
    open: createOpen = $bindable(false),
    oncreated
  }: { open?: boolean; oncreated: (driver: Driver) => void | Promise<void> } = $props();
  const licenseOptions = Object.keys(LICENSE_LABELS) as LicenseClass[];
  let candidateGeneration = 0;

  let createBranch = $state('');
  let candidateSearch = $state('');
  let candidateError = $state<string | null>(null);
  let candidateLoading = $state(false);
  let candidates = $state<DriverCandidate[]>([]);
  let candidateId = $state('');
  let licenseClass = $state<LicenseClass>('liviana');
  let createNotes = $state('');
  let creating = $state(false);
  let createError = $state<string | null>(null);

  async function loadCandidates() {
    const current = ++candidateGeneration;
    candidateLoading = true;
    candidateError = null;
    if (!createBranch) {
      candidates = [];
      candidateLoading = false;
      return;
    }
    try {
      const result = await driversApi.candidates(createBranch, candidateSearch.trim() || undefined);
      if (current !== candidateGeneration || !createOpen) return;
      candidates = result;
      if (!candidates.some((item) => item.employee_id === candidateId)) candidateId = '';
    } catch (err) {
      if (current !== candidateGeneration || !createOpen) return;
      candidateError =
        err instanceof HttpError ? err.message : 'No se pudieron cargar los empleados.';
    } finally {
      if (current === candidateGeneration) candidateLoading = false;
    }
  }

  $effect(() => {
    if (!createOpen) {
      candidateGeneration++;
      return;
    }
    untrack(() => {
      createBranch = branch.id ?? branch.branches[0]?.id ?? '';
      candidateSearch = '';
      candidateId = '';
      licenseClass = 'liviana';
      createNotes = '';
      createError = null;
    });
  });

  $effect(() => {
    if (!createOpen) return;
    void createBranch;
    void candidateSearch;
    candidateGeneration++;
    candidateId = '';
    candidates = [];
    candidateLoading = true;
    candidateError = null;
    const timer = setTimeout(loadCandidates, 250);
    return () => clearTimeout(timer);
  });

  async function create() {
    if (creating || candidateLoading || !candidateId || !createBranch) return;
    creating = true;
    createError = null;
    try {
      const driver = await driversApi.create({
        employee_id: candidateId,
        branch_id: createBranch,
        license_class: licenseClass,
        notes: createNotes.trim() || null
      });
      createOpen = false;
      await oncreated(driver);
    } catch (err) {
      createError = err instanceof HttpError ? err.message : 'No se pudo registrar el conductor.';
    } finally {
      creating = false;
    }
  }
</script>

<Modal
  open={createOpen}
  title="Nuevo conductor"
  size="lg"
  preventClose={creating}
  onclose={() => {
    if (!creating) createOpen = false;
  }}
>
  <div class="form driver-create">
    <p class="hint">
      Un conductor es un empleado con asignación activa en la sucursal. La licencia se carga después
      en su perfil y queda también en su expediente de empleado.
    </p>
    <label>
      <span>Sucursal base</span>
      <select bind:value={createBranch}>
        {#each branch.branches as item (item.id)}
          <option value={item.id}>{item.name}</option>
        {/each}
      </select>
    </label>
    <label>
      <span>Buscar empleado</span>
      <input bind:value={candidateSearch} placeholder="Nombre o código" />
    </label>
    <fieldset class="candidates">
      <legend class="sr-only">Empleados disponibles</legend>
      {#if candidateLoading}<p class="muted" role="status">Buscando empleados…</p>
      {:else}
        {#each candidates as candidate (candidate.employee_id)}
          <label class="candidate" class:selected={candidateId === candidate.employee_id}>
            <input
              type="radio"
              name="driver-candidate"
              value={candidate.employee_id}
              bind:group={candidateId}
            />
            <span
              ><strong>{candidate.name}</strong><small
                >{candidate.code}{candidate.position ? ` · ${candidate.position}` : ''}</small
              ></span
            >
          </label>
        {:else}<p class="muted">
            {candidateError
              ? 'No se pudieron consultar los empleados.'
              : 'No hay empleados disponibles en esta sucursal.'}
          </p>{/each}
      {/if}
    </fieldset>
    {#if candidateError}<div class="candidate-error" role="alert">
        <p>{candidateError}</p>
        <Button size="sm" variant="secondary" disabled={candidateLoading} onclick={loadCandidates}
          >Reintentar empleados</Button
        >
      </div>{/if}
    <label>
      <span>Clase de licencia</span>
      <select bind:value={licenseClass}>
        {#each licenseOptions as option (option)}
          <option value={option}>{LICENSE_LABELS[option]}</option>
        {/each}
      </select>
    </label>
    <label>
      <span>Notas</span>
      <textarea bind:value={createNotes} rows="2" maxlength="2000"></textarea>
    </label>
    {#if createError}<p class="error-text" role="alert">{createError}</p>{/if}
    <div class="actions">
      <Button variant="secondary" disabled={creating} onclick={() => (createOpen = false)}
        >Cancelar</Button
      >
      <Button
        disabled={creating || candidateLoading || !candidateId || !createBranch}
        onclick={create}>{creating ? 'Registrando…' : 'Registrar conductor'}</Button
      >
    </div>
  </div>
</Modal>

<style>
  .candidate-error {
    display: grid;
    gap: var(--driver-space-2);
    padding: var(--driver-space-3);
    border: 1px solid rgb(var(--danger) / 0.3);
    border-radius: var(--driver-radius);
    font-size: 12px;
  }
  .hint,
  .muted {
    font-size: 12px;
    color: rgb(var(--foreground-muted));
  }
  input,
  select,
  textarea {
    min-height: 38px;
    padding: var(--driver-space-2) var(--driver-space-3);
    border: 1px solid rgb(var(--control-border));
    border-radius: var(--driver-radius);
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  input:focus-visible,
  select:focus-visible,
  textarea:focus-visible {
    outline: 2px solid rgb(var(--primary));
    outline-offset: 2px;
  }
  .form {
    display: grid;
    gap: var(--driver-space-3);
  }
  .form label {
    display: grid;
    gap: var(--driver-space-2);
    font-size: 12px;
    font-weight: 500;
  }
  .candidates {
    border: 0;
    padding: 0;
    display: grid;
    gap: var(--driver-space-2);
    max-height: 240px;
    overflow-y: auto;
  }
  .candidate {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: var(--driver-space-2) 11px;
    border: 1px solid rgb(var(--border));
    border-radius: var(--driver-radius);
    text-align: left;
  }
  .candidate span {
    display: grid;
    gap: 3px;
  }
  .candidate input {
    width: 16px;
    height: 16px;
    min-height: 0;
    padding: 0;
    accent-color: rgb(var(--primary));
  }
  .candidate small {
    font-size: 11px;
    color: rgb(var(--foreground-muted));
  }
  .candidate.selected {
    border-color: rgb(var(--primary));
    background: rgb(var(--primary) / 0.08);
  }
  .error-text {
    font-size: 12px;
    color: rgb(var(--danger));
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--driver-space-2);
  }
</style>
