<script lang="ts">
  import {
    api,
    HttpError,
    type DocumentCategoryOut,
    type DocumentRecordOut
  } from '$lib/api/client';
  import Button from '$lib/components/ui/Button.svelte';
  import FormField from '$lib/components/ui/FormField.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';

  interface Props {
    document: DocumentRecordOut;
    categories: DocumentCategoryOut[];
    employeeId?: string;
    onclose: () => void;
    onsaved?: (document: DocumentRecordOut) => void;
  }

  let { document, categories, employeeId, onclose, onsaved }: Props = $props();
  let categoryId = $state('');
  let title = $state('');
  let description = $state('');
  let referenceCode = $state('');
  let issuer = $state('');
  let issuedOn = $state('');
  let expiresOn = $state('');
  let confidentiality = $state<'internal' | 'restricted'>('restricted');
  let tagsText = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    const id = document.id;
    void id;
    categoryId = document.category_id;
    title = document.title;
    description = document.description ?? '';
    referenceCode = document.reference_code ?? '';
    issuer = document.issuer ?? '';
    issuedOn = document.issued_on ?? '';
    expiresOn = document.expires_on ?? '';
    confidentiality = document.confidentiality;
    tagsText = document.tags.join(', ');
  });

  async function save() {
    if (!title.trim() || !categoryId) {
      error = 'El título y la categoría son obligatorios.';
      return;
    }
    saving = true;
    error = null;
    try {
      const payload = {
        category_id: categoryId,
        title: title.trim(),
        description: description.trim() || undefined,
        reference_code: referenceCode.trim() || undefined,
        issuer: issuer.trim() || undefined,
        issued_on: issuedOn || undefined,
        expires_on: expiresOn || undefined,
        confidentiality,
        tags: tagsText
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean)
      };
      const updated = employeeId
        ? await api.documents.updateEmployee(employeeId, document.id, payload)
        : await api.documents.update(document.id, payload);
      onsaved?.(updated);
      onclose();
    } catch (err) {
      error = err instanceof HttpError ? err.message : 'No se pudieron guardar los metadatos.';
    } finally {
      saving = false;
    }
  }
</script>

<Modal open={true} title="Editar metadatos" size="lg" {onclose}>
  <form
    class="space-y-4"
    onsubmit={(event) => {
      event.preventDefault();
      void save();
    }}
  >
    {#if error}<div
        class="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
        role="alert"
      >
        {error}
      </div>{/if}
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <FormField
        id="document-edit-category"
        label="Categoría"
        bind:value={categoryId}
        options={categories
          .filter((item) => item.is_active || item.id === document.category_id)
          .map((item) => ({ value: item.id, label: item.name }))}
        required
      />
      <FormField
        id="document-edit-title"
        label="Título"
        bind:value={title}
        required
        maxlength={200}
      />
      <FormField
        id="document-edit-reference"
        label="Código o referencia"
        bind:value={referenceCode}
        maxlength={120}
      />
      <FormField id="document-edit-issuer" label="Emisor" bind:value={issuer} maxlength={180} />
      <FormField
        id="document-edit-issued"
        label="Fecha de emisión"
        type="date"
        bind:value={issuedOn}
      />
      <FormField
        id="document-edit-expires"
        label="Fecha de vencimiento"
        type="date"
        bind:value={expiresOn}
      />
      <FormField
        id="document-edit-confidentiality"
        label="Visibilidad"
        bind:value={confidentiality}
        options={[
          { value: 'restricted', label: 'Restringido' },
          { value: 'internal', label: 'Interno' }
        ]}
      />
      <FormField
        id="document-edit-tags"
        label="Etiquetas"
        bind:value={tagsText}
        placeholder="contrato, 2026"
      />
    </div>
    <div>
      <label for="document-edit-description" class="mb-1 block text-sm font-medium text-foreground"
        >Descripción</label
      >
      <textarea
        id="document-edit-description"
        bind:value={description}
        rows="3"
        maxlength="4000"
        class="w-full resize-none rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      ></textarea>
    </div>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={onclose} disabled={saving}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar cambios'}</Button>
    </div>
  </form>
</Modal>
