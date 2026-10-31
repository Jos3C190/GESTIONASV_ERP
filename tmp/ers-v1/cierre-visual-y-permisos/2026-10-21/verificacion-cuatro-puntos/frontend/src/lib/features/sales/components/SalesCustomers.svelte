<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import type { SalesCustomer } from '$lib/types/sales';

  let customers = $state<SalesCustomer[]>([]);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let search = $state('');
  let editingId = $state<string | null>(null);
  let code = $state('');
  let name = $state('');
  let phone = $state('');
  let email = $state('');

  async function load() {
    loading = true;
    error = null;
    try {
      customers = (await salesApi.customers({ search, active: null, size: 100 })).items;
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar los clientes.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  function beginEdit(customer: SalesCustomer) {
    editingId = customer.id;
    code = customer.code;
    name = customer.name;
    phone = customer.phone ?? '';
    email = customer.email ?? '';
    success = null;
    error = null;
  }

  function resetForm() {
    editingId = null;
    code = '';
    name = '';
    phone = '';
    email = '';
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    error = null;
    success = null;
    try {
      if (editingId) {
        await salesApi.updateCustomer(editingId, { name, phone: phone || null, email: email || null });
        success = 'Cambios guardados. Los documentos anteriores conservan sus datos.';
      } else {
        await salesApi.createCustomer({ code: code.trim(), name: name.trim(), phone: phone || null, email: email || null });
        success = 'Cliente registrado.';
      }
      resetForm();
      await load();
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo guardar el cliente.';
    } finally {
      saving = false;
    }
  }

  async function toggleActive(customer: SalesCustomer) {
    const action = customer.is_active ? 'desactivar' : 'activar';
    if (!window.confirm(`¿${action[0]?.toUpperCase()}${action.slice(1)} a ${customer.name}?`)) return;
    error = null;
    try {
      await salesApi.updateCustomer(customer.id, { is_active: !customer.is_active });
      success = customer.is_active ? 'Cliente desactivado; su historial se conserva.' : 'Cliente activado.';
      await load();
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo actualizar el cliente.';
    }
  }
</script>

<svelte:head><title>Clientes | GestionaSV</title></svelte:head>

<main class="mx-auto max-w-7xl space-y-5 px-4 pb-10 pt-6 sm:px-6">
  <header class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
    <div><p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas</p><h1 class="mt-1 text-2xl font-bold text-foreground">Clientes</h1><p class="mt-1 text-sm text-foreground-muted">Catálogo comercial de esta empresa. Desactivar conserva cotizaciones y ventas anteriores.</p></div>
    <p class="text-sm text-foreground-muted">{customers.length} cliente(s)</p>
  </header>

  {#if error}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}<button class="ml-3 underline" onclick={() => void load()}>Reintentar</button></div>{/if}
  {#if success}<div class="rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success" role="status">{success}</div>{/if}

  <section class="rounded-xl border border-border bg-surface p-5">
    <h2 class="text-base font-semibold text-foreground">{editingId ? 'Editar cliente' : 'Registrar cliente'}</h2>
    <form class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5" onsubmit={save}>
      {#if !editingId}<label class="block text-sm text-foreground-muted">Código<input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" bind:value={code} maxlength="40" required autocomplete="off" /></label>{/if}
      <label class="block text-sm text-foreground-muted sm:col-span-2">Nombre comercial<input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" bind:value={name} maxlength="200" required autocomplete="organization" /></label>
      <label class="block text-sm text-foreground-muted">Teléfono (opcional)<input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" bind:value={phone} maxlength="40" autocomplete="tel" /></label>
      <label class="block text-sm text-foreground-muted">Correo (opcional)<input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" bind:value={email} type="email" maxlength="320" autocomplete="email" /></label>
      <div class="flex gap-2 sm:col-span-2 lg:col-span-5">
        <button class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" disabled={saving}>{saving ? 'Guardando…' : editingId ? 'Guardar cambios' : 'Guardar cliente'}</button>
        {#if editingId}<button type="button" class="rounded-md border border-border px-4 py-2 text-sm text-foreground" onclick={resetForm}>Cancelar edición</button>{/if}
      </div>
    </form>
  </section>

  <section class="rounded-xl border border-border bg-surface">
    <div class="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between"><h2 class="font-semibold text-foreground">Directorio</h2><div class="flex gap-2"><input aria-label="Buscar clientes" placeholder="Código o nombre" class="h-9 rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={search} onkeydown={(e) => e.key === 'Enter' && void load()} /><button class="rounded-md border border-border px-3 text-sm text-foreground" onclick={() => void load()}>Buscar</button></div></div>
    {#if loading}<p class="p-8 text-center text-sm text-foreground-muted">Cargando clientes…</p>{:else if customers.length === 0}<p class="p-8 text-center text-sm text-foreground-muted">No hay clientes para mostrar. Registra uno arriba para iniciar una cotización.</p>{:else}<div class="overflow-x-auto"><table class="w-full min-w-[700px] text-left text-sm"><thead class="bg-surface-muted text-xs uppercase text-foreground-muted"><tr><th class="px-4 py-3">Código</th><th class="px-4 py-3">Cliente</th><th class="px-4 py-3">Contacto</th><th class="px-4 py-3">Estado</th><th class="px-4 py-3 text-right">Acciones</th></tr></thead><tbody class="divide-y divide-border">{#each customers as customer (customer.id)}<tr><td class="px-4 py-3 font-mono text-xs text-foreground">{customer.code}</td><td class="px-4 py-3 font-medium text-foreground">{customer.name}</td><td class="px-4 py-3 text-foreground-muted">{customer.phone || '—'}<br />{customer.email || ''}</td><td class="px-4 py-3"><span class={customer.is_active ? 'rounded-full bg-success/10 px-2 py-1 text-xs text-success' : 'rounded-full bg-surface-muted px-2 py-1 text-xs text-foreground-muted'}>{customer.is_active ? 'Activo' : 'Inactivo'}</span></td><td class="px-4 py-3 text-right"><button class="mr-3 text-primary hover:underline" onclick={() => beginEdit(customer)}>Editar</button><button class="text-foreground-muted hover:text-foreground" onclick={() => void toggleActive(customer)}>{customer.is_active ? 'Desactivar' : 'Activar'}</button></td></tr>{/each}</tbody></table></div>{/if}
  </section>
</main>
