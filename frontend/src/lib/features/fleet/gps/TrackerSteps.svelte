<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import type { TrackerModel } from '../api';
  import CopyField from './CopyField.svelte';
  import Notice from './Notice.svelte';
  import { OTHER_MODEL, SUPPORTED_DEVICES, type SetupStep } from './setup-flow';

  let {
    step,
    models,
    host,
    fieldError,
    onsubmit,
    onedit,
    modelKey = $bindable(),
    identifier = $bindable()
  }: {
    step: SetupStep;
    models: TrackerModel[];
    host: string | null;
    fieldError: string | null;
    onsubmit: () => void;
    onedit: () => void;
    modelKey: string;
    identifier: string;
  } = $props();

  const selected = $derived(models.find((model) => model.key === modelKey) ?? null);
  const describedBy = $derived(
    fieldError ? 'gps-identifier-error gps-identifier-help' : 'gps-identifier-help'
  );
  const canShare = Boolean(navigator.share || navigator.clipboard);
  let shared = $state(false);
  let shareFailed = $state(false);
  let sharedTimer: ReturnType<typeof setTimeout> | undefined;

  /** El paso más difícil suele hacerlo otra persona: los datos deben poder llegarle. */
  async function shareData() {
    const text = `Servidor: ${host}\nPuerto: ${selected?.port}\nIdentificador: ${identifier}`;
    shareFailed = false;
    try {
      if (navigator.share) {
        await navigator.share({ text });
      } else {
        await navigator.clipboard.writeText(text);
        shared = true;
        clearTimeout(sharedTimer);
        sharedTimer = setTimeout(() => (shared = false), 2000);
      }
    } catch (error) {
      // Cancelar el menú de compartir no es un error.
      if ((error as Error).name !== 'AbortError') shareFailed = true;
    }
  }

  $effect(() => () => clearTimeout(sharedTimer));
</script>

{#if step === 'model'}
  <div class="models" role="radiogroup" aria-label="Modelo del GPS">
    {#each models as model (model.key)}
      <label class="model" class:selected={modelKey === model.key}>
        <input type="radio" name="gps-model" value={model.key} bind:group={modelKey} />
        <span>
          <strong>{model.brand}</strong>
          <small>{model.models}</small>
        </span>
      </label>
    {/each}
    <label class="model" class:selected={modelKey === OTHER_MODEL}>
      <input type="radio" name="gps-model" value={OTHER_MODEL} bind:group={modelKey} />
      <span>
        <strong>Otro modelo o no lo sé</strong>
        <small>Te decimos qué hacer</small>
      </span>
    </label>
  </div>
  {#if modelKey === OTHER_MODEL}
    <Notice>
      Hay que confirmar si tu GPS es compatible. Dile al administrador la marca y el modelo que
      aparecen en la caja o en la etiqueta; puede revisarlos en la
      <a href={SUPPORTED_DEVICES} target="_blank" rel="noreferrer">lista oficial de equipos</a>.
    </Notice>
  {/if}
{:else if step === 'identifier'}
  <form
    class="identifier"
    novalidate
    onsubmit={(event) => {
      event.preventDefault();
      onsubmit();
    }}
  >
    <label class="input">
      <span>Identificador del GPS</span>
      <input
        bind:value={identifier}
        oninput={onedit}
        maxlength="64"
        inputmode="text"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        placeholder="Ej. 358240051111110"
        aria-invalid={fieldError ? 'true' : undefined}
        aria-describedby={describedBy}
      />
    </label>
    {#if fieldError}<p class="field-error" id="gps-identifier-error" role="alert">
        {fieldError}
      </p>{/if}
    <p class="help" id="gps-identifier-help">
      Suele ser el <strong>IMEI</strong>: un número de 15 dígitos en la etiqueta del GPS o en su
      caja.
    </p>
  </form>
  {#if selected?.short_identifier}
    <Notice>
      Este modelo puede enviar solo 12 dígitos: los últimos 11 del IMEI con un cero delante. Si no
      llega señal, prueba con ese número.
    </Notice>
  {/if}
{:else if step === 'configure' && selected && host}
  <div class="fields">
    <CopyField label="Servidor" value={host} />
    <CopyField label="Puerto" value={String(selected.port)} />
    <CopyField label="Identificador" value={identifier} />
  </div>
  <Notice>
    Introduce el servidor y el puerto siguiendo el manual de tu {selected.brand}. Cada fabricante lo
    hace a su manera, normalmente con un SMS o con su propio programa.
  </Notice>
  <div class="handoff">
    <p class="help">¿No sabes hacerlo? Pásale estos datos a quien instaló el GPS.</p>
    {#if canShare}
      <Button variant="secondary" size="lg" onclick={() => void shareData()}>
        {shared ? 'Datos copiados' : 'Enviar datos al técnico'}
      </Button>
      {#if shareFailed}
        <p class="field-error" role="alert">No se pudo enviar. Copia los datos de arriba.</p>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .models,
  .fields {
    display: grid;
    gap: 10px;
  }
  .model {
    position: relative;
    display: flex;
    min-height: 60px;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface-elevated));
    cursor: pointer;
  }
  .model:hover {
    background: rgb(var(--surface-hover));
  }
  .model.selected {
    border-color: rgb(var(--foreground));
    box-shadow: inset 0 0 0 1px rgb(var(--foreground));
  }
  .model:focus-within {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  .model input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
  }
  .model strong {
    display: block;
    color: rgb(var(--foreground));
    font-size: 15px;
    font-weight: 600;
  }
  .model small {
    display: block;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .input {
    display: grid;
    gap: 6px;
  }
  .input span {
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 500;
  }
  .input input {
    width: 100%;
    min-height: 48px;
    padding: 0 14px;
    border: 1px solid rgb(var(--control-border));
    border-radius: 12px;
    color: rgb(var(--foreground));
    background: rgb(var(--surface));
    font-size: 16px;
  }
  .input input:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 1px;
  }
  .input input[aria-invalid='true'] {
    border-color: rgb(var(--danger));
  }
  .field-error {
    margin: 0;
    color: rgb(var(--danger));
    font-size: 14px;
  }
  .help {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .help strong {
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  .identifier,
  .handoff {
    display: grid;
    gap: 8px;
  }
</style>
