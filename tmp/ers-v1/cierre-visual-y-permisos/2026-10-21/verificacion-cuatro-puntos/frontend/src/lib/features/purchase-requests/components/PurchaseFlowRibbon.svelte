<script lang="ts">
  type Step = 1 | 2 | 3;

  let { currentStep, closed = false }: { currentStep: Step; closed?: boolean } = $props();

  let steps = $derived([
    { number: 1, title: 'Solicitudes', description: 'Reúne necesidades aprobadas' },
    { number: 2, title: 'Consolidado', description: 'Ajusta y conserva el origen' },
    {
      number: 3,
      title: closed ? 'Cerrado' : 'Cotización',
      description: closed ? 'Adjudicado o cubierto fuera del consolidado' : 'RFQ y respuestas por proveedor'
    }
  ]);
</script>

<nav aria-label="Etapas de abastecimiento" class="mb-5 rounded-xl border border-border bg-surface/70 p-3 sm:p-4">
  <ol class="grid grid-cols-3">
    {#each steps as step, index (step.number)}
      <li class="relative min-w-0 px-1 sm:px-3">
        {#if index < steps.length - 1}
          <span aria-hidden="true" class={`absolute left-[calc(50%+1rem)] right-[-50%] top-4 h-px ${currentStep > step.number ? 'bg-primary' : 'bg-border'}`}></span>
        {/if}
        <div class="relative flex flex-col items-center text-center">
          <span
            aria-current={currentStep === step.number ? 'step' : undefined}
            class={`grid h-8 w-8 place-items-center rounded-full border text-xs font-semibold transition-colors ${currentStep === step.number ? 'border-primary bg-primary text-primary-foreground shadow-sm' : currentStep > step.number ? 'border-primary/50 bg-primary/10 text-primary' : 'border-border bg-background text-foreground-muted'}`}
          >
            {step.number < currentStep ? '✓' : `0${step.number}`}
          </span>
          <span class={`mt-2 text-xs font-semibold sm:text-sm ${currentStep === step.number ? 'text-foreground' : 'text-foreground-muted'}`}>{step.title}</span>
          <span class="mt-1 hidden max-w-48 text-[11px] leading-4 text-foreground-muted sm:block">{step.description}</span>
        </div>
      </li>
    {/each}
  </ol>
</nav>
