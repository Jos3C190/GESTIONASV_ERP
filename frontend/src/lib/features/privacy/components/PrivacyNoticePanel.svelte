<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import PrivacyEmptyState from './PrivacyEmptyState.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { privacyApi } from '#lib/api/privacy.ts';
  import { formatMoment } from '#lib/features/privacy/labels.ts';
  import type { NoticeElement, PrivacyNotice } from '#lib/types/privacy.ts';

  let { canManage }: { canManage: boolean } = $props();

  let notices = $state<PrivacyNotice[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let open = $state(false);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let title = $state('');
  let body = $state('');
  let elements = $state<NoticeElement[]>([]);
  let covered = $state<string[]>([]);
  let showHistory = $state(false);

  const current = $derived(notices[0] ?? null);

  async function load() {
    loading = true;
    loadError = null;
    try {
      notices = await privacyApi.notices();
    } catch (cause) {
      loadError = cause instanceof HttpError ? cause.message : 'No se pudo cargar el aviso.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  async function openEditor() {
    formError = null;
    covered = [];
    try {
      const template = await privacyApi.noticeTemplate();
      elements = template.elements;
      title = current?.title ?? template.title;
      body = current?.body ?? template.body;
      open = true;
    } catch (cause) {
      loadError = cause instanceof HttpError ? cause.message : 'No se pudo preparar el editor.';
    }
  }

  function toggle(key: string) {
    covered = covered.includes(key) ? covered.filter((k) => k !== key) : [...covered, key];
  }

  async function publish(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    formError = null;
    try {
      await privacyApi.publishNotice({ title, body, covered_elements: covered });
      open = false;
      await load();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo publicar el aviso.';
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
      <h2 class="font-semibold text-foreground">Aviso de privacidad</h2>
      <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
        Informa a los clientes qué datos se tratan, para qué y cómo ejercer sus derechos. Debe
        conocerse antes de recolectar datos y antes de registrar un consentimiento.
      </p>
    </div>
    {#if canManage && !loading && current}
      <Button class="shrink-0" onclick={() => void openEditor()}>Publicar nueva versión</Button>
    {/if}
  </div>

  {#if loading}
    <div class="space-y-3 p-4" aria-busy="true">
      <p class="sr-only" role="status">Cargando el aviso…</p>
      <div class="skeleton h-40 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
    </div>
  {:else if loadError}
    <div
      class="m-4 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else if !current}
    <PrivacyEmptyState
      icon="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6z"
      message="Aún no hay aviso de privacidad publicado"
      detail="Sin aviso no se pueden registrar consentimientos de los clientes."
    >
      {#snippet action()}
        {#if canManage}
          <Button variant="secondary" onclick={() => void openEditor()}>Redactar el aviso</Button>
        {/if}
      {/snippet}
    </PrivacyEmptyState>
  {:else}
    <article class="space-y-3 p-4">
      <p class="text-xs text-foreground-muted">
        Versión {current.version} · publicada el {formatMoment(current.published_at)}
        {#if current.published_by_name}por {current.published_by_name}{/if}
      </p>
      <h3 class="text-lg font-semibold text-foreground">{current.title}</h3>
      <div class="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{current.body}</div>
    </article>
    {#if notices.length > 1}
      <div class="border-t border-border p-4">
        <Button variant="ghost" size="sm" onclick={() => (showHistory = !showHistory)}>
          {showHistory
            ? 'Ocultar versiones anteriores'
            : `Ver versiones anteriores (${notices.length - 1})`}
        </Button>
        {#if showHistory}
          <ul class="mt-2 space-y-1 text-sm text-foreground-muted">
            {#each notices.slice(1) as notice (notice.id)}
              <li>Versión {notice.version} · {formatMoment(notice.published_at)}</li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}
  {/if}
</section>

<Modal {open} title="Publicar aviso de privacidad" onclose={() => (open = false)} size="xl">
  <form class="space-y-4" onsubmit={publish}>
    {#if formError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {formError}
      </p>
    {/if}
    <div>
      <label for="notice-title" class="mb-1 block text-sm font-medium text-foreground">Título</label
      >
      <input
        id="notice-title"
        bind:value={title}
        required
        minlength="5"
        maxlength="200"
        class="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      />
    </div>
    <div>
      <label for="notice-body" class="mb-1 block text-sm font-medium text-foreground">Texto</label>
      <textarea
        id="notice-body"
        bind:value={body}
        required
        rows="12"
        class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm leading-relaxed text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      ></textarea>
      <p class="mt-1 text-xs text-foreground-muted">
        El texto propuesto usa los datos de la empresa. Revísalo y ajústalo a cómo trata los datos.
      </p>
    </div>
    <fieldset>
      <legend class="mb-2 text-sm font-medium text-foreground">
        Confirma que el aviso incluye (Ley para la Protección de Datos Personales, art. 24):
      </legend>
      <div class="space-y-1">
        {#each elements as element (element.key)}
          <label class="flex min-h-9 items-start gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={covered.includes(element.key)}
              onchange={() => toggle(element.key)}
              class="mt-1"
            />
            {element.description}
          </label>
        {/each}
      </div>
    </fieldset>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (open = false)}>Cancelar</Button>
      <Button type="submit" disabled={saving || covered.length < elements.length}>
        {saving ? 'Publicando…' : 'Publicar'}
      </Button>
    </div>
  </form>
</Modal>
