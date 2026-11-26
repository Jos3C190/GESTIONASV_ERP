<script lang="ts">
  /** El supervisor define su PIN de autorización confirmando su contraseña. */
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { posApi } from '#lib/api/pos.ts';

  interface Props {
    open: boolean;
    hasPin: boolean;
    onclose: () => void;
    onsaved: () => void;
  }

  let { open, hasPin, onclose, onsaved }: Props = $props();
  let password = $state('');
  let pin = $state('');
  let repeat = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  const valid = $derived(password.length > 0 && /^\d{6}$/.test(pin) && pin === repeat);

  $effect(() => {
    if (open) {
      password = '';
      pin = '';
      repeat = '';
      error = null;
    }
  });

  function digits(event: Event): string {
    const input = event.currentTarget as HTMLInputElement;
    input.value = input.value.replace(/\D/g, '').slice(0, 6);
    return input.value;
  }

  async function save() {
    if (!valid) return;
    saving = true;
    error = null;
    try {
      await posApi.setPin(password, pin);
      onsaved();
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo guardar el PIN.';
    } finally {
      saving = false;
      password = '';
    }
  }
</script>

<Modal {open} title={hasPin ? 'Cambiar mi PIN' : 'Definir mi PIN'} {onclose} size="sm">
  <form
    id="pin-form"
    class="space-y-3"
    onsubmit={(event) => {
      event.preventDefault();
      void save();
    }}
  >
    <p class="text-sm text-foreground-muted">
      Con este PIN autorizas en la caja salidas de efectivo, descuentos, anulaciones y devoluciones.
      Usa seis dígitos que no sean repetidos ni seguidos.
    </p>
    <label class="block text-sm font-medium text-foreground">
      Tu contraseña
      <input
        type="password"
        autocomplete="current-password"
        class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground"
        bind:value={password}
      />
    </label>
    <label class="block text-sm font-medium text-foreground">
      PIN nuevo
      <input
        type="password"
        inputmode="numeric"
        autocomplete="off"
        maxlength="6"
        class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-center text-lg tracking-[0.4em] text-foreground"
        value={pin}
        oninput={(event) => (pin = digits(event))}
      />
    </label>
    <label class="block text-sm font-medium text-foreground">
      Repite el PIN
      <input
        type="password"
        inputmode="numeric"
        autocomplete="off"
        maxlength="6"
        class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-center text-lg tracking-[0.4em] text-foreground"
        value={repeat}
        oninput={(event) => (repeat = digits(event))}
      />
      {#if repeat.length === 6 && repeat !== pin}
        <span class="mt-1 block text-xs text-danger">Los PIN no coinciden.</span>
      {/if}
    </label>
    {#if error}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {error}
      </p>
    {/if}
  </form>
  {#snippet footer()}
    <Button variant="secondary" onclick={onclose}>Cancelar</Button>
    <Button type="submit" form="pin-form" disabled={!valid || saving}>
      {saving ? 'Guardando…' : 'Guardar PIN'}
    </Button>
  {/snippet}
</Modal>
