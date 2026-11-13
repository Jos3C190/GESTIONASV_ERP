<script lang="ts">
  import type { TransferStatus } from '$lib/features/inventory/transfer-documents';

  interface Props {
    status: TransferStatus;
    /** Adds the approval step between preparation and transit. */
    withApproval?: boolean;
  }
  let { status, withApproval = false }: Props = $props();

  // Partial reception and open differences keep the reception stage active, with a warning tone.
  const receptionPending = $derived(status === 'partially_received' || status === 'discrepancy');
  const receptionDescription = $derived(
    status === 'partially_received'
      ? 'Recepción parcial'
      : status === 'discrepancy'
        ? 'Con discrepancia'
        : 'Cuarentena en destino'
  );
  const steps = $derived(
    withApproval
      ? [
          { label: 'Preparación', description: 'Sin mover existencias' },
          {
            label: 'Aprobación',
            description: status === 'approved' ? 'Aprobado' : 'Antes del despacho'
          },
          { label: 'En tránsito', description: 'Despacho confirmado' },
          { label: 'Recepción', description: receptionDescription }
        ]
      : [
          { label: 'Preparación', description: 'Sin mover existencias' },
          { label: 'En tránsito', description: 'Despacho confirmado' },
          { label: 'Recepción', description: receptionDescription }
        ]
  );
  const lastIndex = $derived(steps.length - 1);
  // Closed with an adjustment: every stage is done, so no stage is the current one.
  const allDone = $derived(status === 'closed_with_adjustment');
  let currentIndex = $derived.by(() => {
    const offset = withApproval ? 1 : 0;
    if (allDone) return steps.length;
    if (status === 'received' || receptionPending) return lastIndex;
    if (status === 'in_transit' || status === 'incident') return 1 + offset;
    if (withApproval && (status === 'pending_approval' || status === 'approved')) return 1;
    return 0;
  });
  // The incident interrupts the trip: the transit stage is the one that needs attention.
  const warnIndex = $derived(
    receptionPending ? lastIndex : status === 'incident' ? currentIndex : -1
  );
  // Distance from the edge of the bar to the centre of the first and last step.
  const inset = $derived(50 / steps.length);
  // An approved transfer has finished its approval step even though it is still the current one.
  const approvedStep = $derived(withApproval && status === 'approved');
</script>

<section
  class="rounded-2xl border border-border bg-surface-subtle px-4 py-5 sm:px-6"
  aria-label="Avance del traslado"
>
  <div class="relative">
    <div
      class="absolute top-4 h-px bg-border"
      style:left="{inset}%"
      style:right="{inset}%"
      aria-hidden="true"
    ></div>
    <div
      class="absolute top-4 h-px bg-primary transition-[width] duration-300 motion-reduce:transition-none"
      style:left="{inset}%"
      style:width="{(Math.min(currentIndex, lastIndex) / lastIndex) * (100 - 2 * inset)}%"
      aria-hidden="true"
    ></div>
    <ol class="relative grid gap-2 {withApproval ? 'grid-cols-4' : 'grid-cols-3'}">
      {#each steps as step, index (step.label)}
        {@const completed = index < currentIndex || (approvedStep && index === 1)}
        {@const current = index === currentIndex}
        {@const warning = index === warnIndex}
        <li
          class="flex min-w-0 flex-col items-center text-center"
          aria-current={current ? 'step' : undefined}
          data-tone={warning ? 'warning' : undefined}
        >
          <span
            class="grid size-8 place-items-center rounded-full border text-xs font-semibold transition-colors duration-200 motion-reduce:transition-none {warning
              ? 'border-warning bg-warning text-warning-foreground'
              : completed || current
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border bg-surface text-foreground-muted'}"
          >
            {completed && !warning ? '✓' : index + 1}
          </span>
          <span
            class="mt-2 text-xs font-semibold sm:text-sm {warning
              ? 'text-warning'
              : current
                ? 'text-primary'
                : 'text-foreground'}">{step.label}</span
          >
          <span
            class="mt-0.5 text-xs {warning
              ? 'block font-medium text-warning'
              : 'hidden text-foreground-muted sm:block'}">{step.description}</span
          >
        </li>
      {/each}
    </ol>
  </div>
</section>
