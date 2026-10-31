<script lang="ts">
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import { purchasesApi } from '$lib/api/purchases';
  import { retaceosApi } from '$lib/api/retaceos';

  type QueueKey =
    | 'approval'
    | 'approved'
    | 'quoteResponse'
    | 'received'
    | 'evaluation'
    | 'orderApproval'
    | 'orderSend'
    | 'orderReceiving'
    | 'orderPartial'
    | 'verification'
    | 'retaceoDraft'
    | 'retaceoCalculated';
  type QueueCount = { value: number | null; loading: boolean; error: boolean };
  type QueueGroup = 'Solicitudes' | 'Cotizaciones' | 'Órdenes' | 'Recepciones' | 'Retaceos';
  type QueueCard = {
    key: QueueKey;
    group: QueueGroup;
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
  const workflowSteps = [
    { title: 'Solicitud', text: 'El empleado registra la necesidad y el responsable la aprueba.' },
    { title: 'Consolidado', text: 'Compras reúne solicitudes aprobadas y, si aplica, agrega demanda central.' },
    { title: 'Cotización (RFQ)', text: 'Se prepara y envía una copia a cada proveedor; luego se registra su respuesta.' },
    { title: 'Comparación y adjudicación', text: 'Compras compara cada producto y decide qué cantidad asignar a cada proveedor.' },
    { title: 'Orden de compra', text: 'Se crea la orden con las cantidades adjudicadas, se aprueba y se envía.' },
    { title: 'Recepción e inspección', text: 'Se cuenta lo recibido, se confirma lo aceptado y se asigna una ubicación.' },
    { title: 'Inventario', text: 'Lo aceptado entra en cuarentena hasta pasar la revisión y quedar disponible.' },
    { title: 'Retaceo', text: 'Se registran y distribuyen costos; después se calcula, verifica y cierra.' }
  ];

  let counts = $state<Record<QueueKey, QueueCount>>({
    approval: { ...EMPTY_COUNT },
    approved: { ...EMPTY_COUNT },
    quoteResponse: { ...EMPTY_COUNT },
    received: { ...EMPTY_COUNT },
    evaluation: { ...EMPTY_COUNT },
    orderApproval: { ...EMPTY_COUNT },
    orderSend: { ...EMPTY_COUNT },
    orderReceiving: { ...EMPTY_COUNT },
    orderPartial: { ...EMPTY_COUNT },
    verification: { ...EMPTY_COUNT },
    retaceoDraft: { ...EMPTY_COUNT },
    retaceoCalculated: { ...EMPTY_COUNT }
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
  let canApproveOrders = $derived(
    permissions.hasPermission('purchase_orders:read') &&
      permissions.hasPermission('purchase_orders:approve')
  );
  let canSendOrders = $derived(
    permissions.hasPermission('purchase_orders:read') &&
      permissions.hasPermission('purchase_orders:send')
  );
  let canReceiveOrders = $derived(
    permissions.hasPermission('purchase_orders:read') &&
      permissions.hasPermission('purchases:read') &&
      permissions.hasPermission('purchases:manage')
  );
  let canVerifyPurchases = $derived(
    permissions.hasPermission('purchases:read') && permissions.hasPermission('purchases:verify')
  );
  let canCompletePurchaseVerification = $derived(
    permissions.hasPermission('purchases:verify') &&
      permissions.hasPermission('inventory:receive') &&
      permissions.hasPermission('locations.view')
  );
  let missingPurchaseVerificationMessage = $derived.by(() => {
    const needsInventoryAccess = !permissions.hasPermission('inventory:receive');
    const needsLocationAccess = !permissions.hasPermission('locations.view');
    if (needsInventoryAccess && needsLocationAccess) {
      return 'Para completar la recepción, tu perfil necesita acceso para registrar la mercancía en Inventario y consultar o asignar ubicaciones. Pide al administrador que revise esos accesos.';
    }
    if (needsInventoryAccess) {
      return 'Para completar la recepción, tu perfil necesita acceso para registrar la mercancía en Inventario. Pide al administrador que revise ese acceso.';
    }
    return 'Para completar la recepción, tu perfil necesita acceso para consultar y asignar ubicaciones. Pide al administrador que revise ese acceso.';
  });
  let canCalculateRetaceo = $derived(permissions.hasPermission('retaceos:calculate'));
  let canCalculateRetaceos = $derived(
    permissions.hasPermission('retaceos:read') &&
      (permissions.hasPermission('retaceos:manage') ||
        permissions.hasPermission('retaceos:calculate'))
  );
  let canVerifyRetaceos = $derived(
    permissions.hasPermission('retaceos:read') && permissions.hasPermission('retaceos:verify')
  );
  let cards = $derived.by(() => {
    const result: QueueCard[] = [];

    if (canApproveRequests) {
      result.push({
        key: 'approval',
        group: 'Solicitudes',
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
        group: 'Solicitudes',
        title: 'Aprobadas para cotizar',
        description: 'Solicitudes listas para preparar una cotización.',
        href: '/purchase-requests?status=approved',
        action: 'Ver solicitudes',
        count: counts.approved,
        icon: 'M9 12l2 2 4-4m5-3v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2Z',
        tone: 'primary'
      });
    }

    if (canReadQuotations) {
      result.push(
        {
          key: 'quoteResponse',
          group: 'Cotizaciones',
          title: 'Cotizaciones por responder',
          description: 'Solicitudes de precio enviadas que aún esperan la respuesta del proveedor.',
          href: '/purchase-quotations?status=requested',
          action: 'Revisar solicitudes de precio',
          count: counts.quoteResponse,
          icon: 'M4 5h16v14H4zM8 9h8M8 13h5M8 17h3',
          tone: 'warning'
        },
        {
          key: 'received',
          group: 'Cotizaciones',
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
          group: 'Cotizaciones',
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

    if (canApproveOrders) {
      result.push({
        key: 'orderApproval',
        group: 'Órdenes',
        title: 'Órdenes por aprobar',
        description: 'Órdenes enviadas al flujo interno de aprobación.',
        href: '/purchase-orders?status=pending_approval',
        action: 'Revisar órdenes',
        count: counts.orderApproval,
        icon: 'M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
        tone: 'warning'
      });
    }

    if (canSendOrders) {
      result.push({
        key: 'orderSend',
        group: 'Órdenes',
        title: 'Órdenes listas para enviar',
        description: 'Órdenes aprobadas que todavía no se han enviado al proveedor.',
        href: '/purchase-orders?status=approved',
        action: 'Enviar órdenes',
        count: counts.orderSend,
        icon: 'M4 12h15m-6-6 6 6-6 6M5 5v14',
        tone: 'primary'
      });
    }

    if (canReceiveOrders) {
      result.push(
        {
          key: 'orderReceiving',
          group: 'Órdenes',
          title: 'Órdenes pendientes de recepción',
          description: 'Órdenes enviadas al proveedor que aún no tienen una recepción registrada.',
          href: '/purchase-orders?status=sent',
          action: 'Preparar recepción',
          count: counts.orderReceiving,
          icon: 'M3 7h18l-2 12H5L3 7Zm4 0V5a5 5 0 0 1 10 0v2',
          tone: 'info'
        },
        {
          key: 'orderPartial',
          group: 'Órdenes',
          title: 'Órdenes parcialmente recibidas',
          description: 'Quedan cantidades pendientes de recibir en estas órdenes.',
          href: '/purchase-orders?status=partially_received',
          action: 'Continuar recepción',
          count: counts.orderPartial,
          icon: 'M4 12h16M12 4v16M5 5h14v14H5z',
          tone: 'primary'
        }
      );
    }

    if (canVerifyPurchases) {
      result.push({
        key: 'verification',
        group: 'Recepciones',
        title: 'Recepciones por verificar',
        description: canCompletePurchaseVerification
          ? 'Mercancía recibida que requiere revisión física y registro en Inventario.'
          : missingPurchaseVerificationMessage,
        href: '/purchases?status=received',
        action: 'Revisar recepciones',
        count: counts.verification,
        icon: 'M5 12l4 4L19 6M4 4h16v16H4z',
        tone: 'success'
      });
    }

    if (canCalculateRetaceos) {
      result.push({
        key: 'retaceoDraft',
        group: 'Retaceos',
        title: 'Retaceos por calcular',
        description: canCalculateRetaceo
          ? 'Borradores de distribución de costos que esperan cálculo.'
          : 'Puedes revisar los borradores. Para calcularlos, pide a un administrador que habilite esa acción para tu perfil.',
        href: '/retaceos?status=draft',
        action: canCalculateRetaceo ? 'Calcular retaceos' : 'Abrir borradores',
        count: counts.retaceoDraft,
        icon: 'M4 4h16v16H4zM8 8h8M8 12h5M8 16h8',
        tone: 'warning'
      });
    }

    if (canVerifyRetaceos) {
      result.push({
        key: 'retaceoCalculated',
        group: 'Retaceos',
        title: 'Retaceos por verificar',
        description: 'Costos calculados que esperan revisión y aprobación.',
        href: '/retaceos?status=calculated',
        action: 'Verificar retaceos',
        count: counts.retaceoCalculated,
        icon: 'M5 12l4 4L19 6M4 4h16v16H4z',
        tone: 'success'
      });
    }

    return result;
  });
  let cardGroups = $derived.by(() => {
    const groupOrder: QueueGroup[] = [
      'Solicitudes',
      'Cotizaciones',
      'Órdenes',
      'Recepciones',
      'Retaceos'
    ];

    return groupOrder
      .map((label) => {
        const groupCards = cards.filter((card) => card.group === label);
        const groupCounts = groupCards.flatMap((card) => (card.count ? [card.count] : []));
        const totalCount = groupCounts.reduce((sum, count) => sum + (count.value ?? 0), 0);
        const countText = groupCounts.some((count) => count.loading)
          ? 'Cargando pendientes…'
          : groupCounts.some((count) => count.error || count.value === null)
            ? 'Conteo incompleto'
            : totalCount === 0
              ? 'Sin pendientes'
              : `${totalCount} pendientes`;

        return { label, cards: groupCards, countText };
      })
      .filter((group) => group.cards.length > 0);
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
    const selectedBranchId = branch.id;
    const loadApproval = canApproveRequests;
    const loadApproved = canStartQuotations;
    const loadQuotes = canReadQuotations;
    const loadOrderApproval = canApproveOrders;
    const loadOrderSend = canSendOrders;
    const loadOrderReceiving = canReceiveOrders;
    const loadVerification = canVerifyPurchases;
    const loadRetaceoDraft = canCalculateRetaceos;
    const loadRetaceoCalculated = canVerifyRetaceos;
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
      quoteResponse: {
        value: null,
        loading: loadQuotes,
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
      orderApproval: {
        value: null,
        loading: loadOrderApproval,
        error: false
      },
      orderSend: {
        value: null,
        loading: loadOrderSend,
        error: false
      },
      orderReceiving: {
        value: null,
        loading: loadOrderReceiving,
        error: false
      },
      orderPartial: {
        value: null,
        loading: loadOrderReceiving,
        error: false
      },
      verification: {
        value: null,
        loading: loadVerification,
        error: false
      },
      retaceoDraft: {
        value: null,
        loading: loadRetaceoDraft,
        error: false
      },
      retaceoCalculated: {
        value: null,
        loading: loadRetaceoCalculated,
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
            branch_id: selectedBranchId ?? undefined,
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
            branch_id: selectedBranchId ?? undefined,
            page: 1,
            size: 1
          })
        )
      });
    }

    if (loadQuotes) {
      jobs.push(
        {
          key: 'quoteResponse',
          request: totalOf(
            purchaseQuotationsApi.list({
              status: 'requested',
              branch_id: selectedBranchId ?? undefined,
              page: 1,
              size: 1
            })
          )
        },
        {
          key: 'received',
          request: totalOf(
            purchaseQuotationsApi.list({
              status: 'received',
              branch_id: selectedBranchId ?? undefined,
              page: 1,
              size: 1
            })
          )
        },
        {
          key: 'evaluation',
          request: totalOf(
            purchaseQuotationsApi.list({
              status: 'under_evaluation',
              branch_id: selectedBranchId ?? undefined,
              page: 1,
              size: 1
            })
          )
        }
      );
    }

    if (loadOrderApproval) {
      jobs.push({
        key: 'orderApproval',
        request: totalOf(
          purchaseOrdersApi.list({
            status: 'pending_approval',
            branch_id: selectedBranchId,
            page: 1,
            size: 1
          })
        )
      });
    }

    if (loadOrderSend) {
      jobs.push({
        key: 'orderSend',
        request: totalOf(
          purchaseOrdersApi.list({
            status: 'approved',
            branch_id: selectedBranchId,
            page: 1,
            size: 1
          })
        )
      });
    }

    if (loadOrderReceiving) {
      jobs.push(
        {
          key: 'orderReceiving',
          request: totalOf(
            purchaseOrdersApi.list({
              status: 'sent',
              branch_id: selectedBranchId,
              page: 1,
              size: 1
            })
          )
        },
        {
          key: 'orderPartial',
          request: totalOf(
            purchaseOrdersApi.list({
              status: 'partially_received',
              branch_id: selectedBranchId,
              page: 1,
              size: 1
            })
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
            branch_id: selectedBranchId ?? undefined,
            page: 1,
            size: 1
          })
        )
      });
    }

    if (loadRetaceoDraft) {
      jobs.push({
        key: 'retaceoDraft',
        request: totalOf(
          retaceosApi.list({
            status: 'draft',
            branch_id: selectedBranchId ?? undefined,
            page: 1,
            size: 1
          })
        )
      });
    }

    if (loadRetaceoCalculated) {
      jobs.push({
        key: 'retaceoCalculated',
        request: totalOf(
          retaceosApi.list({
            status: 'calculated',
            branch_id: selectedBranchId ?? undefined,
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

{#if cards.length > 0}
  <section class="mb-6 space-y-3" aria-labelledby="procurement-queue-title">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 id="procurement-queue-title" class="text-base font-semibold text-foreground">
          Cola de compras
        </h2>
        <p class="text-sm text-foreground-muted">
          Los conteos respetan la empresa, tus permisos y el alcance de sucursal: {branch.label}.
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

    <details class="rounded-xl border border-border bg-surface/50 p-3">
      <summary class="min-h-10 cursor-pointer rounded-md text-sm font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        Ver recorrido completo: de la solicitud al retaceo
      </summary>
      <ol class="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {#each workflowSteps as step, index (step.title)}
          <li class="flex gap-3 rounded-lg border border-border bg-surface p-3">
            <span class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              {String(index + 1).padStart(2, '0')}
            </span>
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-foreground">{step.title}</h3>
              <p class="mt-1 text-xs leading-5 text-foreground-muted">{step.text}</p>
            </div>
          </li>
        {/each}
      </ol>
      <p class="mt-3 text-xs text-foreground-muted">
        Las acciones disponibles dependen de los permisos del perfil y de la sucursal operativa seleccionada arriba.
      </p>
    </details>

    <div class="space-y-5">
      {#each cardGroups as group (group.label)}
        <details
          open={group.label === 'Solicitudes' || group.label === 'Cotizaciones'}
          class="queue-group rounded-xl border border-border bg-surface/50 p-3"
        >
          <summary class="flex min-h-10 cursor-pointer list-none items-center justify-between gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
            <span class="flex min-w-0 items-center gap-2">
              <span class="text-sm font-semibold text-foreground">{group.label}</span>
              <span class="text-xs text-foreground-muted" aria-live="polite">{group.countText}</span>
            </span>
            <span class="queue-chevron shrink-0 text-foreground-muted" aria-hidden="true">⌄</span>
          </summary>
          <div
            class="mt-3 grid gap-3"
            style="grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr));"
          >
            {#each group.cards as card (card.key)}
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
                    <span class="text-sm font-semibold leading-5 text-foreground">{card.title}</span>
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
        </details>
      {/each}
    </div>
  </section>
{/if}

<style>
  .queue-count {
    animation: queue-count-in 180ms ease-out;
  }

  .queue-group > summary::-webkit-details-marker { display: none; }
  .queue-chevron { transition: transform 160ms ease-out; }
  .queue-group[open] .queue-chevron { transform: rotate(180deg); }

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
    .queue-count, .queue-chevron {
      animation: none;
      transition: none;
    }
  }
</style>
