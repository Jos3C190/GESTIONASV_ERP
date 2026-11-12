<script lang="ts">
  import type { TransferStatus } from '$lib/features/inventory/transfer-documents';

  interface Props {
    status: TransferStatus;
    /** Adds the approval step between preparation and transit. */
    withApproval?: boolean;
  }
  let { status, withApproval = false }: Props = $props();

  const steps = $derived(
    withApproval
      ? [
          { label: 'Preparación', description: 'Sin mover existencias' },
          {
            label: 'Aprobación',
            description: status === 'approved' ? 'Aprobado' : 'Antes del despacho'
          },
          { label: 'En tránsito', description: 'Despacho confirmado' },
          { label: 'Recepción', description: 'Cuarentena en destino' }
        ]
      : [
          { label: 'Preparación', description: 'Sin mover existencias' },
          { label: 'En tránsito', description: 'Despacho confirmado' },
          { label: 'Recepción', description: 'Cuarentena en destino' }
        ]
  );
  const lastIndex = $derived(steps.length - 1);
  let currentIndex = $derived.by(() => {
    const offset = withApproval ? 1 : 0;
    if (status === 'received') return lastIndex;
    if (status === 'in_transit') return 1 + offset;
    if (withApproval && (status === 'pending_approval' || status === 'approved')) return 1;
    return 0;
  });
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
      style:width="{(currentIndex / lastIndex) * (100 - 2 * inset)}%"
      aria-hidden="true"
    ></div>
    <ol class="relative grid gap-2 {withApproval ? 'grid-cols-4' : 'grid-cols-3'}">
      {#each steps as step, index (step.label)}
        {@const completed = index < currentIndex || (approvedStep && index === 1)}
        {@const current = index === currentIndex}
        <li
          class="flex min-w-0 flex-col items-center text-center"
          aria-current={current ? 'step' : undefined}
        >
          <span
            class="grid size-8 place-items-center rounded-full border text-xs font-semibold transition-colors duration-200 motion-reduce:transition-none {completed ||
            current
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-border bg-surface text-foreground-muted'}"
          >
            {completed ? '✓' : index + 1}
          </span>
          <span
            class="mt-2 text-xs font-semibold sm:text-sm {current
              ? 'text-primary'
              : 'text-foreground'}">{step.label}</span
          >
          <span class="mt-0.5 hidden text-xs text-foreground-muted sm:block"
            >{step.description}</span
          >
        </li>
      {/each}
    </ol>
  </div>
</section>
