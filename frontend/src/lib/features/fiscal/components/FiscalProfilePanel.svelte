<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalApi } from '#lib/api/fiscal.ts';
  import { confirmation } from '#lib/stores/confirmation.svelte.ts';
  import {
    OPERATING_MODE_HINTS,
    OPERATING_MODE_LABELS,
    PERSON_TYPE_LABELS,
    TAXPAYER_CATEGORY_LABELS
  } from '#lib/features/fiscal/labels.ts';
  import type {
    FiscalProfile,
    OperatingMode,
    PersonType,
    TaxpayerCategory
  } from '#lib/types/fiscal.ts';

  let { canManage }: { canManage: boolean } = $props();

  const MODES: OperatingMode[] = ['simulated', 'test', 'production'];
  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  let profile = $state<FiscalProfile | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let saved = $state<string | null>(null);

  let category = $state<TaxpayerCategory>('other');
  let personType = $state<PersonType>('2');
  let mode = $state<OperatingMode>('simulated');
  let email = $state('');
  let phone = $state('');

  function fill(next: FiscalProfile) {
    profile = next;
    category = next.taxpayer_category;
    personType = next.person_type;
    mode = next.operating_mode;
    email = next.dte_email ?? '';
    phone = next.dte_phone ?? '';
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      fill(await fiscalApi.getProfile());
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudo cargar el perfil de emisor.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  async function persist() {
    saving = true;
    formError = null;
    saved = null;
    try {
      fill(
        await fiscalApi.updateProfile({
          taxpayer_category: category,
          person_type: personType,
          operating_mode: mode,
          dte_email: email.trim() || null,
          dte_phone: phone.trim() || null
        })
      );
      saved = 'Se guardó el perfil de emisor.';
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo guardar el perfil.';
    } finally {
      saving = false;
    }
  }

  function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!canManage) return;
    if (mode === 'production' && profile?.operating_mode !== 'production') {
      confirmation.request({
        kind: 'confirm',
        title: 'Emitir en producción',
        description:
          'Desde ahora los documentos de esta empresa tendrán validez fiscal y se enviarán a Hacienda.',
        resourceName: profile?.commercial_name,
        confirmLabel: 'Pasar a producción',
        execute: persist
      });
      return;
    }
    void persist();
  }
</script>

{#if loading}
  <div class="space-y-3" aria-busy="true">
    <p class="sr-only" role="status">Cargando el perfil de emisor…</p>
    <div class="skeleton h-24 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
    <div class="skeleton h-64 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
  </div>
{:else if loadError || !profile}
  <div
    class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
    role="alert"
  >
    <span>{loadError ?? 'No se pudo cargar el perfil de emisor.'}</span>
    <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
  </div>
{:else}
  <div class="space-y-5">
    <section class="rounded-xl border border-border bg-surface-elevated p-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="font-semibold text-foreground">{profile.company_name}</h2>
          <p class="text-sm text-foreground-muted">{profile.commercial_name}</p>
        </div>
        <Badge variant={profile.operating_mode === 'production' ? 'success' : 'warning'}>
          {OPERATING_MODE_LABELS[profile.operating_mode]}
        </Badge>
      </div>
      <dl class="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt class="text-xs text-foreground-muted">NIT</dt>
          <dd class="font-medium text-foreground">{profile.nit || '—'}</dd>
        </div>
        <div>
          <dt class="text-xs text-foreground-muted">NRC</dt>
          <dd class="font-medium text-foreground">{profile.nrc || '—'}</dd>
        </div>
      </dl>
      <p class="mt-3 text-xs text-foreground-muted">
        La razón social, el nombre comercial, el NIT y el NRC se editan en la ficha de la empresa.
      </p>
    </section>

    {#if profile.operating_mode !== 'production' && profile.production_blockers.length > 0}
      <aside
        class="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm"
        aria-live="polite"
      >
        <p class="font-semibold text-foreground">Para emitir en producción falta:</p>
        <ul class="mt-2 list-disc space-y-1 pl-5 text-foreground-muted">
          {#each profile.production_blockers as reason (reason)}
            <li>{reason}</li>
          {/each}
        </ul>
      </aside>
    {/if}

    {#if saved}
      <p
        class="rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-success"
        role="status"
      >
        {saved}
      </p>
    {/if}

    <form
      class="space-y-5 rounded-xl border border-border bg-surface-elevated p-4"
      onsubmit={submit}
    >
      {#if formError}
        <p
          class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          role="alert"
        >
          {formError}
        </p>
      {/if}

      <fieldset>
        <legend class="mb-2 text-sm font-medium text-foreground">Modo de operación</legend>
        <div class="grid gap-2 md:grid-cols-3">
          {#each MODES as option (option)}
            <label
              class="flex cursor-pointer gap-3 rounded-lg border p-3 text-sm transition-colors {mode ===
              option
                ? 'border-primary bg-primary/5'
                : 'border-border hover:bg-surface-muted/50'}"
            >
              <input
                type="radio"
                name="operating-mode"
                value={option}
                bind:group={mode}
                disabled={!canManage}
                class="mt-0.5"
              />
              <span>
                <span class="block font-medium text-foreground"
                  >{OPERATING_MODE_LABELS[option]}</span
                >
                <span class="block text-xs text-foreground-muted"
                  >{OPERATING_MODE_HINTS[option]}</span
                >
              </span>
            </label>
          {/each}
        </div>
      </fieldset>

      <div class="grid gap-4 md:grid-cols-2">
        <div>
          <label for="fiscal-category" class="mb-1 block text-sm font-medium text-foreground">
            Categoría de contribuyente
          </label>
          <select
            id="fiscal-category"
            bind:value={category}
            disabled={!canManage}
            class={inputClass}
          >
            {#each Object.entries(TAXPAYER_CATEGORY_LABELS) as [value, label] (value)}
              <option {value}>{label}</option>
            {/each}
          </select>
        </div>
        <div>
          <label for="fiscal-person" class="mb-1 block text-sm font-medium text-foreground">
            Tipo de persona
          </label>
          <select
            id="fiscal-person"
            bind:value={personType}
            disabled={!canManage}
            class={inputClass}
          >
            {#each Object.entries(PERSON_TYPE_LABELS) as [value, label] (value)}
              <option {value}>{label}</option>
            {/each}
          </select>
        </div>
        <div>
          <label for="fiscal-email" class="mb-1 block text-sm font-medium text-foreground">
            Correo del emisor en el DTE
          </label>
          <input
            id="fiscal-email"
            type="email"
            bind:value={email}
            maxlength="100"
            disabled={!canManage}
            placeholder="facturacion@empresa.com"
            class={inputClass}
          />
        </div>
        <div>
          <label for="fiscal-phone" class="mb-1 block text-sm font-medium text-foreground">
            Teléfono del emisor en el DTE
          </label>
          <input
            id="fiscal-phone"
            bind:value={phone}
            minlength="8"
            maxlength="30"
            disabled={!canManage}
            placeholder="2222-0000"
            class={inputClass}
          />
        </div>
      </div>

      {#if canManage}
        <div class="flex justify-end border-t border-border pt-4">
          <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar perfil'}</Button
          >
        </div>
      {/if}
    </form>
  </div>
{/if}
