<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import SingleImageEditor from '$lib/features/suppliers/components/SingleImageEditor.svelte';
  import { suppliersApi } from '$lib/api/suppliers';
  import { api, HttpError } from '$lib/api/client';
  import type { Supplier, SupplierContact, SupplierImageDraft } from '$lib/types/supplier';
  import { company } from '$lib/stores/company.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import { confirmation } from '$lib/stores/confirmation.svelte';

  let supplierId = $derived(Number(page.params.id));
  let supplier = $state<Supplier | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let editingId = $state<number | null>(null);
  let name = $state('');
  let phone = $state('');
  let email = $state('');
  let image = $state<SupplierImageDraft | null>(null);

  let canManage = $derived(permissions.hasPermission('suppliers:manage'));
  let canEditImages = $derived(permissions.hasPermission('suppliers:images'));
  let canUploadImages = $derived(permissions.hasPermission('media.upload'));

  function imageDraft(value: SupplierContact['avatar_image']): SupplierImageDraft | null {
    return value
      ? {
          id: value.id,
          source_type: value.source_type,
          url: value.url,
          media_asset_id: value.media_asset_id ?? null,
          alt_text: value.alt_text ?? null
        }
      : null;
  }

  async function load() {
    loading = true;
    error = null;
    try {
      supplier = await suppliersApi.getSupplier(supplierId);
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudieron cargar los contactos.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (supplierId > 0) void load();
  });

  function resetForm() {
    editingId = null;
    name = '';
    phone = '';
    email = '';
    image = null;
  }

  function editContact(contact: SupplierContact) {
    editingId = contact.id_supplier_contact;
    name = contact.full_name;
    phone = contact.phone ?? '';
    email = contact.email ?? '';
    image = imageDraft(contact.avatar_image);
    success = null;
  }

  async function saveContact(event: SubmitEvent) {
    event.preventDefault();
    if (!canManage || !name.trim()) return;
    saving = true;
    error = null;
    success = null;
    try {
      const payload = {
        full_name: name.trim(),
        phone: phone.trim() || null,
        email: email.trim() || null,
        ...(canEditImages ? { image } : {})
      };
      if (editingId) await suppliersApi.updateContact(editingId, payload);
      else await suppliersApi.addContact(supplierId, payload);
      success = editingId
        ? 'Contacto actualizado correctamente.'
        : 'Contacto agregado correctamente.';
      resetForm();
      await load();
    } catch (err: unknown) {
      error =
        err instanceof HttpError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo guardar el contacto.';
    } finally {
      saving = false;
    }
  }

  function toggleContact(contact: SupplierContact) {
    if (!canManage) return;
    if (contact.is_active) {
      confirmation.request({
        kind: 'deactivate',
        title: 'Desactivar contacto',
        description:
          'El contacto dejará de estar disponible para nuevas gestiones. Su historial se conservará.',
        resourceName: contact.full_name,
        confirmLabel: 'Desactivar',
        execute: async () => {
          await suppliersApi.deactivateContact(contact.id_supplier_contact);
          await load();
        }
      });
      return;
    }
    void suppliersApi
      .updateContact(contact.id_supplier_contact, { is_active: true })
      .then(load)
      .catch((err: unknown) => {
        error = err instanceof Error ? err.message : 'No se pudo activar el contacto.';
      });
  }

  function deleteContact(contact: SupplierContact) {
    if (!permissions.hasPermission('suppliers:delete')) return;
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar contacto',
      description: `El contacto "${contact.full_name}" se enviará a la Papelera.`,
      resourceName: contact.full_name,
      confirmLabel: 'Eliminar contacto',
      requireReason: true,
      execute: async (reason) => {
        if (!reason) return;
        await api.lifecycle.delete(
          'supplier_contacts',
          String(contact.id_supplier_contact),
          reason
        );
        await load();
      }
    });
  }
</script>

<svelte:head
  ><title
    >{supplier ? `Contactos — ${supplier.name}` : 'Contactos del proveedor — GestionaSV'}</title
  ></svelte:head
>

<div class="min-h-full bg-background px-4 pb-8 sm:px-6 md:px-8">
  <header class="mb-6 flex items-center gap-3 border-b border-border pb-4 pt-5 md:pt-8">
    <button
      type="button"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-hover hover:text-foreground"
      aria-label="Volver al proveedor"
      onclick={() => goto(`/suppliers/${supplierId}`)}
      ><svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
        ><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg
      ></button
    >
    <div class="min-w-0 flex-1">
      <h1 class="text-xl font-bold text-foreground">Contactos del proveedor</h1>
      <p class="text-sm text-foreground-muted">
        {supplier ? supplier.name : 'Gestiona las personas de contacto.'}
      </p>
    </div>
    {#if supplier}<Button
        variant="secondary"
        size="sm"
        onclick={() => goto(`/suppliers/${supplierId}`)}>Ver proveedor</Button
      >{/if}
  </header>

  {#if success}<div
      class="mb-5 rounded-xl border border-success/30 bg-success/10 p-4 text-sm text-success"
      role="status"
    >
      {success}
    </div>{/if}
  {#if loading}<div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div class="h-96 rounded-xl skeleton"></div>
      <div class="h-96 rounded-xl skeleton"></div>
    </div>{:else if error}<div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>{:else if supplier}<div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
      <Card class="overflow-hidden p-0"
        ><div class="border-b border-border px-5 py-4">
          <h2 class="text-base font-semibold text-foreground">Contactos registrados</h2>
          <p class="mt-1 text-sm text-foreground-muted">
            {supplier.contacts?.length ?? 0} contacto(s) asociados.
          </p>
        </div>
        {#if supplier.contacts?.length}<div class="divide-y divide-border">
            {#each supplier.contacts as contact}<div class="flex items-center gap-3 px-5 py-4">
                <div
                  class="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-surface-muted text-sm font-semibold text-foreground-muted"
                >
                  {#if contact.avatar_image?.url}<img
                      src={contact.avatar_image.url}
                      alt={contact.avatar_image.alt_text || contact.full_name}
                      loading="lazy"
                      referrerpolicy="no-referrer"
                      class="h-full w-full object-cover"
                    />{:else}{contact.full_name.slice(0, 1).toUpperCase()}{/if}
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="truncate text-sm font-medium text-foreground">{contact.full_name}</p>
                    <Badge variant={contact.is_active ? 'success' : 'neutral'}
                      >{contact.is_active ? 'Activo' : 'Inactivo'}</Badge
                    >
                  </div>
                  <p class="mt-1 truncate text-xs text-foreground-muted">
                    {contact.email || 'Sin correo'}{contact.phone ? ` · ${contact.phone}` : ''}
                  </p>
                </div>
                {#if canManage}<div class="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      class="rounded-md px-2 py-1 text-xs text-foreground-muted hover:bg-surface-hover hover:text-foreground"
                      onclick={() => editContact(contact)}>Editar</button
                    ><button
                      type="button"
                      class="rounded-md px-2 py-1 text-xs text-foreground-muted hover:bg-surface-hover hover:text-foreground"
                      onclick={() => toggleContact(contact)}
                      >{contact.is_active ? 'Desactivar' : 'Activar'}</button
                    >{#if permissions.hasPermission('suppliers:delete')}<button
                        type="button"
                        class="rounded-md px-2 py-1 text-xs text-danger hover:bg-danger/10"
                        onclick={() => deleteContact(contact)}>Eliminar</button
                      >{/if}
                  </div>{/if}
              </div>{/each}
          </div>{:else}<div
            class="flex flex-col items-center justify-center px-5 py-16 text-center"
          >
            <div
              class="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface-muted text-foreground-muted"
            >
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.6"
                aria-hidden="true"
                ><circle cx="9" cy="7" r="3" /><path
                  d="M3 20a6 6 0 0112 0M16 11a3 3 0 100-6M17 14a5 5 0 014 5"
                /></svg
              >
            </div>
            <p class="text-sm font-medium text-foreground">Aún no hay contactos</p>
            <p class="mt-1 text-xs text-foreground-muted">
              Agrega la primera persona responsable del proveedor.
            </p>
          </div>{/if}</Card
      >

      {#if canManage}<Card class="p-5"
          ><div class="mb-4">
            <h2 class="text-base font-semibold text-foreground">
              {editingId ? 'Editar contacto' : 'Nuevo contacto'}
            </h2>
            <p class="mt-1 text-sm text-foreground-muted">
              Los datos de contacto son opcionales salvo el nombre.
            </p>
          </div>
          <form onsubmit={saveContact} class="space-y-4">
            <div class="space-y-3">
              <label for="contact-name" class="block text-sm font-medium text-foreground"
                >Nombre completo <span class="text-danger">*</span></label
              ><input
                id="contact-name"
                required
                minlength="2"
                maxlength="150"
                bind:value={name}
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Nombre y apellido"
              /><label for="contact-phone" class="block text-sm font-medium text-foreground"
                >Teléfono</label
              ><input
                id="contact-phone"
                maxlength="50"
                bind:value={phone}
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="+503 0000-0000"
              /><label for="contact-email" class="block text-sm font-medium text-foreground"
                >Correo electrónico</label
              ><input
                id="contact-email"
                type="email"
                maxlength="150"
                bind:value={email}
                class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="contacto@empresa.com"
              />
            </div>
            <SingleImageEditor
              bind:image
              companyId={company.id ?? ''}
              purpose="supplier_contact_avatar"
              label="Fotografía del contacto"
              emptyLabel="Avatar opcional para identificarlo."
              altFallback={name || 'Contacto del proveedor'}
              editable={canEditImages}
              canUpload={canUploadImages}
            />
            <div class="flex justify-end gap-2 border-t border-border pt-4">
              {#if editingId}<Button type="button" variant="secondary" size="sm" onclick={resetForm}
                  >Cancelar</Button
                >{/if}<Button type="submit" size="sm" disabled={saving}
                >{saving
                  ? 'Guardando…'
                  : editingId
                    ? 'Guardar cambios'
                    : 'Agregar contacto'}</Button
              >
            </div>
          </form></Card
        >{:else}<Card class="p-5"
          ><h2 class="text-base font-semibold text-foreground">Modo lectura</h2>
          <p class="mt-2 text-sm text-foreground-muted">
            Se requiere <strong>suppliers:manage</strong> para crear o editar contactos.
          </p></Card
        >{/if}
    </div>{/if}
</div>
