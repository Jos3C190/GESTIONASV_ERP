<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import PrivacyEmptyState from './PrivacyEmptyState.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { HttpError } from '$lib/api/client';
  import { privacyApi } from '$lib/api/privacy';
  import { CHANNEL_LABELS, PURPOSE_LABELS, formatMoment } from '$lib/features/privacy/labels';
  import type { Channel, Consent, ConsentPurpose } from '$lib/types/privacy';

  let { customerId, canManage }: { customerId: string; canManage: boolean } = $props();

  const PURPOSES = Object.keys(PURPOSE_LABELS) as ConsentPurpose[];
  const CHANNELS = Object.keys(CHANNEL_LABELS) as Channel[];
  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let consents = $state<Consent[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);

  let grantOpen = $state(false);
  let purpose = $state<ConsentPurpose>('marketing');
  let channel = $state<Channel>('in_person');
  let notes = $state('');
  let saving = $state(false);
  let formError = $state<string | null>(null);

  let revoking = $state<Consent | null>(null);
  let revokeChannel = $state<Channel>('in_person');

  const active = $derived(consents.filter((c) => !c.revoked_at));
  const available = $derived(PURPOSES.filter((p) => !active.some((c) => c.purpose === p)));

  async function load() {
    loading = true;
    loadError = null;
    try {
      consents = await privacyApi.consents(customerId);
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar los consentimientos.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  function openGrant() {
    purpose = available[0] ?? 'marketing';
    channel = 'in_person';
    notes = '';
    formError = null;
    grantOpen = true;
  }

  async function grant(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    formError = null;
    try {
      await privacyApi.grantConsent(customerId, { purpose, channel, notes: notes.trim() || null });
      grantOpen = false;
      await load();
    } catch (cause) {
      formError =
        cause instanceof HttpError ? cause.message : 'No se pudo registrar el consentimiento.';
    } finally {
      saving = false;
    }
  }

  async function revoke(event: SubmitEvent) {
    event.preventDefault();
    if (!revoking) return;
    saving = true;
    formError = null;
    try {
      await privacyApi.revokeConsent(customerId, revoking.id, revokeChannel);
      revoking = null;
      await load();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo revocar.';
    } finally {
      saving = false;
    }
  }
</script>

<section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
  <div
    class="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-start sm:justify-between"
  >
    <div>
      <h2 class="font-semibold text-foreground">Consentimientos</h2>
      <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
        Usos de sus datos que no son necesarios para venderle ni facturarle. Solo se registran
        después de informarle el aviso de privacidad, y puede retirarlos cuando quiera.
      </p>
    </div>
    {#if canManage && !loading && !loadError && consents.length > 0 && available.length > 0}
      <Button class="shrink-0" variant="secondary" onclick={openGrant}
        >Registrar consentimiento</Button
      >
    {/if}
  </div>

  {#if loading}
    <div class="p-4" aria-busy="true">
      <p class="sr-only" role="status">Cargando consentimientos…</p>
      <div class="skeleton h-12 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
    </div>
  {:else if loadError}
    <div
      class="m-4 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else if consents.length === 0}
    <PrivacyEmptyState
      icon="M9 12l2 2 4-4 M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6z"
      message="El cliente no ha dado consentimientos."
      detail="Sin ellos no se le envían promociones ni se comparten sus datos."
    >
      {#snippet action()}
        {#if canManage}
          <Button class="shrink-0" variant="secondary" onclick={openGrant}
            >Registrar consentimiento</Button
          >
        {/if}
      {/snippet}
    </PrivacyEmptyState>
  {:else}
    <ul class="divide-y divide-border">
      {#each consents as consent (consent.id)}
        <li class="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0 text-sm">
            <p class="flex flex-wrap items-center gap-2 font-medium text-foreground">
              {PURPOSE_LABELS[consent.purpose]}
              {#if consent.revoked_at}
                <Badge variant="neutral">Revocado</Badge>
              {:else}
                <Badge variant="success">Vigente</Badge>
              {/if}
            </p>
            <p class="text-foreground-muted">
              {CHANNEL_LABELS[consent.channel]} · {formatMoment(consent.granted_at)} · aviso versión
              {consent.notice_version}
              {#if consent.revoked_at}
                · revocado el {formatMoment(consent.revoked_at)}
                {#if consent.revocation_channel}
                  ({CHANNEL_LABELS[consent.revocation_channel].toLowerCase()})
                {/if}
              {/if}
            </p>
          </div>
          {#if canManage && !consent.revoked_at}
            <Button
              variant="ghost"
              size="sm"
              onclick={() => {
                revoking = consent;
                revokeChannel = 'in_person';
                formError = null;
              }}>Revocar</Button
            >
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<Modal open={grantOpen} title="Registrar consentimiento" onclose={() => (grantOpen = false)}>
  <form class="space-y-4" onsubmit={grant}>
    {#if formError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {formError}
      </p>
    {/if}
    <div>
      <label for="consent-purpose" class="mb-1 block text-sm font-medium text-foreground"
        >Uso autorizado</label
      >
      <select id="consent-purpose" bind:value={purpose} class={inputClass}>
        {#each available as option (option)}
          <option value={option}>{PURPOSE_LABELS[option]}</option>
        {/each}
      </select>
    </div>
    <div>
      <label for="consent-channel" class="mb-1 block text-sm font-medium text-foreground"
        >Cómo lo dio</label
      >
      <select id="consent-channel" bind:value={channel} class={inputClass}>
        {#each CHANNELS as option (option)}
          <option value={option}>{CHANNEL_LABELS[option]}</option>
        {/each}
      </select>
    </div>
    <div>
      <label for="consent-notes" class="mb-1 block text-sm font-medium text-foreground"
        >Nota (opcional)</label
      >
      <input id="consent-notes" bind:value={notes} maxlength="500" class={inputClass} />
    </div>
    <p class="text-xs text-foreground-muted">
      Se guarda la versión vigente del aviso de privacidad que se le informó.
    </p>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (grantOpen = false)}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Registrar'}</Button>
    </div>
  </form>
</Modal>

<Modal open={revoking !== null} title="Revocar consentimiento" onclose={() => (revoking = null)}>
  <form class="space-y-4" onsubmit={revoke}>
    {#if formError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {formError}
      </p>
    {/if}
    <p class="text-sm text-foreground">
      {revoking ? PURPOSE_LABELS[revoking.purpose] : ''}: el cliente deja de autorizar este uso.
      Debe dejar de aplicarse en un máximo de 5 días hábiles.
    </p>
    <div>
      <label for="revoke-channel" class="mb-1 block text-sm font-medium text-foreground"
        >Cómo lo pidió</label
      >
      <select
        id="revoke-channel"
        value={revokeChannel}
        onchange={(e) => (revokeChannel = e.currentTarget.value as Channel)}
        class={inputClass}
      >
        {#each CHANNELS as option (option)}
          <option value={option}>{CHANNEL_LABELS[option]}</option>
        {/each}
      </select>
    </div>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (revoking = null)}>Cancelar</Button>
      <Button type="submit" variant="danger" disabled={saving}
        >{saving ? 'Revocando…' : 'Revocar'}</Button
      >
    </div>
  </form>
</Modal>
