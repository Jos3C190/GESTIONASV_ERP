<script lang="ts">
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import Button from './Button.svelte';

  let dialog = $state<HTMLDivElement | null>(null);
  let cancelButton = $state<HTMLButtonElement | null>(null);

  let isDanger = $derived(
    confirmation.current?.kind === 'delete' || confirmation.current?.kind === 'revoke'
  );
  let isRestore = $derived(confirmation.current?.kind === 'restore');

  function handleBackdrop(event: MouseEvent) {
    if (event.target === event.currentTarget) confirmation.cancel();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!confirmation.open) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      confirmation.cancel();
      return;
    }
    if (event.key !== 'Tab' || !dialog) return;
    const focusable = Array.from(
      dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  $effect(() => {
    if (!confirmation.open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => cancelButton?.focus());
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  });
</script>

<svelte:window onkeydown={handleKeydown} />

{#if confirmation.open && confirmation.current}
  <div
    class="fixed inset-0 z-[1100] flex items-center justify-center overflow-y-auto bg-black/60 p-4 backdrop-blur-md"
    role="presentation"
    onclick={handleBackdrop}
  >
    <div
      bind:this={dialog}
      class="w-full max-w-md animate-fade-scale overflow-hidden rounded-2xl border border-border bg-surface-elevated shadow-floating"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-action-title"
      aria-describedby="confirm-action-description"
      tabindex="-1"
    >
      <div class="flex gap-4 px-6 pb-5 pt-6">
        <div
          class="flex h-10 w-10 flex-none items-center justify-center rounded-full {isDanger
            ? 'bg-danger/10 text-danger'
            : isRestore
              ? 'bg-success/10 text-success'
              : 'bg-warning/10 text-warning'}"
          aria-hidden="true"
        >
          {#if confirmation.current.kind === 'delete'}
            <svg
              width="19"
              height="19"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path
                d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
              /></svg
            >
          {:else if confirmation.current.kind === 'restore'}
            <svg
              width="19"
              height="19"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 3v6h6" /></svg
            >
          {:else if confirmation.current.kind === 'end-assignment' || confirmation.current.kind === 'revoke'}
            <svg
              width="19"
              height="19"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M9 17H7A5 5 0 0 1 7 7h2" /><path d="M15 7h2a5 5 0 0 1 0 10h-2" /><path
                d="m8 12 8 0"
              /><path d="m4 4 16 16" /></svg
            >
          {:else}
            <svg
              width="19"
              height="19"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              ><path d="M18.36 6.64a9 9 0 1 1-12.73 0" /><path d="M12 2v10" /></svg
            >
          {/if}
        </div>
        <div class="min-w-0 flex-1">
          <h2 id="confirm-action-title" class="text-base font-semibold text-foreground">
            {confirmation.current.title}
          </h2>
          <p id="confirm-action-description" class="mt-1.5 text-sm leading-6 text-foreground-muted">
            {confirmation.current.description}
          </p>
          {#if confirmation.current.resourceName}
            <div
              class="mt-3 truncate rounded-lg border border-border bg-surface-muted px-3 py-2 text-sm font-medium text-foreground"
            >
              {confirmation.current.resourceName}
            </div>
          {/if}
          {#if confirmation.current.requireReason}
            <label
              for="confirm-action-reason"
              class="mt-4 block text-xs font-medium text-foreground"
            >
              {confirmation.current.reasonLabel ?? 'Motivo de eliminación'}
            </label>
            <textarea
              id="confirm-action-reason"
              rows="3"
              maxlength="500"
              value={confirmation.reason}
              oninput={(event) => confirmation.setReason(event.currentTarget.value)}
              placeholder="Explique brevemente por qué debe eliminarse este registro"
              class="mt-1.5 w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary focus:shadow-glow"
            ></textarea>
            <p class="mt-1 text-[11px] text-foreground-subtle">
              El registro irá a la papelera y podrá restaurarse.
            </p>
          {/if}
        </div>
      </div>

      {#if confirmation.error}
        <div
          class="mx-6 mb-5 rounded-lg border border-danger/25 bg-danger/10 px-3 py-2.5 text-sm text-danger"
          role="alert"
          aria-live="assertive"
        >
          {confirmation.error}
        </div>
      {/if}

      <div
        class="flex items-center justify-end gap-2 border-t border-border bg-surface-muted/50 px-6 py-4"
      >
        <button
          bind:this={cancelButton}
          type="button"
          disabled={confirmation.loading}
          onclick={() => confirmation.cancel()}
          class="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-surface-elevated px-3.5 text-sm font-medium text-foreground shadow-soft transition-colors hover:bg-surface-hover disabled:pointer-events-none disabled:opacity-40"
          >Cancelar</button
        >
        <Button
          variant={isDanger ? 'danger' : isRestore ? 'success' : 'warning'}
          disabled={confirmation.loading}
          onclick={() => void confirmation.proceed()}
        >
          {confirmation.loading ? 'Procesando…' : confirmation.current.confirmLabel}
        </Button>
      </div>
    </div>
  </div>
{/if}
