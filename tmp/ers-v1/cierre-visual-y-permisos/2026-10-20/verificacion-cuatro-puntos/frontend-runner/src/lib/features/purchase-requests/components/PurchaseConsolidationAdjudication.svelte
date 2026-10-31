<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { api, HttpError } from '$lib/api/client';
  import { purchaseConsolidationsApi } from '$lib/api/purchase-consolidations';
  import { suppliersApi } from '$lib/api/suppliers';
  import { permissions } from '$lib/stores/permissions.svelte';
  import PurchaseConsolidationAwardLineView from './PurchaseConsolidationAwardLine.svelte';
  import { formatQuantity } from '../adjudication-formatters';
  import type {
    PurchaseConsolidationAwardBoard,
    PurchaseConsolidationAwardDecision,
    PurchaseConsolidationAwardLine as AwardLine,
    PurchaseConsolidationAwardOffer,
    PurchaseConsolidationStatus
  } from '$lib/types/purchase-consolidation';

  let { consolidationId, status }: { consolidationId: string; status: PurchaseConsolidationStatus } = $props();

  let board = $state<PurchaseConsolidationAwardBoard | null>(null);
  let supplierNames = $state<Record<number, string>>({});
  let actorNames = $state<Record<string, string>>({});
  let loading = $state(true);
  let savingKey = $state<string | null>(null);
  let error = $state<string | null>(null);
  let success = $state<{ targetId: string; message: string } | null>(null);
  let generation = 0;

  const canRead = $derived(
    permissions.hasPermission('purchase_requests:read') &&
      permissions.hasPermission('purchase_quotations:read')
  );
  const canAward = $derived(
    status !== 'closed' && status !== 'cancelled' && permissions.hasPermission('purchase_quotations:select')
  );
  const canCreateOrders = $derived(permissions.hasPermission('purchase_orders:manage'));

  let orderableQuotations = $derived.by(() => {
    if (!board) return [];
    const groups = new Map<
      string,
      { id: string; code: string; supplierId: number; awardCount: number }
    >();
    for (const line of board.lines) {
      for (const decision of line.decisions) {
        const remaining = toScaledQuantity(decision.remaining_to_order_quantity);
        if (decision.revoked_at || remaining === null || remaining <= 0n) continue;
        const current = groups.get(decision.quotation_id);
        if (current) {
          current.awardCount += 1;
        } else {
          groups.set(decision.quotation_id, {
            id: decision.quotation_id,
            code: decision.quotation_code,
            supplierId: decision.supplier_id,
            awardCount: 1
          });
        }
      }
    }
    return [...groups.values()];
  });

  function message(cause: unknown) {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo cargar la comparación de ofertas.';
  }

  async function load() {
    const current = ++generation;
    loading = true;
    error = null;
    try {
      const result = await purchaseConsolidationsApi.getAwardBoard(consolidationId);
      if (current === generation) {
        board = result;
        const supplierIds = [
          ...new Set(result.lines.flatMap((line) => line.offers.map((offer) => offer.supplier_id)))
        ];
        const names = await Promise.all(
          supplierIds.map(async (supplierId) => {
            const supplier = await suppliersApi.getSupplier(supplierId).catch(() => null);
            return [supplierId, supplier?.name ?? `Proveedor #${supplierId}`] as const;
          })
        );
        if (current === generation) {
          supplierNames = Object.fromEntries(names);
          const currentUser = await api.auth.me().catch(() => null);
          const readableActorIds = permissions.hasPermission('users:read')
            ? [
                ...new Set(
                  result.lines.flatMap((line) =>
                    line.decisions.flatMap((decision) => [
                      decision.decided_by_id,
                      ...(decision.revoked_by_id ? [decision.revoked_by_id] : [])
                    ])
                  )
                )
              ].filter((id) => id !== currentUser?.id)
            : [];
          const actors = await Promise.all(
            readableActorIds.map(async (id) => {
              const user = await api.users.get(id).catch(() => null);
              return user ? ([id, user.username] as const) : null;
            })
          );
          if (current === generation) {
            actorNames = Object.fromEntries([
              ...(currentUser ? [[currentUser.id, currentUser.username] as const] : []),
              ...actors.filter((actor): actor is readonly [string, string] => actor !== null)
            ]);
          }
        }
      }
    } catch (cause: unknown) {
      if (current !== generation) return;
      error = message(cause);
      board = null;
    } finally {
      if (current === generation) loading = false;
    }
  }

  function toScaledQuantity(value: string): bigint | null {
    const normalized = value.trim();
    if (!/^\d+(?:\.\d{1,6})?$/.test(normalized)) return null;
    const [whole, fraction = ''] = normalized.split('.');
    return BigInt(whole ?? '0') * 1_000_000n + BigInt(fraction.padEnd(6, '0'));
  }

  async function submitAward(
    line: AwardLine,
    offer: PurchaseConsolidationAwardOffer,
    quantity: string,
    rawReason: string
  ): Promise<boolean> {
    if (savingKey) return false;
    const reason = rawReason.trim();
    const quantityScaled = toScaledQuantity(quantity);
    const lineCap = toScaledQuantity(line.remaining_quantity);
    const offerCap = toScaledQuantity(offer.remaining_offer_quantity);
    if (quantityScaled === null || quantityScaled <= 0n) {
      error = 'Escribe una cantidad mayor que cero, con hasta seis decimales.';
      return false;
    }
    if (
      lineCap === null ||
      offerCap === null ||
      quantityScaled > lineCap ||
      quantityScaled > offerCap
    ) {
      error = 'La cantidad supera lo que queda de la demanda o de la oferta.';
      return false;
    }
    if (!reason) {
      error = 'Escribe el motivo de esta adjudicación.';
      return false;
    }

    const key = `${line.id}:${offer.quotation_detail_id}`;
    savingKey = key;
    error = null;
    success = null;
    try {
      board = await purchaseConsolidationsApi.award(consolidationId, {
        consolidation_line_id: line.id,
        quotation_id: offer.quotation_id,
        quotation_detail_id: offer.quotation_detail_id,
        quantity,
        reason
      });
      success = {
        targetId: key,
        message: `Adjudicación registrada: ${formatQuantity(quantity)} ${line.unit_name} para ${supplierNames[offer.supplier_id] ?? `Proveedor #${offer.supplier_id}`}.`
      };
      return true;
    } catch (cause: unknown) {
      error = message(cause);
      return false;
    } finally {
      savingKey = null;
    }
  }

  async function submitRevoke(
    decision: PurchaseConsolidationAwardDecision,
    rawReason: string
  ): Promise<boolean> {
    if (!board || savingKey) return false;
    const reason = rawReason.trim();
    if (!reason) {
      error = 'Escribe por qué necesitas revertir esta adjudicación.';
      return false;
    }
    const decisionUnit =
      board.lines.find((line) => line.decisions.some((item) => item.id === decision.id))
        ?.unit_name ?? 'unidades';
    savingKey = decision.id;
    error = null;
    success = null;
    try {
      board = await purchaseConsolidationsApi.revokeAward(consolidationId, decision.id, reason);
      success = {
        targetId: decision.id,
        message: `Se revirtió la adjudicación de ${formatQuantity(decision.quantity)} ${decisionUnit}; quedó registrada en el historial.`
      };
      return true;
    } catch (cause: unknown) {
      error = message(cause);
      return false;
    } finally {
      savingKey = null;
    }
  }

  $effect(() => {
    const id = consolidationId;
    if (id && canRead) void load();
    else loading = false;
  });
</script>

{#if canRead}
  <section aria-labelledby="adjudication-title">
    <Card class="mb-4 overflow-hidden p-0">
      <div class="border-b border-border p-4 sm:p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="adjudication-title" class="text-lg font-semibold text-foreground">
              Comparar y adjudicar por producto
            </h2>
            <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
              Revisa las respuestas recibidas y asigna cada cantidad al proveedor elegido. Puedes
              dividir un producto entre varias ofertas.
            </p>
          </div>
          {#if canAward}
            <span
              class="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary"
              >Decisión manual</span
            >
          {/if}
        </div>
        {#if board && board.currencies.length > 0}
          <div
            class="mt-4 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2.5 text-sm text-foreground-muted"
            role="note"
          >
            Monedas de las ofertas: <strong class="text-foreground"
              >{board.currencies.join(', ')}</strong
            >. Los importes se muestran en su moneda original; el sistema no hace conversión ni
            ordena proveedores automáticamente.
          </div>
        {/if}
        {#if status === 'closed'}
          <p class="mt-4 rounded-lg border border-success/25 bg-success/5 px-3 py-2.5 text-sm text-foreground-muted" role="status">
            Consolidación cerrada. Las decisiones registradas se muestran en modo de consulta.
          </p>
        {/if}
        {#if canCreateOrders && orderableQuotations.length > 0}
          <div class="mt-4 rounded-lg border border-primary/20 bg-primary/5 p-3 sm:p-4">
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h3 class="text-sm font-semibold text-foreground">Órdenes por cotización</h3>
                <p class="mt-1 text-xs text-foreground-muted">
                  Cada borrador corresponde a una cotización. Si un proveedor tiene varias
                  cotizaciones adjudicadas, se crea un borrador por cada una; solo incluirá las
                  cantidades que aún no están en otra orden.
                </p>
              </div>
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              {#each orderableQuotations as item (item.id)}
                <a
                  href={`/purchase-orders/new?quotation_id=${encodeURIComponent(item.id)}&consolidation_id=${encodeURIComponent(consolidationId)}`}
                  class="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-surface hover:bg-foreground-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  Crear orden · {item.code} · {supplierNames[item.supplierId] ??
                    `Proveedor #${item.supplierId}`}
                  <span class="rounded-full bg-black/10 px-2 py-0.5 text-xs">
                    {item.awardCount}
                    {item.awardCount === 1 ? 'adjudicación' : 'adjudicaciones'}
                  </span>
                </a>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      {#if error}
        <div
          class="flex flex-wrap items-center justify-between gap-3 border-b border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
          role="alert"
        >
          <span>{error}</span>
          <Button
            size="sm"
            variant="secondary"
            class="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            onclick={() => void load()}>Actualizar</Button
          >
        </div>
      {/if}

      {#if loading}
        <div class="space-y-3 p-4" role="status" aria-label="Cargando comparación de ofertas">
          <div class="skeleton h-20 rounded-lg"></div>
          <div class="skeleton h-20 rounded-lg"></div>
        </div>
      {:else if !board}
        <div class="flex flex-wrap items-center justify-between gap-3 p-4">
          <p class="text-sm text-foreground-muted">No fue posible cargar la comparación.</p>
          <Button
            size="sm"
            variant="secondary"
            class="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            onclick={() => void load()}>Reintentar</Button
          >
        </div>
      {:else if board.lines.length === 0}
        <p class="p-5 text-sm text-foreground-muted">
          Este consolidado todavía no tiene productos.
        </p>
      {:else}
        <div class="divide-y divide-border">
          {#each board.lines as line (line.id)}
            <PurchaseConsolidationAwardLineView
              {line}
              {supplierNames}
              {actorNames}
              {canAward}
              {savingKey}
              {success}
              onAward={submitAward}
              onRevoke={submitRevoke}
            />
          {/each}
        </div>
      {/if}
    </Card>
  </section>
{:else}
  <section aria-labelledby="adjudication-permission-title">
    <Card class="mb-4 p-4">
      <h2 id="adjudication-permission-title" class="font-semibold text-foreground">
        Comparación y adjudicación
      </h2>
      <p class="mt-1 text-sm text-foreground-muted" role="status">
        Tu perfil no tiene permiso para consultar las solicitudes y cotizaciones de este
        consolidado.
      </p>
    </Card>
  </section>
{/if}
