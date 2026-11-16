<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import PrivacyEmptyState from './PrivacyEmptyState.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { privacyApi } from '#lib/api/privacy.ts';
  import { formatMoment, fromLocalInput, toLocalInput } from '#lib/features/privacy/labels.ts';
  import { confirmation } from '#lib/stores/confirmation.svelte.ts';
  import type { Incident, IncidentInput } from '#lib/types/privacy.ts';

  let { canManage }: { canManage: boolean } = $props();

  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';
  const areaClass =
    'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';
  const labelClass = 'mb-1 block text-sm font-medium text-foreground';

  /** Campos de fecha y hora como los muestra `<input type="datetime-local">`. */
  interface IncidentForm {
    discovered_at: string;
    occurred_at: string;
    description: string;
    data_categories: string;
    affected_count: number | null;
    measures: string;
    notified_ace_at: string;
    ace_reference: string;
    notified_prosecutor_at: string;
    prosecutor_reference: string;
    notified_subjects_at: string;
    subjects_reference: string;
    subjects_not_required_reason: string;
  }

  let incidents = $state<Incident[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let editing = $state<Incident | null>(null);
  let open = $state(false);
  let form = $state<IncidentForm>(toForm(null));
  let saving = $state(false);
  let formError = $state<string | null>(null);

  function toForm(incident: Incident | null): IncidentForm {
    return {
      discovered_at: toLocalInput(incident?.discovered_at ?? new Date().toISOString()),
      occurred_at: toLocalInput(incident?.occurred_at ?? null),
      description: incident?.description ?? '',
      data_categories: incident?.data_categories ?? '',
      affected_count: incident?.affected_count ?? null,
      measures: incident?.measures ?? '',
      notified_ace_at: toLocalInput(incident?.notified_ace_at ?? null),
      ace_reference: incident?.ace_reference ?? '',
      notified_prosecutor_at: toLocalInput(incident?.notified_prosecutor_at ?? null),
      prosecutor_reference: incident?.prosecutor_reference ?? '',
      notified_subjects_at: toLocalInput(incident?.notified_subjects_at ?? null),
      subjects_reference: incident?.subjects_reference ?? '',
      subjects_not_required_reason: incident?.subjects_not_required_reason ?? ''
    };
  }

  function optional(value: string): string | null {
    return value.trim() || null;
  }

  function toInput(value: IncidentForm): IncidentInput {
    return {
      discovered_at: fromLocalInput(value.discovered_at) ?? new Date().toISOString(),
      occurred_at: fromLocalInput(value.occurred_at),
      description: value.description.trim(),
      data_categories: value.data_categories.trim(),
      affected_count: value.affected_count ?? null,
      measures: optional(value.measures),
      notified_ace_at: fromLocalInput(value.notified_ace_at),
      ace_reference: optional(value.ace_reference),
      notified_prosecutor_at: fromLocalInput(value.notified_prosecutor_at),
      prosecutor_reference: optional(value.prosecutor_reference),
      notified_subjects_at: fromLocalInput(value.notified_subjects_at),
      subjects_reference: optional(value.subjects_reference),
      subjects_not_required_reason: optional(value.subjects_not_required_reason)
    };
  }

  function pendingNotifications(incident: Incident): string[] {
    const missing: string[] = [];
    if (!incident.notified_ace_at) missing.push('Agencia de Ciberseguridad del Estado');
    if (!incident.notified_prosecutor_at) missing.push('Fiscalía General de la República');
    if (!incident.notified_subjects_at && !incident.subjects_not_required_reason) {
      missing.push('titulares afectados');
    }
    return missing;
  }

  function isLate(incident: Incident): boolean {
    return (
      incident.status === 'open' &&
      pendingNotifications(incident).length > 0 &&
      new Date(incident.notification_deadline).getTime() < Date.now()
    );
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      incidents = await privacyApi.incidents();
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar las vulneraciones.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  function openEditor(incident: Incident | null) {
    editing = incident;
    form = toForm(incident);
    formError = null;
    open = true;
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    formError = null;
    try {
      const payload = toInput(form);
      if (editing) await privacyApi.updateIncident(editing.id, payload);
      else await privacyApi.createIncident(payload);
      open = false;
      await load();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo guardar la vulneración.';
    } finally {
      saving = false;
    }
  }

  function close(incident: Incident) {
    confirmation.request({
      kind: 'confirm',
      title: 'Cerrar la vulneración',
      description:
        'Confirma que las medidas se aplicaron y las notificaciones quedaron registradas. Una vulneración cerrada ya no se edita.',
      resourceName: incident.code,
      confirmLabel: 'Cerrar',
      execute: async () => {
        await privacyApi.closeIncident(incident.id);
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
      <h2 class="font-semibold text-foreground">Vulneraciones de seguridad</h2>
      <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
        Accesos indebidos, pérdidas o filtraciones de datos personales. Se notifican a la Agencia de
        Ciberseguridad del Estado, a la Fiscalía y a los titulares afectados dentro de 72 horas.
      </p>
    </div>
    {#if canManage && (loading || loadError || incidents.length > 0)}
      <Button class="shrink-0" onclick={() => openEditor(null)}>Registrar vulneración</Button>
    {/if}
  </div>

  {#if loading}
    <div class="space-y-3 p-4" aria-busy="true">
      <p class="sr-only" role="status">Cargando vulneraciones…</p>
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
  {:else if incidents.length === 0}
    <PrivacyEmptyState
      icon="M12 9v4 M12 17h.01 M10.3 3.9L2.4 18a2 2 0 001.7 3h15.8a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"
      message="No hay vulneraciones registradas."
      detail="Si se detecta un acceso indebido, una pérdida o una filtración de datos, regístrala de inmediato: el plazo para notificar es de 72 horas."
    >
      {#snippet action()}
        {#if canManage}
          <Button variant="secondary" onclick={() => openEditor(null)}>Registrar vulneración</Button
          >
        {/if}
      {/snippet}
    </PrivacyEmptyState>
  {:else}
    <ul class="divide-y divide-border">
      {#each incidents as incident (incident.id)}
        {@const missing = pendingNotifications(incident)}
        <li class="flex flex-col gap-2 p-4 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0 text-sm">
            <p class="flex flex-wrap items-center gap-2 font-medium text-foreground">
              <span class="font-mono">{incident.code}</span>
              {#if incident.status === 'closed'}
                <Badge variant="neutral">Cerrada</Badge>
              {:else}
                <Badge variant="warning">Abierta</Badge>
              {/if}
              {#if isLate(incident)}<Badge variant="danger">Notificación vencida</Badge>{/if}
            </p>
            <p class="mt-1 line-clamp-2 text-foreground">{incident.description}</p>
            <p class="mt-1 text-foreground-muted">
              Descubierta el {formatMoment(incident.discovered_at)}
              {#if incident.status === 'open'}
                · notificar antes del {formatMoment(incident.notification_deadline)}
              {/if}
            </p>
            {#if incident.status === 'open' && missing.length > 0}
              <p class="mt-1 text-warning">Falta notificar a: {missing.join(', ')}.</p>
            {/if}
          </div>
          {#if canManage && incident.status === 'open'}
            <div class="flex shrink-0 gap-2">
              <Button variant="secondary" size="sm" onclick={() => openEditor(incident)}
                >Editar</Button
              >
              <Button size="sm" disabled={missing.length > 0} onclick={() => close(incident)}>
                Cerrar
              </Button>
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<Modal
  {open}
  title={editing ? `Vulneración ${editing.code}` : 'Registrar vulneración'}
  onclose={() => (open = false)}
  size="xl"
>
  <form class="space-y-5" onsubmit={save}>
    {#if formError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {formError}
      </p>
    {/if}
    <div class="grid gap-4 sm:grid-cols-2">
      <div>
        <label for="incident-discovered" class={labelClass}>Descubierta el</label>
        <input
          id="incident-discovered"
          type="datetime-local"
          bind:value={form.discovered_at}
          required
          class={inputClass}
        />
      </div>
      <div>
        <label for="incident-occurred" class={labelClass}>Ocurrió el (si se sabe)</label>
        <input
          id="incident-occurred"
          type="datetime-local"
          bind:value={form.occurred_at}
          class={inputClass}
        />
      </div>
      <div class="sm:col-span-2">
        <label for="incident-description" class={labelClass}>Qué pasó</label>
        <textarea
          id="incident-description"
          bind:value={form.description}
          required
          minlength="10"
          rows="3"
          class={areaClass}
        ></textarea>
      </div>
      <div>
        <label for="incident-categories" class={labelClass}>Datos comprometidos</label>
        <input
          id="incident-categories"
          bind:value={form.data_categories}
          required
          minlength="3"
          placeholder="Nombres, teléfonos, direcciones…"
          class={inputClass}
        />
      </div>
      <div>
        <label for="incident-affected" class={labelClass}>Titulares afectados (aprox.)</label>
        <input
          id="incident-affected"
          type="number"
          min="0"
          bind:value={form.affected_count}
          class={inputClass}
        />
      </div>
      <div class="sm:col-span-2">
        <label for="incident-measures" class={labelClass}>Medidas tomadas</label>
        <textarea id="incident-measures" bind:value={form.measures} rows="2" class={areaClass}
        ></textarea>
      </div>
    </div>

    <fieldset class="space-y-3 border-t border-border pt-4">
      <legend class="text-sm font-semibold text-foreground">Notificaciones</legend>
      <div class="grid gap-4 sm:grid-cols-2">
        <div>
          <label for="incident-ace-at" class={labelClass}
            >Agencia de Ciberseguridad: notificada el</label
          >
          <input
            id="incident-ace-at"
            type="datetime-local"
            bind:value={form.notified_ace_at}
            class={inputClass}
          />
        </div>
        <div>
          <label for="incident-ace-ref" class={labelClass}>Referencia</label>
          <input
            id="incident-ace-ref"
            bind:value={form.ace_reference}
            maxlength="200"
            class={inputClass}
          />
        </div>
        <div>
          <label for="incident-fgr-at" class={labelClass}>Fiscalía: notificada el</label>
          <input
            id="incident-fgr-at"
            type="datetime-local"
            bind:value={form.notified_prosecutor_at}
            class={inputClass}
          />
        </div>
        <div>
          <label for="incident-fgr-ref" class={labelClass}>Referencia</label>
          <input
            id="incident-fgr-ref"
            bind:value={form.prosecutor_reference}
            maxlength="200"
            class={inputClass}
          />
        </div>
        <div>
          <label for="incident-subjects-at" class={labelClass}>Titulares: notificados el</label>
          <input
            id="incident-subjects-at"
            type="datetime-local"
            bind:value={form.notified_subjects_at}
            class={inputClass}
          />
        </div>
        <div>
          <label for="incident-subjects-ref" class={labelClass}>Medio usado</label>
          <input
            id="incident-subjects-ref"
            bind:value={form.subjects_reference}
            maxlength="200"
            class={inputClass}
          />
        </div>
        <div class="sm:col-span-2">
          <label for="incident-subjects-reason" class={labelClass}>
            Si no se notifica a los titulares, explica por qué
          </label>
          <input
            id="incident-subjects-reason"
            bind:value={form.subjects_not_required_reason}
            maxlength="500"
            class={inputClass}
          />
        </div>
      </div>
    </fieldset>

    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (open = false)}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
    </div>
  </form>
</Modal>
