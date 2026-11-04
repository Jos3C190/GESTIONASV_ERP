<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import FleetIcon from '$lib/features/fleet/FleetIcon.svelte';
  import ImageLightbox from '$lib/features/fleet/ImageLightbox.svelte';
  import { fieldsToReview, issuesFor } from './review';
  import type { CaptureConfig, CaptureIssue, CaptureSide, CaptureValues } from './types';

  type Reading = 'analyzing' | 'slow' | 'failed' | 'unavailable' | 'done';

  let {
    config,
    values,
    issues,
    fills,
    previews,
    reading,
    unread,
    touched,
    canOverride,
    acknowledged = $bindable(false),
    overrideReason = $bindable(''),
    onedit,
    onretake
  }: {
    config: Pick<
      CaptureConfig<unknown>,
      'documentName' | 'title' | 'fields' | 'groups' | 'mismatchStop' | 'acknowledge' | 'fillNote'
    >;
    values: CaptureValues;
    issues: CaptureIssue[];
    fills: readonly string[];
    previews: Record<CaptureSide, string | null>;
    reading: Reading;
    unread: string[];
    touched: ReadonlySet<string>;
    canOverride: boolean;
    acknowledged?: boolean;
    overrideReason?: string;
    onedit: (key: string, value: string) => void;
    onretake: () => void;
  } = $props();

  const uid = $props.id();
  const STATUS: Record<Reading, string> = $derived({
    analyzing: `Leyendo ${config.documentName}. Puedes escribir los datos mientras tanto.`,
    slow: 'La lectura está tardando más de lo normal. Puedes continuar a mano.',
    failed: 'No se pudieron leer los datos. Escríbelos revisando la foto.',
    unavailable: 'La lectura automática no está disponible. Escribe los datos revisando la foto.',
    done: 'Revisa cada dato contra la foto antes de confirmar.'
  });
  const images = $derived(
    (['front', 'back'] as const).flatMap((side) => {
      const src = previews[side];
      return src ? [{ side, src, alt: side === 'front' ? 'Frente' : 'Reverso' }] : [];
    })
  );
  const mismatches = $derived(issues.filter((issue) => issue.severity === 'mismatch'));
  const warnings = $derived(issues.filter((issue) => issue.severity === 'warning'));
  const flagged = $derived(fieldsToReview(issues, config.groups));
  let zoomed = $state<number | null>(null);
  let zoomOrigin: HTMLButtonElement | null = null;

  const field = (key: string) => config.fields[key] ?? { label: key, hint: undefined };

  function focusField(key: string) {
    const input = document.getElementById(`${uid}-${key}`);
    input?.focus();
    input?.scrollIntoView({ block: 'center' });
  }

  function describedBy(key: string): string | undefined {
    const ids = [
      field(key).hint ? `${uid}-${key}-hint` : null,
      fills.includes(key) ? `${uid}-${key}-fill` : null,
      issuesFor(issues, key).length ? `${uid}-${key}-issues` : null
    ].filter(Boolean);
    return ids.length ? ids.join(' ') : undefined;
  }
</script>

<div class="review">
  <div class="photos">
    <div class="thumbs">
      {#each images as image, index (image.side)}
        <button
          type="button"
          class="thumb"
          aria-label={`Ampliar ${image.alt.toLowerCase()}`}
          onclick={(event) => {
            zoomOrigin = event.currentTarget;
            zoomed = index;
          }}
        >
          <img src={image.src} alt={image.alt} width="856" height="540" />
          <span>{image.alt}</span>
        </button>
      {/each}
    </div>
    <Button variant="ghost" size="sm" onclick={onretake}>
      <FleetIcon name="refresh" size={14} />Repetir fotos
    </Button>
  </div>

  <div class="form">
    <p class="status" class:busy={reading === 'analyzing' || reading === 'slow'} role="status">
      {STATUS[reading]}
    </p>

    {#if unread.length > 0}
      <div class="unread" role="status">
        <p>
          No pudimos leer: {unread.map((key) => field(key).label).join(', ')}. Repite la
          foto o escríbelos revisando la imagen.
        </p>
        <Button variant="secondary" size="sm" onclick={onretake}>Repetir foto</Button>
      </div>
    {/if}

    {#if flagged.length > 0}
      <nav class="to-review" aria-label="Datos por revisar">
        <span>Por revisar:</span>
        {#each flagged as key (key)}
          <button type="button" onclick={() => focusField(key)}>{field(key).label}</button>
        {/each}
      </nav>
    {/if}

    {#each config.groups as group (group.title)}
      <fieldset>
        <legend>{group.title}</legend>
        <div class="grid">
          {#each group.fields as key (key)}
            {@const fieldIssues = issuesFor(issues, key)}
            <div class="field">
              <label for={`${uid}-${key}`}>{field(key).label}</label>
              <input
                id={`${uid}-${key}`}
                value={values[key] ?? ''}
                class:reading={reading === 'analyzing' && !values[key] && !touched.has(key)}
                autocomplete="off"
                autocapitalize="characters"
                autocorrect="off"
                spellcheck="false"
                enterkeyhint="next"
                aria-invalid={fieldIssues.some((issue) => issue.severity !== 'warning')}
                aria-describedby={describedBy(key)}
                oninput={(event) => onedit(key, event.currentTarget.value)}
              />
              {#if field(key).hint}
                <small id={`${uid}-${key}-hint`}>{field(key).hint}</small>
              {/if}
              {#if fills.includes(key) && config.fillNote}
                <small id={`${uid}-${key}-fill`}>{config.fillNote}</small>
              {/if}
              {#if fieldIssues.length > 0}
                <div id={`${uid}-${key}-issues`}>
                  {#each fieldIssues as issue (issue.code)}
                    <p class={`issue ${issue.severity}`}>{issue.message}</p>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </fieldset>
    {/each}

    {#if mismatches.length > 0}
      {#if canOverride}
        <div class="field">
          <label for={`${uid}-reason`}>Motivo de la excepción</label>
          <textarea id={`${uid}-reason`} rows="2" bind:value={overrideReason} maxlength="500"
          ></textarea>
        </div>
      {:else}
        <p class="stop" role="alert">{config.mismatchStop}</p>
      {/if}
    {/if}

    {#if warnings.length > 0}
      <label class="check">
        <input type="checkbox" bind:checked={acknowledged} />
        <span>{config.acknowledge}</span>
      </label>
    {/if}

    <p class="note">
      Estas comprobaciones revisan que los datos sean coherentes; no certifican que el documento sea
      auténtico.
    </p>
  </div>
</div>

{#if zoomed !== null}
  <ImageLightbox
    images={images.map((image) => ({ src: image.src, alt: image.alt }))}
    bind:index={zoomed}
    title={config.title}
    layer={1100}
    onclose={() => {
      zoomed = null;
      // Vuelve a la miniatura: quien usa teclado sigue donde estaba.
      requestAnimationFrame(() => zoomOrigin?.focus());
    }}
  />
{/if}

<style>
  .review {
    display: flex;
    flex-direction: column;
  }
  /* En móvil las fotos siguen a la vista al editar: comparar es el trabajo de este paso. */
  .photos {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: var(--capture-space-2);
    padding: var(--capture-space-2) var(--capture-space-4);
    border-bottom: 1px solid rgb(var(--border));
    background: rgb(var(--surface-elevated));
  }
  .thumbs {
    display: flex;
    flex: 1;
    gap: var(--capture-space-2);
    min-width: 0;
  }
  .thumb {
    position: relative;
    overflow: hidden;
    flex: 1;
    max-width: 128px;
    min-height: 44px;
    border: 1px solid rgb(var(--border));
    border-radius: var(--capture-radius);
    background: rgb(var(--surface-muted));
  }
  .thumb:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  .thumb img {
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 85.6 / 54;
    object-fit: cover;
  }
  .thumb span {
    position: absolute;
    bottom: 2px;
    left: 2px;
    padding: 0 4px;
    border-radius: var(--capture-radius-sm);
    color: #fff;
    background: rgb(0 0 0 / 72%);
    font-size: 11px;
  }
  .form {
    display: flex;
    flex-direction: column;
    gap: var(--capture-space-4);
    padding: var(--capture-space-4);
  }
  .status {
    margin: 0;
    padding: var(--capture-space-2) var(--capture-space-3);
    border-radius: var(--capture-radius);
    color: rgb(var(--foreground-muted));
    background: rgb(var(--surface-muted));
    font-size: 14px;
  }
  .unread {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--capture-space-2);
    padding: var(--capture-space-3);
    border-left: 3px solid rgb(var(--warning));
    border-radius: var(--capture-radius);
    color: rgb(var(--foreground));
    background: rgb(var(--warning) / 10%);
    font-size: 14px;
  }
  .unread p {
    margin: 0;
  }
  .to-review {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--capture-space-1) var(--capture-space-2);
    font-size: 14px;
  }
  .to-review span {
    color: rgb(var(--foreground-muted));
  }
  .to-review button {
    min-height: 32px;
    padding: 0 var(--capture-space-2);
    border: 1px solid rgb(var(--border-strong));
    border-radius: var(--capture-radius);
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .to-review button:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  fieldset {
    min-width: 0;
    margin: 0;
    padding: 0;
    border: 0;
  }
  legend {
    margin-bottom: var(--capture-space-3);
    padding: 0;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 600;
  }
  .grid {
    display: grid;
    gap: var(--capture-space-3);
  }
  .field {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: var(--capture-space-1);
  }
  .field label {
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 500;
  }
  .field small {
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  /* 16 px evita que iOS acerque la página al enfocar el campo. */
  .field input,
  .field textarea {
    width: 100%;
    min-height: 44px;
    padding: var(--capture-space-2) var(--capture-space-3);
    border: 1px solid rgb(var(--control-border));
    border-radius: var(--capture-radius);
    color: rgb(var(--foreground));
    background: rgb(var(--surface));
    font-size: 16px;
  }
  .field input:focus-visible,
  .field textarea:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 1px;
  }
  .field input[aria-invalid='true'] {
    border-color: rgb(var(--danger));
  }
  .field input.reading {
    background: rgb(var(--surface-hover));
    animation: pulse 1.4s ease-in-out infinite;
  }
  /* El aviso en claro da 4.41:1 como texto: el color va en la barra y el texto queda legible. */
  .issue {
    margin: var(--capture-space-1) 0 0;
    padding-left: var(--capture-space-2);
    border-left: 2px solid rgb(var(--warning));
    color: rgb(var(--foreground));
    font-size: 13px;
  }
  .issue.error,
  .issue.mismatch {
    border-left-color: rgb(var(--danger));
    font-weight: 500;
  }
  .stop {
    margin: 0;
    padding: var(--capture-space-3);
    border-left: 3px solid rgb(var(--danger));
    border-radius: var(--capture-radius);
    color: rgb(var(--foreground));
    background: rgb(var(--danger) / 10%);
    font-size: 14px;
  }
  .check {
    display: flex;
    align-items: flex-start;
    gap: var(--capture-space-3);
    min-height: 44px;
    padding: var(--capture-space-3);
    border: 1px solid rgb(var(--border));
    border-radius: var(--capture-radius);
    color: rgb(var(--foreground));
    font-size: 14px;
    cursor: pointer;
  }
  .check input {
    flex: none;
    width: 20px;
    height: 20px;
  }
  .check:focus-within {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  .note {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 12px;
  }
  @media (min-width: 480px) {
    .grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  /* Con espacio de sobra, fotos grandes en columna fija junto al formulario. */
  @media (min-width: 768px) {
    .review {
      display: grid;
      grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
      align-items: start;
    }
    .photos {
      flex-direction: column;
      align-items: stretch;
      padding: var(--capture-space-5);
      border-right: 1px solid rgb(var(--border));
      border-bottom: 0;
    }
    .thumbs {
      flex-direction: column;
    }
    .thumb {
      max-width: none;
    }
    .thumb span {
      bottom: var(--capture-space-1);
      left: var(--capture-space-1);
      font-size: 12px;
    }
    .form {
      padding: var(--capture-space-5);
    }
    .field input,
    .field textarea {
      font-size: 14px;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .field input.reading {
      animation: none;
    }
  }
  @keyframes pulse {
    50% {
      opacity: 0.55;
    }
  }
</style>
