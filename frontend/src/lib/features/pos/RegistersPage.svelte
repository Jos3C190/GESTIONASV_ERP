<script lang="ts">
  /** Cajas del punto de venta: cada una usa un punto de venta de la configuración fiscal. */
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { posApi } from '#lib/api/pos.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import type { PointOfSaleOption, PosRegister } from '#lib/types/pos.ts';
  import { formatMoney, toCents } from './format.ts';

  let registers = $state<PosRegister[]>([]);
  let options = $state<PointOfSaleOption[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let editing = $state<PosRegister | 'new' | null>(null);
  let form = $state({
    point: '',
    code: '',
    name: '',
    opening: '50.00',
    threshold: '20.00',
    limit: '',
    active: true
  });
  let saving = $state(false);
  let formError = $state<string | null>(null);

  const available = $derived(options.filter((item) => item.available));
  const valid = $derived(
    (editing !== 'new' || form.point !== '') &&
      /^[A-Za-z0-9][A-Za-z0-9-]{1,19}$/.test(form.code.trim()) &&
      form.name.trim().length >= 2 &&
      toCents(form.opening) !== null &&
      toCents(form.threshold) !== null &&
      (form.limit.trim() === '' || toCents(form.limit) !== null)
  );

  async function load() {
    loading = true;
    error = null;
    try {
      const [found, points] = await Promise.all([
        posApi.registers(branch.id),
        posApi.pointOfSaleOptions()
      ]);
      registers = found;
      // Con una sucursal elegida, solo se ofrecen sus puntos de venta: la caja nueva aparece aquí.
      options = branch.id ? points.filter((item) => item.branch_id === branch.id) : points;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudieron cargar las cajas.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void branch.id;
    void load();
  });

  function start(register: PosRegister | 'new') {
    editing = register;
    formError = null;
    form =
      register === 'new'
        ? {
            point: available.length === 1 ? available[0]!.id : '',
            code: '',
            name: '',
            opening: '50.00',
            threshold: '20.00',
            limit: '',
            active: true
          }
        : {
            point: register.point_of_sale_id,
            code: register.code,
            name: register.name,
            opening: register.opening_float,
            threshold: register.cash_out_approval_threshold,
            limit: register.cash_drawer_limit ?? '',
            active: register.is_active
          };
  }

  async function save() {
    if (!valid || editing === null) return;
    saving = true;
    formError = null;
    const input = {
      code: form.code.trim().toUpperCase(),
      name: form.name.trim(),
      opening_float: form.opening.trim(),
      cash_out_approval_threshold: form.threshold.trim(),
      cash_drawer_limit: form.limit.trim() || null,
      is_active: form.active
    };
    try {
      if (editing === 'new') await posApi.createRegister(form.point, input);
      else await posApi.updateRegister(editing.id, editing.version, input);
      editing = null;
      await load();
    } catch (err) {
      formError = err instanceof Error ? err.message : 'No se pudo guardar la caja.';
    } finally {
      saving = false;
    }
  }
</script>

<div class="space-y-4">
  <div class="flex justify-end">
    <Button onclick={() => start('new')} disabled={loading || available.length === 0}
      >Nueva caja</Button
    >
  </div>

  {#if loading}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each [1, 2, 3] as item (item)}<div class="h-32 rounded-xl skeleton"></div>{/each}
    </div>
  {:else if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <p>{error}</p>
      <div class="mt-3">
        <Button variant="secondary" size="sm" onclick={load}>Reintentar</Button>
      </div>
    </div>
  {:else if registers.length === 0}
    <div
      class="flex flex-col items-center rounded-xl border border-border bg-surface p-10 text-center"
    >
      <span
        class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-subtle"
        aria-hidden="true"
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          ><rect x="3" y="7" width="18" height="12" rx="2" /><path d="M7 7V5h10v2M3 12h18" /></svg
        >
      </span>
      <p class="mt-3 font-semibold text-foreground">Todavía no hay cajas</p>
      <p class="mt-1 max-w-md text-sm text-foreground-muted">
        {available.length
          ? 'Crea una caja sobre uno de los puntos de venta de la configuración fiscal.'
          : 'Primero registra un punto de venta para la sucursal en Configuración fiscal.'}
      </p>
      {#if available.length}
        <div class="mt-4"><Button onclick={() => start('new')}>Nueva caja</Button></div>
      {:else}
        <a
          href="/sales/fiscal-settings"
          class="mt-4 inline-flex h-9 items-center rounded-lg border border-border px-4 text-sm font-medium text-foreground hover:bg-surface-hover"
          >Ir a Configuración fiscal</a
        >
      {/if}
    </div>
  {:else}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each registers as item (item.id)}
        <article class="rounded-xl border border-border bg-surface p-4">
          <div class="flex items-start justify-between gap-2">
            <div>
              <h2 class="text-base font-semibold text-foreground">{item.code}</h2>
              <p class="text-sm text-foreground-muted">{item.name}</p>
            </div>
            <Badge variant={item.is_active ? 'success' : 'neutral'}
              >{item.is_active ? 'Activa' : 'Inactiva'}</Badge
            >
          </div>
          <dl class="mt-3 space-y-1 text-sm">
            <div class="flex justify-between">
              <dt class="text-foreground-muted">Sucursal</dt>
              <dd>{item.branch_name}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-foreground-muted">Punto de venta</dt>
              <dd>{item.establishment_code}{item.point_of_sale_code}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-foreground-muted">Fondo</dt>
              <dd class="tabular-nums">{formatMoney(item.opening_float)}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-foreground-muted">Salidas sin supervisor hasta</dt>
              <dd class="tabular-nums">{formatMoney(item.cash_out_approval_threshold)}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-foreground-muted">Límite en gaveta</dt>
              <dd class="tabular-nums">
                {item.cash_drawer_limit ? formatMoney(item.cash_drawer_limit) : 'Sin límite'}
              </dd>
            </div>
          </dl>
          {#if item.unclosed_shift_cashier}
            <p class="mt-3 text-xs text-foreground-muted">
              Turno sin cerrar de {item.unclosed_shift_cashier}
            </p>
          {/if}
          <div class="mt-3 flex justify-end">
            <Button variant="secondary" size="sm" onclick={() => start(item)}>Editar</Button>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</div>

<Modal
  open={editing !== null}
  title={editing === 'new' ? 'Nueva caja' : 'Editar caja'}
  onclose={() => (editing = null)}
  size="md"
>
  <form
    id="register-form"
    class="space-y-3"
    onsubmit={(event) => {
      event.preventDefault();
      void save();
    }}
  >
    {#if editing === 'new'}
      <label class="block text-sm font-medium text-foreground">
        Punto de venta fiscal
        <select
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
          value={form.point}
          onchange={(event) => (form.point = (event.currentTarget as HTMLSelectElement).value)}
        >
          <option value="">Elige el punto de venta</option>
          {#each options as option (option.id)}
            <option value={option.id} disabled={!option.available}>
              {option.branch_name} · {option.establishment_code}{option.code}
              {option.name}{option.unavailable_reason ? ` (${option.unavailable_reason})` : ''}
            </option>
          {/each}
        </select>
      </label>
    {/if}
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="block text-sm font-medium text-foreground">
        Código
        <input
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm uppercase"
          maxlength="20"
          placeholder="CAJA-01"
          disabled={editing !== 'new' && editing?.has_shifts}
          bind:value={form.code}
        />
      </label>
      <label class="block text-sm font-medium text-foreground">
        Nombre
        <input
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
          maxlength="80"
          placeholder="Caja principal"
          bind:value={form.name}
        />
      </label>
      <label class="block text-sm font-medium text-foreground">
        Fondo de la caja
        <input
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm tabular-nums"
          inputmode="decimal"
          bind:value={form.opening}
        />
      </label>
      <label class="block text-sm font-medium text-foreground">
        Salidas sin supervisor hasta
        <input
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm tabular-nums"
          inputmode="decimal"
          bind:value={form.threshold}
        />
      </label>
      <label class="block text-sm font-medium text-foreground sm:col-span-2">
        Límite de efectivo en gaveta <span class="font-normal text-foreground-subtle"
          >(opcional: avisa que toca un retiro)</span
        >
        <input
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm tabular-nums"
          inputmode="decimal"
          bind:value={form.limit}
        />
      </label>
    </div>
    {#if editing !== 'new' && editing?.has_shifts}
      <p class="text-xs text-foreground-muted">
        El código de una caja con turnos no cambia: aparece en sus tiquetes y cierres.
      </p>
    {/if}
    <label class="flex items-center gap-2 text-sm text-foreground">
      <input
        type="checkbox"
        checked={form.active}
        onchange={(event) => (form.active = (event.currentTarget as HTMLInputElement).checked)}
      />
      Caja activa
    </label>
    {#if formError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {formError}
      </p>
    {/if}
  </form>
  {#snippet footer()}
    <Button variant="secondary" onclick={() => (editing = null)}>Cancelar</Button>
    <Button type="submit" form="register-form" disabled={!valid || saving}
      >{saving ? 'Guardando…' : 'Guardar'}</Button
    >
  {/snippet}
</Modal>
