export type ConfirmActionKind = 'delete' | 'deactivate' | 'end-assignment' | 'revoke';

export interface ConfirmActionRequest {
  kind: ConfirmActionKind;
  title: string;
  description: string;
  confirmLabel: string;
  resourceName?: string;
  execute: () => void | Promise<void>;
}

function createConfirmationStore() {
  let current = $state<ConfirmActionRequest | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
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
    request(next: ConfirmActionRequest) {
      if (loading) return;
      returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      error = null;
      current = next;
    },
    cancel() {
      if (loading || current === null) return;
      current = null;
      error = null;
      restoreFocus();
    },
    async proceed() {
      if (loading || current === null) return;
      loading = true;
      error = null;
      try {
        await current.execute();
        current = null;
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
      returnFocus = null;
    }
  };
}

export const confirmation = createConfirmationStore();
