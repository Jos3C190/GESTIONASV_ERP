export type ConfirmActionKind = 'delete' | 'deactivate' | 'restore' | 'end-assignment' | 'revoke';

export interface ConfirmActionRequest {
  kind: ConfirmActionKind;
  title: string;
  description: string;
  confirmLabel: string;
  resourceName?: string;
  requireReason?: boolean;
  reasonLabel?: string;
  execute: (reason?: string) => void | Promise<void>;
}

function createConfirmationStore() {
  let current = $state<ConfirmActionRequest | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let reason = $state('');
  let returnFocus: HTMLElement | null = null;

  function restoreFocus() {
    const target = returnFocus;
    returnFocus = null;
    requestAnimationFrame(() => target?.focus());
  }

  return {
    get current() {
      return current;
    },
    get open() {
      return current !== null;
    },
    get loading() {
      return loading;
    },
    get error() {
      return error;
    },
    get reason() {
      return reason;
    },
    setReason(value: string) {
      reason = value;
      if (error) error = null;
    },
    request(next: ConfirmActionRequest) {
      if (loading) return;
      returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      error = null;
      reason = '';
      current = next;
    },
    cancel() {
      if (loading || current === null) return;
      current = null;
      error = null;
      reason = '';
      restoreFocus();
    },
    async proceed() {
      if (loading || current === null) return;
      if (current.requireReason && reason.trim().length < 3) {
        error = 'Indique un motivo de al menos 3 caracteres.';
        return;
      }
      loading = true;
      error = null;
      try {
        await current.execute(reason.trim() || undefined);
        current = null;
        reason = '';
        restoreFocus();
      } catch (cause) {
        error = cause instanceof Error ? cause.message : 'No se pudo completar la operación.';
      } finally {
        loading = false;
      }
    },
    reset() {
      current = null;
      loading = false;
      error = null;
      reason = '';
      returnFocus = null;
    }
  };
}

export const confirmation = createConfirmationStore();
