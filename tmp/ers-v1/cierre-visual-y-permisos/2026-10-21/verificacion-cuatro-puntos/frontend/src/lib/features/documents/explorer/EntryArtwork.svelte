<script lang="ts">
  import {
    documentFileLabel,
    documentFileTone,
    normalizeDocumentExtension
  } from './file-types';

  interface Props {
    kind: 'folder' | 'file';
    extension?: string;
  }

  let { kind, extension = '' }: Props = $props();

  const normalizedExtension = $derived(normalizeDocumentExtension(extension));
  const tone = $derived(documentFileTone(extension));
  const label = $derived(documentFileLabel(extension));
</script>

<span class="entry-artwork" data-kind={kind} data-extension={normalizedExtension} data-tone={tone} aria-hidden="true">
  {#if kind === 'folder'}
    <svg class="folder-artwork" viewBox="0 0 88 72" fill="none">
      <path class="folder-back" d="M8 19a6 6 0 0 1 6-6h22l8 8h30a6 6 0 0 1 6 6v31a7 7 0 0 1-7 7H15a7 7 0 0 1-7-7V19Z" />
      <path class="folder-lip" d="M8 29h72v29a7 7 0 0 1-7 7H15a7 7 0 0 1-7-7V29Z" />
      <path class="folder-highlight" d="M15 34h58" />
    </svg>
  {:else}
    <svg class="document-artwork" viewBox="0 0 72 82" fill="none">
      <path class="document-sheet" d="M13 4h30l16 16v53a5 5 0 0 1-5 5H13a5 5 0 0 1-5-5V9a5 5 0 0 1 5-5Z" />
      <path class="document-fold" d="M43 4v12a4 4 0 0 0 4 4h12" />
      <path class="document-shine" d="M15 10v56" />
    </svg>
    <span class="document-label">{label}</span>
  {/if}
</span>

<style>
  .entry-artwork {
    --artwork-color: rgb(var(--document-file-generic));
    --artwork-dark: rgb(var(--document-file-generic-dark));
    position: relative;
    display: inline-flex;
    height: 82px;
    width: 88px;
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    filter: drop-shadow(0 9px 10px rgb(0 0 0 / 0.18));
  }
  .folder-artwork { width: 88px; height: 72px; overflow: visible; }
  .folder-back { fill: rgb(var(--document-folder-back)); }
  .folder-lip { fill: rgb(var(--document-folder-front)); }
  .folder-highlight { stroke: rgb(var(--document-folder-highlight)); stroke-width: 2; stroke-linecap: round; opacity: 0.65; }
  .document-artwork { width: 72px; height: 82px; overflow: visible; }
  .document-sheet { fill: var(--artwork-color); }
  .document-fold { fill: var(--artwork-dark); }
  .document-shine { stroke: rgb(255 255 255 / 0.2); stroke-width: 2; stroke-linecap: round; }
  .document-label {
    position: absolute;
    left: 50%;
    top: 49px;
    transform: translate(-50%, -50%);
    color: white;
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.025em;
    line-height: 1;
    text-shadow: 0 1px 1px rgb(0 0 0 / 0.2);
  }
  [data-tone='pdf'] { --artwork-color: rgb(var(--document-file-pdf)); --artwork-dark: rgb(var(--document-file-pdf-dark)); }
  [data-tone='doc'] { --artwork-color: rgb(var(--document-file-doc)); --artwork-dark: rgb(var(--document-file-doc-dark)); }
  [data-tone='sheet'] { --artwork-color: rgb(var(--document-file-sheet)); --artwork-dark: rgb(var(--document-file-sheet-dark)); }
  [data-tone='slides'] { --artwork-color: rgb(var(--document-file-slides)); --artwork-dark: rgb(var(--document-file-slides-dark)); }
  [data-tone='archive'] { --artwork-color: rgb(var(--document-file-archive)); --artwork-dark: rgb(var(--document-file-archive-dark)); }
  [data-tone='text'] { --artwork-color: rgb(var(--document-file-text)); --artwork-dark: rgb(var(--document-file-text-dark)); }
  [data-tone='image'] { --artwork-color: rgb(var(--document-file-image)); --artwork-dark: rgb(var(--document-file-image-dark)); }  @media (max-width: 430px) {
    .entry-artwork { height: 70px; width: 76px; }
    .folder-artwork { height: 62px; width: 76px; }
    .document-artwork { height: 70px; width: 62px; }
    .document-label { top: 42px; font-size: 0.62rem; }
  }
</style>
