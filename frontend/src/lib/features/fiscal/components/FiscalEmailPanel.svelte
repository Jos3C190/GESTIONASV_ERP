<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalApi } from '#lib/api/fiscal.ts';
  import { confirmation } from '#lib/stores/confirmation.svelte.ts';
  import { formatDay } from '#lib/features/sales/quotation-labels.ts';
  import type { EmailSettings, SmtpSecurity } from '#lib/types/fiscal.ts';

  let { canManage }: { canManage: boolean } = $props();

  const SECURITY: { value: SmtpSecurity; label: string; port: number }[] = [
    { value: 'starttls', label: 'STARTTLS (puerto 587)', port: 587 },
    { value: 'ssl', label: 'SSL/TLS (puerto 465)', port: 465 },
    { value: 'none', label: 'Sin cifrado (solo relé interno)', port: 25 }
  ];
  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  let current = $state<EmailSettings | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let saved = $state<string | null>(null);
  let testing = $state(false);
  let testResult = $state<{ ok: boolean; message: string } | null>(null);

  let host = $state('');
  let port = $state('587');
  let security = $state<SmtpSecurity>('starttls');
  let username = $state('');
  let password = $state('');
  let fromAddress = $state('');
  let fromName = $state('');
  let enabled = $state(true);
  let testRecipient = $state('');

  function fill(next: EmailSettings) {
    current = next;
    host = next.host ?? '';
    port = String(next.port ?? 587);
    security = next.security ?? 'starttls';
    username = next.username ?? '';
    password = '';
    fromAddress = next.from_address ?? '';
    fromName = next.from_name ?? '';
    enabled = next.configured ? next.is_enabled : true;
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      fill(await fiscalApi.getEmailSettings());
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudo cargar el correo saliente.';
    } finally {
      loading = false;
    }
  }
  onMount(() => void load());

  function chooseSecurity(value: SmtpSecurity) {
    const previous = SECURITY.find((item) => item.value === security);
    security = value;
    // Si el puerto era el sugerido para la seguridad anterior, se propone el de la nueva.
    if (!port || Number(port) === previous?.port) {
      port = String(SECURITY.find((item) => item.value === value)?.port ?? 587);
    }
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!canManage || saving) return;
    saving = true;
    formError = null;
    saved = null;
    testResult = null;
    try {
      fill(
        await fiscalApi.saveEmailSettings({
          host: host.trim(),
          port: Number(port),
          security,
          username: username.trim() || null,
          password: password || null,
          from_address: fromAddress.trim(),
          from_name: fromName.trim() || null,
          is_enabled: enabled
        })
      );
      saved = 'Se guardó el correo saliente. Envía un correo de prueba para confirmarlo.';
    } catch (cause) {
      formError =
        cause instanceof HttpError ? cause.message : 'No se pudo guardar el correo saliente.';
    } finally {
      saving = false;
    }
  }

  async function sendTest() {
    if (!testRecipient.trim() || testing) return;
    testing = true;
    testResult = null;
    try {
      testResult = await fiscalApi.testEmailSettings(testRecipient.trim());
      fill(await fiscalApi.getEmailSettings());
    } catch (cause) {
      testResult = {
        ok: false,
        message: cause instanceof HttpError ? cause.message : 'No se pudo enviar la prueba.'
      };
    } finally {
      testing = false;
    }
  }

  function remove() {
    confirmation.request({
      kind: 'delete',
      title: 'Quitar el correo saliente',
      description: current?.server_fallback
        ? 'Los documentos se enviarán con el correo del servidor.'
        : 'Los documentos dejarán de enviarse por correo hasta que configures otro.',
      confirmLabel: 'Quitar',
      execute: async () => {
        await fiscalApi.deleteEmailSettings();
        await load();
        saved = 'Se quitó el correo saliente de la empresa.';
      }
    });
  }
</script>

{#if loading}
  <div class="space-y-3" aria-busy="true">
    <p class="sr-only" role="status">Cargando el correo saliente…</p>
    <div class="skeleton h-24 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
    <div class="skeleton h-64 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
  </div>
{:else if loadError || !current}
  <div
    class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
    role="alert"
  >
    <span>{loadError ?? 'No se pudo cargar el correo saliente.'}</span>
    <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
  </div>
{:else}
  <div class="space-y-5">
    <section class="space-y-2 rounded-xl border border-border bg-surface-elevated p-4 text-sm">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="font-semibold text-foreground">Correo saliente de la empresa</h2>
          <p class="text-foreground-muted">
            Los documentos tributarios se envían a los clientes desde tu servidor de correo y tu
            dominio.
          </p>
        </div>
        {#if current.configured}
          <Badge variant={current.is_enabled ? 'success' : 'warning'}>
            {current.is_enabled ? 'Activo' : 'Desactivado'}
          </Badge>
        {:else}
          <Badge variant="warning">Sin configurar</Badge>
        {/if}
      </div>
      {#if !current.configured || !current.is_enabled}
        <p class="text-foreground-muted">
          {current.server_fallback
            ? 'Mientras tanto, los documentos salen con el correo del servidor.'
            : 'Mientras no lo configures, los documentos no se envían por correo.'}
        </p>
      {/if}
      <ul class="list-disc space-y-1 pl-5 text-xs text-foreground-muted">
        <li>
          El dominio del remitente debe tener SPF, DKIM y DMARC; si no, Gmail y Outlook pueden
          mandar los correos a spam. Lo configura tu proveedor de correo.
        </li>
        <li>
          Google: usa smtp.gmail.com, puerto 587 y una contraseña de aplicación (requiere
          verificación en dos pasos).
        </li>
        <li>
          Microsoft 365: smtp.office365.com, puerto 587, con «SMTP autenticado» activado en el
          buzón.
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
        <label class="space-y-1 text-sm text-foreground-muted"
          >Servidor SMTP
          <input
            class={inputClass}
            value={host}
            oninput={(event) => (host = event.currentTarget.value)}
            placeholder="smtp.gmail.com"
            autocomplete="off"
            disabled={!canManage}
            required
          />
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label class="space-y-1 text-sm text-foreground-muted"
            >Seguridad
            <select
              class={inputClass}
              value={security}
              onchange={(event) => chooseSecurity(event.currentTarget.value as SmtpSecurity)}
              disabled={!canManage}
            >
              {#each SECURITY as option (option.value)}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          </label>
          <label class="space-y-1 text-sm text-foreground-muted"
            >Puerto
            <input
              class={inputClass}
              type="number"
              min="1"
              max="65535"
              value={port}
              oninput={(event) => (port = event.currentTarget.value)}
              disabled={!canManage}
              required
            />
          </label>
        </div>
        <label class="space-y-1 text-sm text-foreground-muted"
          >Usuario
          <input
            class={inputClass}
            value={username}
            oninput={(event) => (username = event.currentTarget.value)}
            placeholder="facturacion@tuempresa.com"
            autocomplete="off"
            disabled={!canManage}
          />
        </label>
        <label class="space-y-1 text-sm text-foreground-muted"
          >Contraseña
          <input
            class={inputClass}
            type="password"
            value={password}
            oninput={(event) => (password = event.currentTarget.value)}
            placeholder={current.has_password
              ? 'Guardada; escribe otra para cambiarla'
              : 'Contraseña o contraseña de aplicación'}
            autocomplete="new-password"
            disabled={!canManage}
          />
        </label>
        <label class="space-y-1 text-sm text-foreground-muted"
          >Correo del remitente
          <input
            class={inputClass}
            type="email"
            value={fromAddress}
            oninput={(event) => (fromAddress = event.currentTarget.value)}
            placeholder="facturacion@tuempresa.com"
            disabled={!canManage}
            required
          />
        </label>
        <label class="space-y-1 text-sm text-foreground-muted"
          >Nombre del remitente (opcional)
          <input
            class={inputClass}
            value={fromName}
            oninput={(event) => (fromName = event.currentTarget.value)}
            placeholder="Por defecto, el nombre comercial"
            maxlength="150"
            disabled={!canManage}
          />
        </label>
      </div>
      <label class="flex items-center gap-2 text-sm text-foreground">
        <input
          type="checkbox"
          checked={enabled}
          onchange={(event) => (enabled = event.currentTarget.checked)}
          disabled={!canManage}
        />
        Enviar los documentos con este correo
      </label>
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
      <section class="space-y-3 rounded-xl border border-border bg-surface p-4" aria-label="Prueba">
        <h2 class="font-semibold text-foreground">Correo de prueba</h2>
        {#if current.last_test_at}
          <p class="text-sm {current.last_test_ok ? 'text-success' : 'text-danger'}">
            Última prueba el {formatDay(current.last_test_at)}: {current.last_test_ok
              ? 'se envió bien.'
              : (current.last_test_error ?? 'falló.')}
          </p>
        {:else}
          <p class="text-sm text-foreground-muted">Todavía no se ha probado esta configuración.</p>
        {/if}
        {#if canManage}
          <form
            class="flex flex-col gap-2 sm:flex-row sm:items-end"
            onsubmit={(event) => {
              event.preventDefault();
              void sendTest();
            }}
          >
            <label class="flex min-w-0 flex-1 flex-col gap-1 text-sm text-foreground-muted"
              >Enviar la prueba a
              <input
                class={inputClass}
                type="email"
                value={testRecipient}
                oninput={(event) => (testRecipient = event.currentTarget.value)}
                placeholder="tu-correo@tuempresa.com"
              />
            </label>
            <Button type="submit" variant="secondary" disabled={testing || !testRecipient.trim()}
              >{testing ? 'Enviando…' : 'Enviar correo de prueba'}</Button
            >
          </form>
        {/if}
        {#if testResult}
          <p
            class="text-sm {testResult.ok ? 'text-success' : 'text-danger'}"
            role={testResult.ok ? 'status' : 'alert'}
          >
            {testResult.message}
          </p>
        {/if}
      </section>
    {/if}
  </div>
{/if}
