<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalApi } from '#lib/api/fiscal.ts';
  import { confirmation } from '#lib/stores/confirmation.svelte.ts';
  import { formatDay } from '#lib/features/sales/quotation-labels.ts';
  import type { HaciendaCredentials, HaciendaTestResult } from '#lib/types/fiscal.ts';

  let { canManage }: { canManage: boolean } = $props();

  const MAX_CERTIFICATE_BYTES = 256 * 1024;
  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  let current = $state<HaciendaCredentials | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let saved = $state<string | null>(null);
  let testing = $state(false);
  let testResult = $state<HaciendaTestResult | null>(null);

  let apiPassword = $state('');
  let privatePassword = $state('');
  let certificate = $state<{ name: string; base64: string } | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);

  async function load() {
    loading = true;
    loadError = null;
    try {
      current = await fiscalApi.getHaciendaCredentials();
    } catch (cause) {
      loadError =
        cause instanceof HttpError
          ? cause.message
          : 'No se pudieron cargar las credenciales de Hacienda.';
    } finally {
      loading = false;
    }
  }
  onMount(() => void load());

  function toBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (const byte of bytes) binary += String.fromCharCode(byte);
    return btoa(binary);
  }

  async function chooseFile(event: Event) {
    formError = null;
    const file = (event.currentTarget as HTMLInputElement).files?.[0];
    if (!file) {
      certificate = null;
      return;
    }
    if (file.size > MAX_CERTIFICATE_BYTES) {
      certificate = null;
      formError = 'El certificado pesa más de 256 KB.';
      return;
    }
    certificate = { name: file.name, base64: toBase64(await file.arrayBuffer()) };
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!canManage || saving) return;
    saving = true;
    formError = null;
    saved = null;
    testResult = null;
    try {
      current = await fiscalApi.saveHaciendaCredentials({
        api_password: apiPassword || null,
        private_key_password: privatePassword || null,
        certificate_base64: certificate?.base64 ?? null
      });
      apiPassword = '';
      privatePassword = '';
      certificate = null;
      if (fileInput) fileInput.value = '';
      saved = 'Se guardaron las credenciales. Prueba la conexión para poder emitir ante Hacienda.';
    } catch (cause) {
      formError =
        cause instanceof HttpError ? cause.message : 'No se pudieron guardar las credenciales.';
    } finally {
      saving = false;
    }
  }

  async function test() {
    if (testing) return;
    testing = true;
    testResult = null;
    formError = null;
    try {
      testResult = await fiscalApi.testHaciendaCredentials();
      current = await fiscalApi.getHaciendaCredentials();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo probar la conexión.';
    } finally {
      testing = false;
    }
  }

  function remove() {
    confirmation.request({
      kind: 'delete',
      title: 'Quitar las credenciales de Hacienda',
      description:
        'La empresa no podrá emitir ante Hacienda hasta que cargues otras. Solo se puede hacer en modo simulado.',
      confirmLabel: 'Quitar',
      execute: async () => {
        await fiscalApi.deleteHaciendaCredentials();
        await load();
        saved = 'Se quitaron las credenciales de Hacienda.';
      }
    });
  }
</script>

{#if loading}
  <div class="space-y-3" aria-busy="true">
    <p class="sr-only" role="status">Cargando las credenciales de Hacienda…</p>
    <div class="skeleton h-24 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
    <div class="skeleton h-64 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
  </div>
{:else if loadError || !current}
  <div
    class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
    role="alert"
  >
    <span>{loadError ?? 'No se pudieron cargar las credenciales de Hacienda.'}</span>
    <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
  </div>
{:else}
  <div class="space-y-5">
    <section class="space-y-2 rounded-xl border border-border bg-surface-elevated p-4 text-sm">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="font-semibold text-foreground">Credenciales de Hacienda</h2>
          <p class="text-foreground-muted">
            Con ellas la empresa se autentica en el Ministerio de Hacienda y firma sus documentos.
            Se guardan cifradas y no se vuelven a mostrar.
          </p>
        </div>
        {#if !current.configured}
          <Badge variant="warning">Sin cargar</Badge>
        {:else if current.last_test_ok}
          <Badge variant="success">Probadas</Badge>
        {:else}
          <Badge variant="warning">Sin probar</Badge>
        {/if}
      </div>
      {#if current.configured}
        <dl class="grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt class="text-xs text-foreground-muted">NIT del certificado</dt>
            <dd class="font-mono text-foreground">{current.certificate_nit}</dd>
          </div>
          <div>
            <dt class="text-xs text-foreground-muted">Huella del certificado</dt>
            <dd class="break-all font-mono text-xs text-foreground">
              {current.certificate_sha256?.slice(0, 16)}…
            </dd>
          </div>
        </dl>
      {/if}
      <ul class="list-disc space-y-1 pl-5 text-xs text-foreground-muted">
        <li>
          La contraseña de la API y el certificado (.crt) se obtienen en el portal de facturación
          electrónica de Hacienda, con la cuenta de la empresa.
        </li>
        <li>
          Para pasar la empresa al ambiente de pruebas o a producción, primero carga las
          credenciales y prueba la conexión.
        </li>
      </ul>
    </section>

    <form class="space-y-4 rounded-xl border border-border bg-surface p-4" onsubmit={submit}>
      {#if formError}
        <div
          class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
          role="alert"
        >
          {formError}
        </div>
      {/if}
      {#if saved}
        <p class="text-sm text-success" aria-live="polite">{saved}</p>
      {/if}
      <div class="grid gap-4 sm:grid-cols-2">
        <label class="space-y-1 text-sm text-foreground-muted sm:col-span-2"
          >Certificado (.crt)
          <input
            bind:this={fileInput}
            class="block w-full text-sm text-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-surface-muted file:px-3 file:py-2 file:text-sm file:text-foreground"
            type="file"
            accept=".crt,application/xml,text/xml"
            onchange={(event) => void chooseFile(event)}
            disabled={!canManage}
          />
          <span class="block text-xs">
            {certificate
              ? `Seleccionado: ${certificate.name}`
              : current.configured
                ? 'Hay un certificado guardado; elige otro solo para cambiarlo.'
                : 'Elige el archivo {nit}.crt que generó Hacienda.'}
          </span>
        </label>
        <label class="space-y-1 text-sm text-foreground-muted"
          >Contraseña de la API
          <input
            class={inputClass}
            type="password"
            value={apiPassword}
            oninput={(event) => (apiPassword = event.currentTarget.value)}
            placeholder={current.configured ? 'Guardada; escribe otra para cambiarla' : ''}
            autocomplete="new-password"
            disabled={!canManage}
          />
        </label>
        <label class="space-y-1 text-sm text-foreground-muted"
          >Contraseña de la llave privada
          <input
            class={inputClass}
            type="password"
            value={privatePassword}
            oninput={(event) => (privatePassword = event.currentTarget.value)}
            placeholder={current.configured ? 'Guardada; escribe otra para cambiarla' : ''}
            autocomplete="new-password"
            disabled={!canManage}
          />
        </label>
      </div>
      {#if canManage}
        <div class="flex flex-wrap gap-2">
          <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
          {#if current.configured}
            <Button variant="secondary" onclick={remove}>Quitar</Button>
          {/if}
        </div>
      {/if}
    </form>

    {#if current.configured}
      <section
        class="space-y-3 rounded-xl border border-border bg-surface p-4"
        aria-label="Conexión"
      >
        <h2 class="font-semibold text-foreground">Conexión con Hacienda</h2>
        {#if current.last_test_at}
          <p class="text-sm {current.last_test_ok ? 'text-success' : 'text-danger'}">
            Última prueba el {formatDay(current.last_test_at)}: {current.last_test_ok
              ? 'conexión y firma correctas.'
              : (current.last_test_error ?? 'falló.')}
          </p>
        {:else}
          <p class="text-sm text-foreground-muted">Todavía no se han probado estas credenciales.</p>
        {/if}
        {#if canManage}
          <Button variant="secondary" disabled={testing} onclick={() => void test()}
            >{testing ? 'Probando…' : 'Probar conexión'}</Button
          >
        {/if}
        {#if testResult}
          <ul class="space-y-1 text-sm" role={testResult.ok ? 'status' : 'alert'}>
            <li class={testResult.authentication_ok ? 'text-success' : 'text-danger'}>
              Autenticación: {testResult.authentication_message}
            </li>
            <li class={testResult.signature_ok ? 'text-success' : 'text-danger'}>
              Firma: {testResult.signature_message}
            </li>
          </ul>
        {/if}
      </section>
    {/if}
  </div>
{/if}
