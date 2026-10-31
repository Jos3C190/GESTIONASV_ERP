<script lang="ts">
  import type { TransferStatus } from '$lib/features/inventory/transfer-documents';

  let { status }: { status: TransferStatus } = $props();
  const steps = [
    { label: 'Preparación', description: 'Sin mover existencias' },
    { label: 'En tránsito', description: 'Despacho confirmado' },
    { label: 'Recepción', description: 'Cuarentena en destino' }
  ];
  let currentIndex = $derived(status === 'received' ? 2 : status === 'in_transit' ? 1 : 0);
</script>

<section class="rounded-2xl border border-border bg-surface-subtle px-4 py-5 sm:px-6" aria-label="Avance del traslado">
  <div class="relative">
    <div class="absolute left-[16.66%] right-[16.66%] top-4 h-px bg-border" aria-hidden="true"></div>
    <div
      class="absolute left-[16.66%] top-4 h-px bg-primary transition-[width] duration-300 motion-reduce:transition-none"
      style:width="{(currentIndex / 2) * 66.68}%"
      aria-hidden="true"
    ></div>
    <ol class="relative grid grid-cols-3 gap-2">
      {#each steps as step, index (step.label)}
        {@const completed = index < currentIndex}
        {@const current = index === currentIndex}
        <li class="flex min-w-0 flex-col items-center text-center" aria-current={current ? 'step' : undefined}>
          <span
            class="grid size-8 place-items-center rounded-full border text-xs font-semibold transition-colors duration-200 motion-reduce:transition-none {completed || current ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-surface text-foreground-muted'}"
          >
            {completed ? '✓' : index + 1}
          </span>
          <span class="mt-2 text-xs font-semibold sm:text-sm {current ? 'text-primary' : 'text-foreground'}">{step.label}</span>
          <span class="mt-0.5 hidden text-xs text-foreground-muted sm:block">{step.description}</span>
        </li>
      {/each}
    </ol>
  </div>
</section>
