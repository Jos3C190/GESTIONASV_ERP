<script lang="ts">
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { purchasesApi } from '$lib/api/purchases';

  type QueueKey = 'approval' | 'approved' | 'received' | 'evaluation' | 'verification';
  type QueueCount = { value: number | null; loading: boolean; error: boolean };
  type QueueCard = {
    key: QueueKey;
    title: string;
    description: string;
    href: string;
    action: string;
    count?: QueueCount;
    icon: string;
    tone: 'warning' | 'primary' | 'info' | 'success';
  };

  const EMPTY_COUNT: QueueCount = { value: null, loading: false, error: false };
  const toneClasses = {
    warning: 'bg-warning/10 text-warning',
    primary: 'bg-primary/10 text-primary',
    info: 'bg-surface-muted text-foreground',
    success: 'bg-success/10 text-success'
  };

  let counts = $state<Record<QueueKey, QueueCount>>({
    approval: { ...EMPTY_COUNT },
    approved: { ...EMPTY_COUNT },
    received: { ...EMPTY_COUNT },
    evaluation: { ...EMPTY_COUNT },
    verification: { ...EMPTY_COUNT }
  });
  let requestGeneration = 0;
  let refreshToken = $state(0);
  let refreshing = $state(false);

  let canApproveRequests = $derived(
    permissions.hasPermission('purchase_requests:read') &&
      permissions.hasPermission('purchase_requests:approve')
  );
  let canStartQuotations = $derived(
    permissions.hasPermission('purchase_requests:read') &&
      permissions.hasPermission('purchase_quotations:manage')
  );
  let canReadQuotations = $derived(permissions.hasPermission('purchase_quotations:read'));
  let canVerifyPurchases = $derived(
    permissions.hasPermission('purchases:read') && permissions.hasPermission('purchases:verify')
  );
  let canShowQuotationCounts = $derived(branch.accessAllBranches);
  let quotationScopeNotice = $derived(
    canReadQuotations && !canShowQuotationCounts
      ? 'La cola de cotizaciones no se muestra porque el módulo aún no filtra por sucursal.'
      : null
  );

  let cards = $derived.by(() => {
    const result: QueueCard[] = [];

    if (canApproveRequests) {
      result.push({
        key: 'approval',
        title: 'Por aprobar',
        description: 'Solicitudes de compra enviadas para revisión.',
        href: '/purchase-requests?status=submitted',
        action: 'Revisar solicitudes',
        count: counts.approval,
        icon: 'M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
        tone: 'warning'
      });
    }

    if (canStartQuotations) {
      result.push({
        key: 'approved',
        title: 'Aprobadas para cotizar',
        description: 'Solicitudes listas para preparar una cotización.',
        href: '/purchase-requests?status=approved',
        action: 'Ver solicitudes',
        count: counts.approved,
        icon: 'M9 12l2 2 4-4m5-3v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2Z',
        tone: 'primary'
      });
    }

    if (canReadQuotations && canShowQuotationCounts) {
      result.push(
        {
          key: 'received',
          title: 'Ofertas registradas',
          description: 'Respuestas de proveedores ingresadas manualmente por el equipo.',
          href: '/purchase-quotations?status=received',
          action: 'Revisar respuestas',
          count: counts.received,
          icon: 'M4 5h16v14H4zM8 9h8M8 13h5',
          tone: 'info'
        },
        {
          key: 'evaluation',
          title: 'En evaluación',
          description: 'Cotizaciones que siguen en proceso de comparación.',
          href: '/purchase-quotations?status=under_evaluation',
          action: 'Continuar evaluación',
          count: counts.evaluation,
          icon: 'M3 12h4l3 8 4-16 3 8h4',
          tone: 'primary'
        }
      );
    }

    if (canVerifyPurchases) {
      result.push({
        key: 'verification',
        title: 'Recepciones por verificar',
        description: 'Mercancía recibida que requiere revisión física.',
        href: '/purchases?status=received',
        action: 'Revisar recepciones',
        count: counts.verification,
        icon: 'M5 12l4 4L19 6M4 4h16v16H4z',
        tone: 'success'
      });
    }

    return result;
  });

  async function totalOf(result: Promise<{ meta: { total: number } }>): Promise<number> {
    return (await result).meta.total;
  }

  function retryCounts() {
    refreshToken += 1;
  }

  function showAllBranches() {
    if (branch.accessAllBranches) branch.select(null);
  }

  $effect(() => {
    const refreshRequested = refreshToken > 0;
    const selectedBranchId = branch.id ?? undefined;
    const loadApproval = canApproveRequests;
    const loadApproved = canStartQuotations;
    const loadQuotes = canReadQuotations && canShowQuotationCounts;
    const loadVerification = canVerifyPurchases;
    const generation = ++requestGeneration;

    if (refreshRequested) refreshing = true;

    counts = {
      approval: {
        value: null,
        loading: loadApproval,
        error: false
      },
      approved: {
        value: null,
        loading: loadApproved,
        error: false
      },
      received: {
        value: null,
        loading: loadQuotes,
        error: false
      },
      evaluation: {
        value: null,
        loading: loadQuotes,
        error: false
      },
      verification: {
        value: null,
        loading: loadVerification,
        error: false
      }
    };

    const jobs: Array<{ key: QueueKey; request: Promise<number> }> = [];

    if (loadApproval) {
      jobs.push({
        key: 'approval',
        request: totalOf(
          purchaseRequestsApi.list({
            status: 'submitted',
            branch_id: selectedBranchId,
            page: 1,
            size: 1
          })
        )
      });
    }

    if (loadApproved) {
      jobs.push({
        key: 'approved',
        request: totalOf(
          purchaseRequestsApi.list({
            status: 'approved',
            branch_id: selectedBranchId,
            page: 1,
            size: 1
          })
        )
      });
    }

    if (loadQuotes) {
      jobs.push(
        {
          key: 'received',
          request: totalOf(purchaseQuotationsApi.list({ status: 'received', page: 1, size: 1 }))
        },
        {
          key: 'evaluation',
          request: totalOf(
            purchaseQuotationsApi.list({ status: 'under_evaluation', page: 1, size: 1 })
          )
        }
      );
    }

    if (loadVerification) {
      jobs.push({
        key: 'verification',
        request: totalOf(
          purchasesApi.list({
            status: 'received',
            branch_id: selectedBranchId,
            page: 1,
            size: 1
          })
        )
      });
    }

    void Promise.allSettled(jobs.map((job) => job.request)).then((results) => {
      if (generation !== requestGeneration) return;

      refreshing = false;
      const next = { ...counts };
      jobs.forEach((job, index) => {
        const result = results[index];
        next[job.key] =
          result?.status === 'fulfilled'
            ? { value: result.value, loading: false, error: false }
            : { value: null, loading: false, error: true };
      });
      counts = next;
    });

    return () => {
      if (requestGeneration === generation) requestGeneration += 1;
    };
  });
</script>

{#if cards.length > 0 || quotationScopeNotice}
  <section class="mb-6 space-y-3" aria-labelledby="procurement-queue-title">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 id="procurement-queue-title" class="text-base font-semibold text-foreground">
          Cola de compras
        </h2>
        <p class="text-sm text-foreground-muted">
          Solicitudes y recepciones: {branch.label}.
          {#if canReadQuotations && canShowQuotationCounts}
            Cotizaciones: todas las sucursales.
          {/if}
        </p>
      </div>
      {#if Object.values(counts).some((count) => count.error)}
        <button
          type="button"
          onclick={retryCounts}
          disabled={refreshing}
          class="inline-flex min-h-9 items-center justify-center rounded-lg border border-border bg-surface px-3 text-sm font-medium text-foreground hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          {refreshing ? 'Actualizando conteos…' : 'Reintentar conteos'}
        </button>
      {:else if branch.accessAllBranches && branch.id !== null}
        <button
          type="button"
          onclick={showAllBranches}
          class="inline-flex min-h-9 items-center justify-center rounded-lg border border-border bg-surface px-3 text-sm font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          Ver todas las sucursales
        </button>
      {:else}
        <span class="text-xs text-foreground-subtle">Las tarjetas abren sus módulos.</span>
      {/if}
    </div>

    {#if quotationScopeNotice}
      <p
        class="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-foreground-muted"
        role="status"
      >
        {quotationScopeNotice}
      </p>
    {/if}

    <div
      class="grid gap-3"
      style="grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr));"
    >
      {#each cards as card (card.key)}
        <a
          href={card.href}
          class="group flex min-h-36 flex-col rounded-xl border border-border bg-surface-elevated p-3.5 transition-colors hover:border-primary/40 hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex min-w-0 items-center gap-2.5">
              <span
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg {toneClasses[
                  card.tone
                ]}"
                aria-hidden="true"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"><path d={card.icon} /></svg
                >
              </span>
              <h3 class="text-sm font-semibold leading-5 text-foreground">{card.title}</h3>
            </div>
            {#if card.count?.loading}
              <span aria-live="polite" aria-atomic="true">
                <span class="sr-only">Cargando conteo…</span>
                <span class="skeleton block h-7 w-10 rounded" aria-hidden="true"></span>
              </span>
            {:else if card.count}
              <span
                class="queue-count font-mono text-2xl font-semibold tabular-nums text-foreground"
                aria-live="polite"
                aria-atomic="true"
                aria-label={card.count.error
                  ? 'No se pudo cargar el conteo'
                  : `${card.count.value} pendientes`}
              >
                {card.count.error ? '—' : (card.count.value ?? '—')}
              </span>
            {/if}
          </div>

          <p class="mt-3 text-sm leading-5 text-foreground-muted">{card.description}</p>

          {#if card.count && !card.count.loading && !card.count.error && card.count.value === 0}
            <p class="mt-2 text-xs font-medium text-success">Sin pendientes en este alcance.</p>
          {/if}

          {#if card.count?.error}
            <p class="mt-2 text-xs leading-5 text-warning" role="status" aria-live="polite">
              No se pudo cargar el conteo. Puedes abrir la lista o reintentar las tarjetas.
            </p>
          {/if}

          <span
            class="mt-auto inline-flex items-center gap-1 pt-3 text-sm font-medium text-primary group-hover:underline"
          >
            {card.count?.error ? 'Abrir módulo' : card.action}
            <span aria-hidden="true">→</span>
          </span>
        </a>
      {/each}
    </div>
  </section>
{/if}

<style>
  .queue-count {
    animation: queue-count-in 180ms ease-out;
  }

  @keyframes queue-count-in {
    from {
      opacity: 0;
      transform: translateY(3px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .queue-count {
      animation: none;
    }
  }
</style>
