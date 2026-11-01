<script lang="ts">
  import { api, HttpError } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';

  let {
    open,
    title,
    resource,
    recordId,
    description,
    onclose,
    ondone
  }: {
    open: boolean;
    title: string;
    resource: 'fleet_vehicles' | 'drivers';
    recordId: string;
    description: string;
    onclose: () => void;
    ondone: () => void;
  } = $props();

  let reason = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    if (open) {
      reason = '';
      error = null;
    }
  });

  async function confirm() {
    saving = true;
    error = null;
    try {
      await api.lifecycle.delete(resource, recordId, reason.trim());
      ondone();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudo mover a la papelera.';
    } finally {
      saving = false;
    }
  }
</script>

<Modal {open} {title} {onclose}>
  <div class="body">
    <p>{description}</p>
    <label>
      <span>Motivo</span>
      <textarea bind:value={reason} rows="3" maxlength="500"></textarea>
    </label>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <div class="actions">
      <Button variant="secondary" onclick={onclose}>Cancelar</Button>
      <Button variant="danger" disabled={saving || reason.trim().length < 3} onclick={confirm}
        >{saving ? 'Moviendo…' : 'Mover a la papelera'}</Button
      >
    </div>
  </div>
</Modal>

<style>
  .body {
    display: grid;
    gap: 12px;
    font-size: 13px;
  }
  label {
    display: grid;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
  }
  textarea {
    padding: 8px 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--surface));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .error {
    color: rgb(var(--danger));
    font-size: 12px;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
