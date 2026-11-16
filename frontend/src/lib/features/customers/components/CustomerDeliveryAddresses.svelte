<script lang="ts">
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { customersApi } from '#lib/api/customers.ts';
  import GeographyFields from '#lib/features/customers/components/GeographyFields.svelte';
  import { confirmation } from '#lib/stores/confirmation.svelte.ts';
  import type { DeliveryAddress, DeliveryAddressInput } from '#lib/types/customer.ts';

  interface Props {
    customerId: string;
    addresses: DeliveryAddress[];
    canManage: boolean;
    onchange: () => void;
  }

  let { customerId, addresses, canManage, onchange }: Props = $props();

  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';
  const labelClass = 'mb-1 block text-sm font-medium text-foreground';

  let open = $state(false);
  let editing = $state<DeliveryAddress | null>(null);
  let form = $state<DeliveryAddressInput>(blank());
  let saving = $state(false);
  let formError = $state<string | null>(null);

  function blank(): DeliveryAddressInput {
    return {
      label: '',
      address_line: '',
      geography: null,
      latitude: null,
      longitude: null,
      contact_name: null,
      phone: null,
      is_default: false,
      is_active: true
    };
  }

  function nullable(value: string): string | null {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }

  function openCreate() {
    editing = null;
    form = blank();
    formError = null;
    open = true;
  }

  function openEdit(address: DeliveryAddress) {
    editing = address;
    const geo = address.address;
    form = {
      label: address.label,
      address_line: address.address_line,
      geography:
        geo.department_id && geo.municipality_id && geo.district_id
          ? {
              department_id: geo.department_id,
              municipality_id: geo.municipality_id,
              district_id: geo.district_id
            }
          : null,
      latitude: address.latitude,
      longitude: address.longitude,
      contact_name: address.contact_name,
      phone: address.phone,
      is_default: address.is_default,
      is_active: address.is_active
    };
    formError = null;
    open = true;
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    formError = null;
    try {
      if (editing) await customersApi.updateDeliveryAddress(customerId, editing.id, form);
      else await customersApi.addDeliveryAddress(customerId, form);
      open = false;
      onchange();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo guardar la dirección.';
    } finally {
      saving = false;
    }
  }

  function remove(address: DeliveryAddress) {
    confirmation.request({
      kind: 'delete',
      title: 'Quitar dirección de entrega',
      description: 'Las entregas ya registradas conservan la dirección con la que se hicieron.',
      resourceName: address.label,
      confirmLabel: 'Quitar',
      execute: async () => {
        await customersApi.deleteDeliveryAddress(customerId, address.id);
        onchange();
      }
    });
  }
</script>

<section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
  <div
    class="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between"
  >
    <div>
      <h2 class="font-semibold text-foreground">Direcciones de entrega</h2>
      <p class="mt-1 text-sm text-foreground-muted">
        Lugares donde se entrega la mercadería. Las coordenadas sirven para el seguimiento del
        reparto.
      </p>
    </div>
    {#if canManage}
      <Button variant="secondary" size="sm" onclick={openCreate}>Agregar dirección</Button>
    {/if}
  </div>
  {#if addresses.length === 0}
    <p class="p-4 text-sm text-foreground-muted">Sin direcciones de entrega registradas.</p>
  {:else}
    <ul class="divide-y divide-border">
      {#each addresses as address (address.id)}
        <li class="flex flex-col gap-2 p-4 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0 text-sm">
            <p class="flex flex-wrap items-center gap-2 font-medium text-foreground">
              {address.label}
              {#if address.is_default}<Badge variant="primary">Principal</Badge>{/if}
              {#if !address.is_active}<Badge variant="neutral">Inactiva</Badge>{/if}
            </p>
            <p class="break-words text-foreground-muted">
              {address.address_line}{address.address.district
                ? `, ${address.address.district}, ${address.address.municipality}`
                : ''}
            </p>
            {#if address.contact_name || address.phone}
              <p class="text-xs text-foreground-muted">
                {[address.contact_name, address.phone].filter(Boolean).join(' · ')}
              </p>
            {/if}
          </div>
          {#if canManage}
            <div class="flex gap-2">
              <Button variant="secondary" size="sm" onclick={() => openEdit(address)}>Editar</Button
              >
              <Button variant="ghost" size="sm" onclick={() => remove(address)}>Quitar</Button>
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<Modal
  {open}
  title={editing ? `Editar ${editing.label}` : 'Nueva dirección de entrega'}
  onclose={() => (open = false)}
  size="lg"
>
  <form class="space-y-4" onsubmit={save}>
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
        <label for="delivery-label" class={labelClass}>Nombre</label>
        <input
          id="delivery-label"
          bind:value={form.label}
          required
          minlength="2"
          maxlength="80"
          placeholder="Bodega, sucursal centro…"
          class={inputClass}
        />
      </div>
      <div>
        <label for="delivery-contact" class={labelClass}>Contacto</label>
        <input
          id="delivery-contact"
          value={form.contact_name ?? ''}
          oninput={(e) => (form.contact_name = nullable(e.currentTarget.value))}
          maxlength="120"
          class={inputClass}
        />
      </div>
    </div>
    <div>
      <label for="delivery-line" class={labelClass}>Dirección</label>
      <input
        id="delivery-line"
        bind:value={form.address_line}
        required
        minlength="3"
        maxlength="200"
        class={inputClass}
      />
    </div>
    <GeographyFields
      idPrefix="delivery"
      value={form.geography}
      onchange={(value) => (form.geography = value)}
    />
    <div class="grid gap-4 sm:grid-cols-3">
      <div>
        <label for="delivery-phone" class={labelClass}>Teléfono</label>
        <input
          id="delivery-phone"
          value={form.phone ?? ''}
          oninput={(e) => (form.phone = nullable(e.currentTarget.value))}
          maxlength="30"
          class={inputClass}
        />
      </div>
      <div>
        <label for="delivery-lat" class={labelClass}>Latitud</label>
        <input
          id="delivery-lat"
          type="number"
          step="0.000001"
          min="-90"
          max="90"
          value={form.latitude ?? ''}
          oninput={(e) => (form.latitude = nullable(e.currentTarget.value))}
          class={inputClass}
        />
      </div>
      <div>
        <label for="delivery-lng" class={labelClass}>Longitud</label>
        <input
          id="delivery-lng"
          type="number"
          step="0.000001"
          min="-180"
          max="180"
          value={form.longitude ?? ''}
          oninput={(e) => (form.longitude = nullable(e.currentTarget.value))}
          class={inputClass}
        />
      </div>
    </div>
    <div class="flex flex-wrap gap-4">
      <label class="flex min-h-11 items-center gap-2 text-sm text-foreground">
        <input type="checkbox" bind:checked={form.is_default} /> Dirección principal
      </label>
      <label class="flex min-h-11 items-center gap-2 text-sm text-foreground">
        <input type="checkbox" bind:checked={form.is_active} /> Activa
      </label>
    </div>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (open = false)}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
    </div>
  </form>
</Modal>
