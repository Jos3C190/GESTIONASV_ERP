<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseOrdersApi } from '$lib/api/purchase-orders';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { PurchaseOrderExpenseTypeCatalog } from '$lib/types/purchase-order';

  let types = $state<PurchaseOrderExpenseTypeCatalog[]>([]);
  let loading = $state(true);
  let saving = $state(false);
  let catalogError = $state<string | null>(null);
  let formError = $state<string | null>(null);
  let successMessage = $state<string | null>(null);
  let search = $state('');
  let showInactive = $state(false);
  let modalOpen = $state(false);
  let editing = $state<PurchaseOrderExpenseTypeCatalog | null>(null);
  let name = $state('');
  let description = $state('');

  const canManage = $derived(permissions.hasPermission('expense_types:manage'));
  const filteredTypes = $derived.by(() => {
    const query = search.trim().toLocaleLowerCase('es-SV');
    return types.filter((item) => {
      if (!showInactive && !item.is_active) return false;
      if (!query) return true;
      return [item.name, item.description]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase('es-SV').includes(query));
    });
  });
  const activeCount = $derived(types.filter((item) => item.is_active).length);
  const inactiveCount = $derived(types.length - activeCount);
  const usageCount = $derived(types.reduce((sum, item) => sum + item.usage_count, 0));

  async function load() {
    loading = true;
    catalogError = null;
    try {
      types = await purchaseOrdersApi.listExpenseTypeCatalog();
    } catch (cause) {
      catalogError = cause instanceof HttpError
        ? cause.message
        : 'No se pudo cargar el catálogo de tipos de gasto.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (canManage) void load();
    else loading = false;
  });

  function openCreate() {
    editing = null;
    name = '';
    description = '';
    formError = null;
    modalOpen = true;
  }

  function openEdit(item: PurchaseOrderExpenseTypeCatalog) {
    editing = item;
    name = item.name;
    description = item.description ?? '';
    formError = null;
    modalOpen = true;
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    if (!canManage) return;
    saving = true;
    formError = null;
    successMessage = null;
    try {
      const cleanedDescription = description.trim();
      if (editing) {
        await purchaseOrdersApi.updateExpenseType(editing.id, {
          name: name.trim(),
          description: cleanedDescription || null,
          is_active: editing.is_active
        });
      } else {
        await purchaseOrdersApi.createExpenseType({
          name: name.trim(),
          description: cleanedDescription || undefined
        });
      }
      modalOpen = false;
      await load();
      successMessage = editing
        ? 'Se guardaron los cambios del tipo de gasto.'
        : 'El tipo de gasto quedó disponible para las nuevas compras.';
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo guardar el tipo de gasto.';
    } finally {
      saving = false;
    }
  }

  function toggle(item: PurchaseOrderExpenseTypeCatalog) {
    const activating = !item.is_active;
    successMessage = null;
    confirmation.request({
      kind: activating ? 'restore' : 'deactivate',
      title: activating ? 'Reactivar tipo de gasto' : 'Desactivar tipo de gasto',
      description: activating
        ? 'Volverá a estar disponible al crear cotizaciones y órdenes nuevas.'
        : `Dejará de ofrecerse en nuevos documentos. Sus ${item.usage_count} referencias históricas se conservarán.`,
      resourceName: item.name,
      confirmLabel: activating ? 'Reactivar' : 'Desactivar',
      execute: async () => {
        await purchaseOrdersApi.updateExpenseType(item.id, {
          name: item.name,
          description: item.description,
          is_active: activating
        });
        await load();
        successMessage = activating
          ? 'El tipo de gasto volvió a estar disponible.'
          : 'El tipo de gasto se desactivó y su historial se conservó.';
      }
    });
  }
</script>

<svelte:head>
  <title>Tipos de gasto | GestionaSV</title>
</svelte:head>

{#if !canManage}
  <div class="m-4 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
    No tienes permiso para administrar los tipos de gasto.
  </div>
{:else}
  <div class="space-y-5 p-4 sm:p-6 md:p-8">
    <header class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase tracking-wider text-primary">Compras</p>
        <h1 class="mt-1 text-2xl font-bold tracking-tight text-foreground">Tipos de gasto</h1>
        <p class="mt-1 max-w-2xl text-sm text-foreground-muted">
          Administra los cargos disponibles para cotizaciones y órdenes de compra de esta empresa.
        </p>
      </div>
      <Button onclick={openCreate}>Nuevo tipo de gasto</Button>
    </header>

    <section class="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl border border-border bg-surface-elevated px-4 py-3" aria-label="Resumen del catálogo">
      <p class="text-sm text-foreground"><span class="font-semibold">{activeCount}</span> activos</p>
      <span class="hidden h-5 border-l border-border sm:block" aria-hidden="true"></span>
      <p class="text-sm text-foreground"><span class="font-semibold">{usageCount}</span> referencias históricas</p>
      <span class="hidden h-5 border-l border-border sm:block" aria-hidden="true"></span>
      <p class="text-sm text-foreground"><span class="font-semibold">{inactiveCount}</span> inactivos conservados</p>
    </section>

    <aside class="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-foreground-muted">
      <p class="font-semibold text-foreground">Registro de gastos y retaceo</p>
      <p class="mt-1 max-w-4xl">
        Registra cada cargo una sola vez en su etapa. Si un flete u otro costo se distribuirá en el retaceo,
        evita volver a capturarlo como un cargo adicional de la orden.
      </p>
    </aside>

    {#if successMessage}
      <p class="rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-success" role="status">{successMessage}</p>
    {/if}

    {#if catalogError && !modalOpen && types.length > 0}
      <div class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between" role="alert">
        <span>{catalogError}</span>
        <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
      </div>
    {/if}

    <section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
      <div class="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 class="font-semibold text-foreground">Catálogo de la empresa</h2>
          <p class="mt-1 text-xs text-foreground-muted">
            {types.length === 1 ? '1 tipo configurado' : `${types.length} tipos configurados`}
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label class="sr-only" for="expense-type-search">Buscar tipo de gasto</label>
          <input
            id="expense-type-search"
            bind:value={search}
            placeholder="Buscar tipo de gasto…"
            class="h-11 min-w-56 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <label class="flex min-h-11 items-center gap-2 rounded-md border border-border px-3 text-xs text-foreground-muted">
            <input type="checkbox" bind:checked={showInactive} /> Mostrar inactivos
          </label>
        </div>
      </div>

      {#if loading}
        <div class="space-y-3 p-4" aria-busy="true">
          <p class="sr-only" role="status">Cargando tipos de gasto…</p>
          <div class="skeleton motion-reduce:animate-none h-12 rounded-lg" aria-hidden="true"></div>
          <div class="skeleton motion-reduce:animate-none h-12 rounded-lg" aria-hidden="true"></div>
          <div class="skeleton motion-reduce:animate-none h-12 rounded-lg" aria-hidden="true"></div>
        </div>
      {:else if catalogError && types.length === 0}
        <div class="px-6 py-12 text-center">
          <p class="text-sm font-semibold text-foreground">No se pudo cargar el catálogo</p>
          <p class="mt-1 text-sm text-foreground-muted">Revisa tu conexión e inténtalo de nuevo.</p>
          <Button class="mt-4" variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
        </div>
      {:else if filteredTypes.length === 0}
        <div class="px-6 py-14 text-center">
          <div class="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-surface-muted text-foreground-muted" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M12 3v18M3 12h18" />
            </svg>
          </div>
          <p class="mt-3 text-sm font-semibold text-foreground">
            {types.length === 0 ? 'Aún no hay tipos de gasto' : 'Sin resultados'}
          </p>
          <p class="mt-1 text-sm text-foreground-muted">
            {types.length === 0
              ? 'Crea un tipo para habilitar la captura de gastos en una orden.'
              : 'Prueba otra búsqueda o muestra los tipos inactivos.'}
          </p>
          {#if types.length > 0 && !showInactive && inactiveCount > 0}
            <Button class="mt-4" variant="secondary" size="sm" onclick={() => { search = ''; showInactive = true; }}>
              Mostrar {inactiveCount} inactivo(s)
            </Button>
          {/if}
          {#if types.length === 0}
            <Button class="mt-4" size="sm" onclick={openCreate}>Crear primer tipo</Button>
          {/if}
        </div>
      {:else}
        <div class="hidden overflow-x-auto md:block">
          <table class="w-full min-w-[680px] text-sm">
            <thead class="bg-surface-muted text-xs text-foreground-muted">
              <tr>
                <th class="p-3 text-left font-medium">Tipo de gasto</th>
                <th class="p-3 text-left font-medium">Descripción</th>
                <th class="p-3 text-left font-medium">Referencias</th>
                <th class="p-3 text-left font-medium">Estado</th>
                <th class="p-3 text-right font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {#each filteredTypes as item (item.id)}
                <tr class="border-t border-border transition-colors hover:bg-surface-muted/40">
                  <td class="p-3 font-medium text-foreground">{item.name}</td>
                  <td class="max-w-md p-3 text-foreground-muted">{item.description || '—'}</td>
                  <td class="p-3 text-foreground-muted">{item.usage_count}</td>
                  <td class="p-3">
                    <Badge variant={item.is_active ? 'success' : 'neutral'}>
                      {item.is_active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td class="p-3">
                    <div class="flex justify-end gap-2">
                      <Button variant="secondary" size="sm" onclick={() => openEdit(item)}>Editar</Button>
                      <Button variant={item.is_active ? 'ghost' : 'secondary'} size="sm" onclick={() => toggle(item)}>
                        {item.is_active ? 'Desactivar' : 'Reactivar'}
                      </Button>
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="divide-y divide-border md:hidden">
          {#each filteredTypes as item (item.id)}
            <article class="space-y-3 p-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <h3 class="font-semibold text-foreground">{item.name}</h3>
                  <p class="mt-1 break-words text-sm text-foreground-muted">{item.description || 'Sin descripción'}</p>
                </div>
                <Badge variant={item.is_active ? 'success' : 'neutral'}>
                  {item.is_active ? 'Activo' : 'Inactivo'}
                </Badge>
              </div>
              <p class="text-xs text-foreground-muted">
                {item.usage_count === 1 ? '1 referencia histórica' : `${item.usage_count} referencias históricas`}
              </p>
              <div class="grid grid-cols-2 gap-2">
                <Button variant="secondary" size="lg" onclick={() => openEdit(item)}>Editar</Button>
                <Button variant={item.is_active ? 'ghost' : 'secondary'} size="lg" onclick={() => toggle(item)}>
                  {item.is_active ? 'Desactivar' : 'Reactivar'}
                </Button>
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </section>
  </div>
{/if}

<Modal
  open={modalOpen}
  title={editing ? 'Editar tipo de gasto' : 'Nuevo tipo de gasto'}
  onclose={() => (modalOpen = false)}
  size="md"
>
  <form class="space-y-4" onsubmit={save}>
    {#if formError}
      <p id="expense-type-form-error" class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger" role="alert" aria-live="assertive">{formError}</p>
    {/if}
    <p class="text-sm text-foreground-muted">
      El tipo se configura para la empresa activa y estará disponible en sus documentos de compra.
    </p>
    <FormField
      id="expense-type-name"
      label="Nombre"
      bind:value={name}
      required
      maxlength={120}
      disabled={Boolean(editing?.usage_count)}
      placeholder="Ej. Flete internacional"
    />
    {#if editing?.usage_count}
      <p class="-mt-2 text-xs text-foreground-muted">
        Este tipo aparece en documentos existentes. Su nombre está bloqueado para conservar el historial.
      </p>
    {/if}
    <div>
      <label for="expense-type-description" class="mb-1 block text-sm font-medium text-foreground">Descripción</label>
      <textarea
        id="expense-type-description"
        bind:value={description}
        maxlength="1000"
        rows="3"
        placeholder="Cuándo debe usarse este cargo"
        class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      ></textarea>
    </div>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (modalOpen = false)}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
    </div>
  </form>
</Modal>
