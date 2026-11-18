<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalApi } from '#lib/api/fiscal.ts';
  import { contingenciesApi } from '#lib/api/sales-contingencies.ts';
  import {
    CONTINGENCY_STATUS_BADGES,
    CONTINGENCY_STATUS_LABELS,
    CONTINGENCY_TYPE_LABELS,
    RESPONSIBLE_DOCUMENT_LABELS,
    formatMoment
  } from '#lib/features/sales/fiscal-labels.ts';
  import { confirmation } from '#lib/stores/confirmation.svelte.ts';
  import type { Establishment } from '#lib/types/fiscal.ts';
  import type { ContingencyOverview, ContingencyWindow } from '#lib/types/sales-contingencies.ts';

  let { canOperate }: { canOperate: boolean } = $props();

  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  let overview = $state<ContingencyOverview | null>(null);
  let establishments = $state<Establishment[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busy = $state(false);

  let activating = $state(false);
  let establishmentId = $state('');
  let contingencyType = $state('2');
  let reason = $state('');

  let responsibleName = $state('');
  let responsibleType = $state('13');
  let responsibleNumber = $state('');
  let savingResponsible = $state(false);
  let responsibleMessage = $state<string | null>(null);

  const openWindows = $derived(
    (overview?.windows ?? []).filter((item) => item.status !== 'COMPLETADA')
  );
  const history = $derived(
    (overview?.windows ?? []).filter((item) => item.status === 'COMPLETADA')
  );
  const activeEstablishments = $derived(establishments.filter((item) => item.is_active));

  function message(cause: unknown, fallback: string): string {
    return cause instanceof HttpError ? cause.message : fallback;
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      const [current, list] = await Promise.all([
        contingenciesApi.overview(),
        fiscalApi.listEstablishments()
      ]);
      overview = current;
      establishments = list;
      if (current.responsible) {
        responsibleName = current.responsible.name;
        responsibleType = current.responsible.document_type;
        responsibleNumber = current.responsible.document_number;
      }
    } catch (cause) {
      loadError = message(cause, 'No se pudo cargar la contingencia de la empresa.');
    } finally {
      loading = false;
    }
  }
  onMount(() => void load());

  async function activate(event: SubmitEvent) {
    event.preventDefault();
    if (busy) return;
    busy = true;
    actionError = null;
    notice = null;
    try {
      const entry = await contingenciesApi.activate({
        establishment_id: establishmentId,
        contingency_type: Number(contingencyType),
        reason: reason.trim() || null
      });
      notice = `Contingencia activa en ${entry.branch_name ?? entry.establishment_code}. Los documentos de ese establecimiento se generan sin conexión con Hacienda.`;
      activating = false;
      reason = '';
      await load();
    } catch (cause) {
      actionError = message(cause, 'No se pudo activar la contingencia.');
    } finally {
      busy = false;
    }
  }

  function where(entry: ContingencyWindow): string {
    return entry.branch_name
      ? `${entry.branch_name} (${entry.establishment_code})`
      : (entry.establishment_code ?? 'Establecimiento');
  }

  function close(entry: ContingencyWindow) {
    confirmation.request({
      kind: 'confirm',
      title: 'Cerrar la contingencia',
      description: overview?.responsible
        ? `Cierra la contingencia de ${where(entry)} cuando la comunicación se haya restablecido. Se informará el evento a Hacienda y se transmitirán sus ${entry.documents.total} documento(s).`
        : `Cierra la contingencia de ${where(entry)}. Sin un responsable registrado el evento no se informa: regístralo para enviarlo.`,
      confirmLabel: 'Cerrar contingencia',
      execute: async () => {
        actionError = null;
        notice = null;
        const result = await contingenciesApi.close(entry.id);
        notice =
          result.status === 'CERRADA'
            ? `Se cerró la contingencia de ${where(entry)}; falta informar el evento.`
            : `Se cerró la contingencia de ${where(entry)} y se informó el evento.`;
        await load();
      }
    });
  }

  async function sendEvent(entry: ContingencyWindow) {
    if (busy) return;
    busy = true;
    actionError = null;
    notice = null;
    try {
      const result = await contingenciesApi.sendEvent(entry.id);
      notice =
        result.last_error && result.status === 'CERRADA'
          ? `Hacienda no recibió el evento: ${result.last_error}`
          : `Se informó el evento de ${where(entry)}.`;
      await load();
    } catch (cause) {
      actionError = message(cause, 'No se pudo informar el evento.');
    } finally {
      busy = false;
    }
  }

  async function saveResponsible(event: SubmitEvent) {
    event.preventDefault();
    if (savingResponsible) return;
    savingResponsible = true;
    responsibleMessage = null;
    actionError = null;
    try {
      const saved = await contingenciesApi.saveResponsible({
        name: responsibleName,
        document_type: responsibleType,
        document_number: responsibleNumber
      });
      if (overview) overview = { ...overview, responsible: saved };
      responsibleMessage = 'Se guardó el responsable fiscal.';
    } catch (cause) {
      actionError = message(cause, 'No se pudo guardar el responsable.');
    } finally {
      savingResponsible = false;
    }
  }
</script>

{#if loading}
  <div class="space-y-3" aria-busy="true">
    <p class="sr-only" role="status">Cargando la contingencia…</p>
    <div class="skeleton h-24 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
    <div class="skeleton h-48 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
  </div>
{:else if loadError || !overview}
  <div
    class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
    role="alert"
  >
    <span>{loadError ?? 'No se pudo cargar la contingencia de la empresa.'}</span>
    <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
  </div>
{:else}
  <div class="space-y-5">
    {#if actionError}
      <div
        class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {actionError}
      </div>
    {/if}
    {#if notice}
      <p
        class="rounded-lg border border-border bg-surface px-4 py-3 text-sm text-foreground"
        aria-live="polite"
      >
        {notice}
      </p>
    {/if}

    <section class="space-y-3 rounded-xl border border-border bg-surface p-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="font-semibold text-foreground">Establecimientos en contingencia</h2>
          <p class="text-sm text-foreground-muted">
            Si Hacienda no responde, la contingencia se activa sola. Actívala tú ante un corte de
            energía o de internet en la tienda: los documentos se generan sin conexión, el cliente
            recibe su PDF y se transmiten al cerrarla.
          </p>
        </div>
        {#if canOperate && !activating}
          <Button onclick={() => (activating = true)}>Activar contingencia</Button>
        {/if}
      </div>

      {#if activating}
        <form
          class="grid gap-4 rounded-lg border border-border bg-surface-muted p-4 sm:grid-cols-2"
          onsubmit={activate}
        >
          <label class="space-y-1 text-sm text-foreground-muted"
            >Establecimiento
            <select
              class={inputClass}
              value={establishmentId}
              onchange={(event) => (establishmentId = event.currentTarget.value)}
              required
            >
              <option value="" disabled>Elige el establecimiento</option>
              {#each activeEstablishments as item (item.id)}
                <option value={item.id}>{item.branch_name} ({item.code})</option>
              {/each}
            </select>
          </label>
          <label class="space-y-1 text-sm text-foreground-muted"
            >Tipo de contingencia
            <select
              class={inputClass}
              value={contingencyType}
              onchange={(event) => (contingencyType = event.currentTarget.value)}
            >
              {#each Object.entries(CONTINGENCY_TYPE_LABELS) as [value, label] (value)}
                <option {value}>{label}</option>
              {/each}
            </select>
          </label>
          <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
            >Motivo {contingencyType === '5' ? '(obligatorio)' : '(opcional)'}
            <textarea
              class="min-h-20 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              maxlength="500"
              value={reason}
              oninput={(event) => (reason = event.currentTarget.value)}
            ></textarea>
          </label>
          <div class="flex flex-wrap gap-2 sm:col-span-2">
            <Button type="submit" disabled={busy || !establishmentId}
              >{busy ? 'Activando…' : 'Activar'}</Button
            >
            <Button variant="secondary" onclick={() => (activating = false)}>Cancelar</Button>
          </div>
        </form>
      {/if}

      {#if openWindows.length === 0}
        <div class="flex flex-col items-center gap-2 py-6 text-center">
          <span
            class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-lg text-foreground-muted"
            aria-hidden="true">✓</span
          >
          <p class="font-medium text-foreground">
            Todos los establecimientos emiten con normalidad.
          </p>
          <p class="text-sm text-foreground-muted">
            No hay contingencias abiertas ni eventos por informar.
          </p>
        </div>
      {:else}
        <ul class="space-y-3">
          {#each openWindows as entry (entry.id)}
            <li class="space-y-2 rounded-lg border border-border p-4">
              <div class="flex flex-wrap items-start justify-between gap-2">
                <div class="min-w-0">
                  <p class="font-medium text-foreground">{where(entry)}</p>
                  <p class="text-sm text-foreground-muted">
                    {entry.contingency_label}{entry.reason ? ` · ${entry.reason}` : ''}
                  </p>
                </div>
                <span
                  class={`rounded-full px-2 py-1 text-xs ${CONTINGENCY_STATUS_BADGES[entry.status]}`}
                  >{CONTINGENCY_STATUS_LABELS[entry.status]}</span
                >
              </div>
              <dl class="grid gap-2 text-sm sm:grid-cols-3">
                <div>
                  <dt class="text-xs text-foreground-muted">Desde</dt>
                  <dd class="text-foreground">{formatMoment(entry.started_at)}</dd>
                </div>
                <div>
                  <dt class="text-xs text-foreground-muted">Documentos</dt>
                  <dd class="text-foreground">
                    {entry.documents.total} · {entry.documents.transmitted} transmitido(s){entry
                      .documents.rejected
                      ? ` · ${entry.documents.rejected} rechazado(s)`
                      : ''}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-foreground-muted">Plazo</dt>
                  <dd
                    class={entry.event_overdue || entry.transmission_overdue
                      ? 'text-danger'
                      : 'text-foreground'}
                  >
                    {#if entry.status === 'ACTIVA'}
                      Al cerrarla hay 24 h para informar el evento
                    {:else if entry.status === 'CERRADA'}
                      Evento hasta {formatMoment(entry.event_deadline)}{entry.event_overdue
                        ? ' (vencido)'
                        : ''}
                    {:else}
                      Transmitir hasta {formatMoment(
                        entry.transmission_deadline
                      )}{entry.transmission_overdue ? ' (vencido)' : ''}
                    {/if}
                  </dd>
                </div>
              </dl>
              {#if entry.last_error}
                <p
                  class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
                >
                  {entry.last_error}
                </p>
              {/if}
              {#if canOperate}
                <div class="flex flex-wrap gap-2">
                  {#if entry.status === 'ACTIVA'}
                    <Button variant="secondary" onclick={() => close(entry)}
                      >Cerrar contingencia</Button
                    >
                  {:else if entry.status === 'CERRADA'}
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onclick={() => void sendEvent(entry)}>Informar evento</Button
                    >
                  {/if}
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="space-y-3 rounded-xl border border-border bg-surface p-4">
      <div>
        <h2 class="font-semibold text-foreground">Responsable fiscal</h2>
        <p class="text-sm text-foreground-muted">
          Persona de la empresa que firma ante Hacienda los eventos de contingencia y las
          invalidaciones de documentos. Con un responsable registrado, el evento se informa solo al
          cerrarse la contingencia.
        </p>
      </div>
      {#if !overview.responsible}
        <p class="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
          Sin responsable fiscal registrado: no se pueden informar contingencias ni invalidar
          documentos.
        </p>
      {/if}
      <form class="grid gap-4 sm:grid-cols-3" onsubmit={saveResponsible}>
        <label class="space-y-1 text-sm text-foreground-muted sm:col-span-3"
          >Nombre
          <input
            class={inputClass}
            maxlength="100"
            value={responsibleName}
            oninput={(event) => (responsibleName = event.currentTarget.value)}
            disabled={!canOperate}
            required
          />
        </label>
        <label class="space-y-1 text-sm text-foreground-muted"
          >Tipo de documento
          <select
            class={inputClass}
            value={responsibleType}
            onchange={(event) => (responsibleType = event.currentTarget.value)}
            disabled={!canOperate}
          >
            {#each Object.entries(RESPONSIBLE_DOCUMENT_LABELS) as [value, label] (value)}
              <option {value}>{label}</option>
            {/each}
          </select>
        </label>
        <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
          >Número de documento
          <input
            class={inputClass}
            maxlength="25"
            value={responsibleNumber}
            oninput={(event) => (responsibleNumber = event.currentTarget.value)}
            disabled={!canOperate}
            required
          />
        </label>
        {#if canOperate}
          <div class="flex flex-wrap items-center gap-3 sm:col-span-3">
            <Button type="submit" disabled={savingResponsible}
              >{savingResponsible ? 'Guardando…' : 'Guardar responsable'}</Button
            >
            {#if responsibleMessage}
              <span class="text-sm text-success" aria-live="polite">{responsibleMessage}</span>
            {/if}
          </div>
        {/if}
      </form>
    </section>

    {#if history.length > 0}
      <section class="space-y-2 rounded-xl border border-border bg-surface p-4">
        <h2 class="font-semibold text-foreground">Contingencias recientes</h2>
        <ul class="divide-y divide-border text-sm">
          {#each history as entry (entry.id)}
            <li class="flex flex-wrap items-center justify-between gap-2 py-2">
              <span class="text-foreground">{where(entry)} · {entry.contingency_label}</span>
              <span class="text-foreground-muted"
                >{formatMoment(entry.started_at)} – {formatMoment(entry.ended_at)} · {entry
                  .documents.total} documento(s)</span
              >
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  </div>
{/if}
