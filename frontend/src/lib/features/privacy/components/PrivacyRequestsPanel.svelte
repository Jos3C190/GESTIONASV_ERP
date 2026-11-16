<script lang="ts">
  import { onMount } from 'svelte';
  import AsyncSmartSelect, {
    type AsyncSmartOption
  } from '#lib/components/ui/AsyncSmartSelect.svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import PrivacyEmptyState from './PrivacyEmptyState.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { customersApi } from '#lib/api/customers.ts';
  import { privacyApi } from '#lib/api/privacy.ts';
  import {
    ACTION_LABELS,
    ACTION_TEXT,
    ACTIONS_BY_STATUS,
    RIGHT_LABELS,
    STATUS_LABELS,
    STATUS_TONES,
    formatDay,
    todayInElSalvador
  } from '#lib/features/privacy/labels.ts';
  import { confirmation } from '#lib/stores/confirmation.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type {
    RequestAction,
    RightType,
    SubjectRequest,
    SubjectRequestInput,
    UserOption
  } from '#lib/types/privacy.ts';

  let { canManage }: { canManage: boolean } = $props();

  const RIGHTS = Object.keys(RIGHT_LABELS) as RightType[];
  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';
  const labelClass = 'mb-1 block text-sm font-medium text-foreground';

  let scope = $state<'open' | 'closed' | 'all'>('open');
  let requests = $state<SubjectRequest[]>([]);
  let users = $state<UserOption[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let notice = $state<string | null>(null);

  let createOpen = $state(false);
  let form = $state<SubjectRequestInput>(blank());
  let creating = $state(false);
  let createError = $state<string | null>(null);
  let customerLabel = $state('');

  let selected = $state<SubjectRequest | null>(null);
  let pendingAction = $state<RequestAction | null>(null);
  let actionText = $state('');
  let acting = $state(false);
  let actionError = $state<string | null>(null);

  const canErase = $derived(permissions.hasPermission('privacy:erase'));

  function blank(): SubjectRequestInput {
    return {
      customer_id: null,
      requester_name: '',
      requester_document: null,
      response_channel: '',
      right_type: 'access',
      description: '',
      received_on: todayInElSalvador(),
      assignee_id: null
    };
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      requests = await privacyApi.requests(scope);
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar las solicitudes.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void load();
    if (canManage) {
      privacyApi.assigneeOptions().then(
        (items) => (users = items),
        () => (users = [])
      );
    }
  });

  async function searchCustomers(query: string): Promise<AsyncSmartOption[]> {
    const page = await customersApi.list({ search: query, active: null, size: 20 });
    return page.items.map((c) => ({ value: c.id, label: `${c.code} · ${c.name}` }));
  }

  function openCreate() {
    form = blank();
    customerLabel = '';
    createError = null;
    createOpen = true;
  }

  async function create(event: SubmitEvent) {
    event.preventDefault();
    creating = true;
    createError = null;
    try {
      const created = await privacyApi.createRequest(form);
      createOpen = false;
      notice = `Se registró la solicitud ${created.code}; vence el ${formatDay(created.due_on)}.`;
      scope = 'open';
      await load();
    } catch (cause) {
      createError =
        cause instanceof HttpError ? cause.message : 'No se pudo registrar la solicitud.';
    } finally {
      creating = false;
    }
  }

  function chooseAction(action: RequestAction) {
    pendingAction = action;
    actionText = '';
    actionError = null;
  }

  async function confirmAction() {
    if (!selected || !pendingAction) return;
    acting = true;
    actionError = null;
    const isExtension = pendingAction === 'extend';
    try {
      selected = await privacyApi.actOnRequest(selected.id, {
        action: pendingAction,
        text: isExtension ? null : actionText,
        extension_reason: isExtension ? actionText : null
      });
      pendingAction = null;
      await load();
    } catch (cause) {
      actionError = cause instanceof HttpError ? cause.message : 'No se pudo aplicar la acción.';
    } finally {
      acting = false;
    }
  }

  async function assign(assigneeId: string) {
    if (!selected) return;
    selected = await privacyApi.assignRequest(selected.id, assigneeId || null);
    await load();
  }

  async function downloadExport(request: SubjectRequest) {
    if (!request.customer_id) return;
    const data = await privacyApi.exportCustomer(request.customer_id);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `datos-${request.code}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function anonymize(request: SubjectRequest) {
    if (!request.customer_id) return;
    const customerId = request.customer_id;
    confirmation.request({
      kind: 'delete',
      title: 'Anonimizar al cliente',
      description:
        'Se borran su identidad, contacto, dirección y direcciones de entrega, se revocan sus consentimientos y se desactiva. No se puede deshacer. Los documentos fiscales emitidos se conservan.',
      resourceName: request.customer_name ?? request.requester_name,
      confirmLabel: 'Anonimizar',
      execute: async () => {
        await privacyApi.anonymizeCustomer(customerId, request.id);
        notice = `Se anonimizó al cliente de la solicitud ${request.code}. Registra la respuesta para cerrarla.`;
        await load();
      }
    });
  }
</script>

<section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
  <div
    class="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-start sm:justify-between"
  >
    <div>
      <h2 class="font-semibold text-foreground">Solicitudes de titulares</h2>
      <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
        Derechos de acceso, rectificación, cancelación, oposición, portabilidad, olvido y
        limitación. Se responden en 20 días hábiles, prorrogables una vez por otros 20.
      </p>
    </div>
    <div class="flex shrink-0 gap-2">
      <label class="sr-only" for="request-scope">Mostrar</label>
      <select
        id="request-scope"
        value={scope}
        onchange={(e) => {
          scope = e.currentTarget.value as typeof scope;
          void load();
        }}
        class="{inputClass} w-auto"
      >
        <option value="open">En trámite</option>
        <option value="closed">Cerradas</option>
        <option value="all">Todas</option>
      </select>
      {#if canManage && (loading || loadError || requests.length > 0)}
        <Button onclick={openCreate}>Registrar solicitud</Button>
      {/if}
    </div>
  </div>

  {#if notice}
    <p
      class="m-4 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success"
      role="status"
    >
      {notice}
    </p>
  {/if}

  {#if loading}
    <div class="space-y-3 p-4" aria-busy="true">
      <p class="sr-only" role="status">Cargando solicitudes…</p>
      <div class="skeleton h-14 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
      <div class="skeleton h-14 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
    </div>
  {:else if loadError}
    <div
      class="m-4 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else if requests.length === 0}
    <PrivacyEmptyState
      icon="M4 13h4l2 3h4l2-3h4 M4 13l2-8h12l2 8v6H4z"
      message={scope === 'open'
        ? 'No hay solicitudes en trámite.'
        : 'No hay solicitudes en esta vista.'}
      detail="Registra aquí cada pedido de un titular para controlar su plazo de respuesta."
    >
      {#snippet action()}
        {#if canManage}
          <Button variant="secondary" onclick={openCreate}>Registrar solicitud</Button>
        {/if}
      {/snippet}
    </PrivacyEmptyState>
  {:else}
    <ul class="divide-y divide-border">
      {#each requests as request (request.id)}
        <li>
          <button
            type="button"
            class="flex w-full flex-col gap-1 p-4 text-left hover:bg-surface-muted/40 sm:flex-row sm:items-center sm:justify-between"
            onclick={() => {
              selected = request;
              pendingAction = null;
            }}
          >
            <span class="min-w-0">
              <span class="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                <span class="font-mono">{request.code}</span>
                {RIGHT_LABELS[request.right_type]}
                <Badge variant={STATUS_TONES[request.status]}>{STATUS_LABELS[request.status]}</Badge
                >
                {#if request.overdue}<Badge variant="danger">Vencida</Badge>{/if}
              </span>
              <span class="block truncate text-sm text-foreground-muted">
                {request.requester_name}{request.assignee_name ? ` · ${request.assignee_name}` : ''}
              </span>
            </span>
            <span class="text-xs text-foreground-muted">
              Vence el {formatDay(request.effective_due_on)}
            </span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<Modal
  open={createOpen}
  title="Registrar solicitud de titular"
  onclose={() => (createOpen = false)}
  size="lg"
>
  <form class="space-y-4" onsubmit={create}>
    {#if createError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {createError}
      </p>
    {/if}
    <div class="grid gap-4 sm:grid-cols-2">
      <div>
        <label for="request-right" class={labelClass}>Derecho</label>
        <select id="request-right" bind:value={form.right_type} class={inputClass}>
          {#each RIGHTS as right (right)}
            <option value={right}>{RIGHT_LABELS[right]}</option>
          {/each}
        </select>
      </div>
      <div>
        <label for="request-received" class={labelClass}>Recibida el</label>
        <input
          id="request-received"
          type="date"
          bind:value={form.received_on}
          max={todayInElSalvador()}
          required
          class={inputClass}
        />
      </div>
      <div>
        <label for="request-name" class={labelClass}>Titular</label>
        <input
          id="request-name"
          bind:value={form.requester_name}
          required
          minlength="3"
          maxlength="200"
          class={inputClass}
        />
      </div>
      <div>
        <label for="request-document" class={labelClass}>Documento del titular</label>
        <input
          id="request-document"
          value={form.requester_document ?? ''}
          oninput={(e) => (form.requester_document = e.currentTarget.value || null)}
          maxlength="30"
          class={inputClass}
        />
      </div>
      <div class="sm:col-span-2">
        <label for="request-channel" class={labelClass}>Medio para responder</label>
        <input
          id="request-channel"
          bind:value={form.response_channel}
          required
          minlength="3"
          maxlength="200"
          placeholder="Correo, teléfono o dirección que indicó el titular"
          class={inputClass}
        />
      </div>
      <div class="sm:col-span-2">
        <AsyncSmartSelect
          id="request-customer"
          label="Cliente relacionado (si lo es)"
          value={form.customer_id ?? ''}
          placeholder="Buscar cliente…"
          selectedLabel={customerLabel}
          onselect={(value, option) => {
            form.customer_id = value || null;
            customerLabel = option?.label ?? '';
          }}
          loadOptions={searchCustomers}
        />
      </div>
      <div class="sm:col-span-2">
        <label for="request-description" class={labelClass}>Qué pide el titular</label>
        <textarea
          id="request-description"
          bind:value={form.description}
          required
          minlength="5"
          rows="3"
          class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        ></textarea>
      </div>
      <div class="sm:col-span-2">
        <label for="request-assignee" class={labelClass}>Responsable</label>
        <select
          id="request-assignee"
          value={form.assignee_id ?? ''}
          onchange={(e) => (form.assignee_id = e.currentTarget.value || null)}
          class={inputClass}
        >
          <option value="">Sin asignar</option>
          {#each users as user (user.id)}
            <option value={user.id}>{user.name}</option>
          {/each}
        </select>
      </div>
    </div>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (createOpen = false)}>Cancelar</Button>
      <Button type="submit" disabled={creating}>{creating ? 'Registrando…' : 'Registrar'}</Button>
    </div>
  </form>
</Modal>

<Modal
  open={selected !== null}
  title={selected ? `Solicitud ${selected.code}` : ''}
  onclose={() => (selected = null)}
  size="lg"
>
  {#if selected}
    <div class="space-y-4 text-sm">
      <div class="flex flex-wrap items-center gap-2">
        <Badge variant={STATUS_TONES[selected.status]}>{STATUS_LABELS[selected.status]}</Badge>
        <span class="text-foreground">{RIGHT_LABELS[selected.right_type]}</span>
        {#if selected.overdue}<Badge variant="danger">Vencida</Badge>{/if}
      </div>
      <dl class="grid gap-3 sm:grid-cols-2">
        <div>
          <dt class="text-xs text-foreground-muted">Titular</dt>
          <dd>
            {selected.requester_name}
            {selected.requester_document ? `(${selected.requester_document})` : ''}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Responder por</dt>
          <dd class="break-words">{selected.response_channel}</dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Recibida</dt>
          <dd>{formatDay(selected.received_on)}</dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">Vence</dt>
          <dd>
            {formatDay(selected.effective_due_on)}{selected.extended_due_on ? ' (prorrogada)' : ''}
          </dd>
        </div>
        {#if selected.correction_due_on}
          <div>
            <dt class="text-xs text-foreground-muted">Plazo para corregir</dt>
            <dd>{formatDay(selected.correction_due_on)}</dd>
          </div>
        {/if}
        {#if selected.customer_name}
          <div>
            <dt class="text-xs text-foreground-muted">Cliente</dt>
            <dd>{selected.customer_name}</dd>
          </div>
        {/if}
      </dl>
      <p class="whitespace-pre-wrap rounded-lg bg-surface-muted/50 p-3">{selected.description}</p>
      {#if selected.extension_reason}
        <p class="text-foreground-muted">
          <span class="font-medium text-foreground">Prórroga:</span>
          {selected.extension_reason}
        </p>
      {/if}
      {#if selected.resolution}
        <p class="whitespace-pre-wrap">
          <span class="font-medium">Respuesta:</span>
          {selected.resolution}
        </p>
      {/if}

      {#if canManage && ACTIONS_BY_STATUS[selected.status].length > 0}
        <div class="space-y-3 border-t border-border pt-4">
          <div>
            <label for="request-assign" class={labelClass}>Responsable</label>
            <select
              id="request-assign"
              value={selected.assignee_id ?? ''}
              onchange={(e) => void assign(e.currentTarget.value)}
              class={inputClass}
            >
              <option value="">Sin asignar</option>
              {#each users as user (user.id)}
                <option value={user.id}>{user.name}</option>
              {/each}
            </select>
          </div>
          {#if selected.customer_id}
            <div class="flex flex-wrap gap-2">
              {#if ['access', 'portability'].includes(selected.right_type)}
                <Button
                  variant="secondary"
                  size="sm"
                  onclick={() => selected && void downloadExport(selected)}
                >
                  Descargar datos del cliente
                </Button>
              {/if}
              {#if canErase && ['cancellation', 'erasure'].includes(selected.right_type) && selected.status !== 'awaiting_correction'}
                <Button variant="danger" size="sm" onclick={() => selected && anonymize(selected)}>
                  Anonimizar al cliente
                </Button>
              {/if}
            </div>
          {/if}
          <div class="flex flex-wrap gap-2">
            {#each ACTIONS_BY_STATUS[selected.status] as action (action)}
              <Button
                variant={pendingAction === action ? 'primary' : 'secondary'}
                size="sm"
                onclick={() => chooseAction(action)}
              >
                {ACTION_LABELS[action]}
              </Button>
            {/each}
          </div>
          {#if pendingAction}
            <div class="space-y-2 rounded-lg border border-border p-3">
              {#if actionError}
                <p class="text-sm text-danger" role="alert">{actionError}</p>
              {/if}
              {#if ACTION_TEXT[pendingAction]}
                <label for="request-action-text" class={labelClass}
                  >{ACTION_TEXT[pendingAction]}</label
                >
                <textarea
                  id="request-action-text"
                  bind:value={actionText}
                  rows="3"
                  class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                ></textarea>
              {/if}
              <div class="flex justify-end gap-2">
                <Button variant="ghost" size="sm" onclick={() => (pendingAction = null)}
                  >Cancelar</Button
                >
                <Button size="sm" disabled={acting} onclick={() => void confirmAction()}>
                  {acting ? 'Aplicando…' : ACTION_LABELS[pendingAction]}
                </Button>
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</Modal>
