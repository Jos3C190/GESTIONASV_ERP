<script lang="ts">
  /** Depósito bancario de los turnos cerrados de una sucursal, con su boleta. */
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { posApi } from '#lib/api/pos.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import type { DepositShift, PosDeposit } from '#lib/types/pos.ts';
  import {
    centsToAmount,
    formatDate,
    formatDateTime,
    formatMoney,
    idempotencyKey,
    toCents,
    today
  } from './format.ts';

  let candidates = $state<DepositShift[]>([]);
  let deposits = $state<PosDeposit[]>([]);
  let chosen = $state<string[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let form = $state({ date: today(), bank: '', account: '', slip: '', amount: '', notes: '' });
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let key = $state(idempotencyKey('deposito'));

  const branchId = $derived(branch.id);
  const expected = $derived(
    candidates
      .filter((item) => chosen.includes(item.shift_id))
      .reduce((sum, item) => sum + (toCents(item.amount) ?? 0), 0)
  );
  const amountCents = $derived(toCents(form.amount));
  const difference = $derived(amountCents === null ? null : amountCents - expected);
  const valid = $derived(
    chosen.length > 0 &&
      form.bank.trim().length >= 2 &&
      form.account.trim().length >= 2 &&
      form.slip.trim().length >= 2 &&
      amountCents !== null &&
      amountCents > 0 &&
      form.date !== '' &&
      form.date <= today() &&
      (difference === 0 || form.notes.trim().length >= 5)
  );

  async function load() {
    loading = true;
    error = null;
    try {
      [candidates, deposits] = await Promise.all([
        branchId ? posApi.depositCandidates(branchId) : Promise.resolve([]),
        posApi.deposits(branchId)
      ]);
      chosen = candidates.map((item) => item.shift_id);
      form.amount = centsToAmount(
        candidates.reduce((sum, item) => sum + (toCents(item.amount) ?? 0), 0)
      );
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudieron cargar los depósitos.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void branchId;
    void load();
  });

  function toggle(id: string, on: boolean) {
    chosen = on ? [...chosen, id] : chosen.filter((item) => item !== id);
  }

  async function save() {
    if (!valid || !branchId || amountCents === null) return;
    saving = true;
    formError = null;
    try {
      const created = await posApi.createDeposit({
        branch_id: branchId,
        shift_ids: chosen,
        deposited_on: form.date,
        bank_name: form.bank.trim(),
        account_reference: form.account.trim(),
        slip_number: form.slip.trim(),
        deposited_amount: centsToAmount(amountCents),
        notes: form.notes.trim() || null,
        idempotency_key: key
      });
      notice = `Depósito ${created.code} registrado por ${formatMoney(created.deposited_amount)}.`;
      form = {
        date: today(),
        bank: form.bank,
        account: form.account,
        slip: '',
        amount: '',
        notes: ''
      };
      key = idempotencyKey('deposito');
      await load();
    } catch (err) {
      formError = err instanceof Error ? err.message : 'No se pudo registrar el depósito.';
      if (!(err instanceof HttpError && err.status === 0)) key = idempotencyKey('deposito');
    } finally {
      saving = false;
    }
  }
</script>

<div class="space-y-6">
  {#if notice}
    <div
      class="rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-foreground"
      role="status"
    >
      {notice}
    </div>
  {/if}

  {#if !branchId}
    <div class="rounded-xl border border-border bg-surface p-6 text-sm text-foreground-muted">
      Elige una sucursal en el menú para registrar su depósito. Abajo ves los depósitos de todas tus
      sucursales.
    </div>
  {/if}

  {#if loading}
    <div class="h-48 rounded-xl skeleton" aria-label="Cargando depósitos"></div>
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
  {:else}
    {#if branchId}
      <section
        class="rounded-xl border border-border bg-surface p-5"
        aria-labelledby="deposit-title"
      >
        <h2 id="deposit-title" class="text-base font-semibold text-foreground">Nuevo depósito</h2>
        {#if candidates.length === 0}
          <p class="mt-2 text-sm text-foreground-muted">
            No hay turnos cerrados con efectivo por depositar.
          </p>
        {:else}
          <ul class="mt-3 divide-y divide-border rounded-lg border border-border">
            {#each candidates as item (item.shift_id)}
              <li>
                <label class="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    aria-label={`Depositar el turno ${item.shift_code}`}
                    checked={chosen.includes(item.shift_id)}
                    onchange={(event) =>
                      toggle(item.shift_id, (event.currentTarget as HTMLInputElement).checked)}
                  />
                  <span class="flex-1"
                    >{item.shift_code} · {item.register_code} · {item.cashier_name}<span
                      class="block text-xs text-foreground-muted"
                      >Cerrado {formatDateTime(item.closed_at)}</span
                    ></span
                  >
                  <span class="font-semibold tabular-nums">{formatMoney(item.amount)}</span>
                </label>
              </li>
            {/each}
          </ul>
          <p class="mt-2 text-right text-sm">
            Esperado: <span class="font-semibold tabular-nums"
              >{formatMoney(centsToAmount(expected))}</span
            >
          </p>
          <form
            class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            onsubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <label class="block text-sm font-medium text-foreground"
              >Fecha<input
                type="date"
                max={today()}
                class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                bind:value={form.date}
              /></label
            >
            <label class="block text-sm font-medium text-foreground"
              >Banco<input
                class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                maxlength="80"
                placeholder="Banco Agrícola"
                bind:value={form.bank}
              /></label
            >
            <label class="block text-sm font-medium text-foreground"
              >Cuenta<input
                class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                maxlength="40"
                placeholder="Corriente 0000-0000"
                bind:value={form.account}
              /></label
            >
            <label class="block text-sm font-medium text-foreground"
              >N.º de boleta<input
                class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                maxlength="40"
                bind:value={form.slip}
              /></label
            >
            <label class="block text-sm font-medium text-foreground"
              >Monto depositado<input
                class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm tabular-nums"
                inputmode="decimal"
                bind:value={form.amount}
              /></label
            >
            <div class="text-sm">
              <p class="text-foreground-muted">Diferencia</p>
              <p
                class={`text-lg font-semibold tabular-nums ${difference ? 'text-danger' : 'text-foreground'}`}
              >
                {difference === null
                  ? '—'
                  : difference === 0
                    ? 'Cuadra'
                    : formatMoney(centsToAmount(difference))}
              </p>
            </div>
            {#if difference}
              <label class="block text-sm font-medium text-foreground sm:col-span-2 lg:col-span-3"
                >Explica la diferencia<textarea
                  class="mt-1 w-full rounded-lg border border-border bg-surface p-2 text-sm"
                  rows="2"
                  maxlength="300"
                  bind:value={form.notes}
                ></textarea></label
              >
            {/if}
            {#if formError}
              <p
                class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger sm:col-span-2 lg:col-span-3"
                role="alert"
              >
                {formError}
              </p>
            {/if}
            <div class="flex justify-end sm:col-span-2 lg:col-span-3">
              <Button type="submit" disabled={!valid || saving}
                >{saving ? 'Registrando…' : 'Registrar depósito'}</Button
              >
            </div>
          </form>
        {/if}
      </section>
    {/if}

    <section aria-labelledby="history-title">
      <h2 id="history-title" class="mb-2 text-base font-semibold text-foreground">
        Depósitos registrados
      </h2>
      {#if deposits.length === 0}
        <p class="rounded-xl border border-border bg-surface p-6 text-sm text-foreground-muted">
          Todavía no hay depósitos.
        </p>
      {:else}
        <div class="overflow-x-auto rounded-xl border border-border bg-surface">
          <table class="w-full min-w-[640px] text-sm">
            <thead
              class="bg-surface-muted text-left text-xs uppercase tracking-wider text-foreground-muted"
            >
              <tr
                ><th class="px-4 py-2">Depósito</th><th class="px-4 py-2">Fecha</th><th
                  class="px-4 py-2">Banco y boleta</th
                ><th class="px-4 py-2">Turnos</th><th class="px-4 py-2 text-right">Depositado</th
                ><th class="px-4 py-2 text-right">Diferencia</th></tr
              >
            </thead>
            <tbody class="divide-y divide-border">
              {#each deposits as item (item.id)}
                <tr>
                  <td class="px-4 py-2 font-semibold"
                    >{item.code}<span class="block text-xs font-normal text-foreground-muted"
                      >{item.branch_name}</span
                    ></td
                  >
                  <td class="px-4 py-2 tabular-nums">{formatDate(item.deposited_on)}</td>
                  <td class="px-4 py-2"
                    >{item.bank_name}<span class="block text-xs text-foreground-muted"
                      >{item.slip_number}</span
                    ></td
                  >
                  <td class="px-4 py-2"
                    >{item.shifts.map((shift) => shift.shift_code).join(', ')}</td
                  >
                  <td class="px-4 py-2 text-right tabular-nums"
                    >{formatMoney(item.deposited_amount)}</td
                  >
                  <td
                    class={`px-4 py-2 text-right tabular-nums ${Number(item.difference) !== 0 ? 'font-semibold text-danger' : ''}`}
                    >{Number(item.difference) === 0 ? 'Cuadra' : formatMoney(item.difference)}</td
                  >
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>
  {/if}
</div>
