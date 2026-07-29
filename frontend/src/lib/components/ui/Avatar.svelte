<script lang="ts">
  /**
   * Avatar — Avatar circular con imagen opcional y fallback de iniciales con gradientes estéticos (Geist).
   * Centrado óptico de texto y proporciones ajustadas.
   */

  interface Props {
    initials?: string;
    size?: number;
    src?: string | null;
    alt?: string;
    class?: string;
  }

  let { initials = '', size = 28, src = null, alt, class: className = '' }: Props = $props();

  let imgError = $state(false);

  const PALETTES = [
    { bg: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', text: '#ffffff' }, // Indigo
    { bg: 'linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%)', text: '#ffffff' }, // Sky
    { bg: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', text: '#ffffff' }, // Emerald
    { bg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)', text: '#ffffff' }, // Amber
    { bg: 'linear-gradient(135deg, #ec4899 0%, #db2777 100%)', text: '#ffffff' }, // Pink
    { bg: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)', text: '#ffffff' }, // Purple
    { bg: 'linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)', text: '#ffffff' }, // Teal
    { bg: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', text: '#ffffff' }, // Blue
  ];

  let displayInitials = $derived((initials || '?').trim().substring(0, 2).toUpperCase());

  let palette = $derived.by(() => {
    let hash = 0;
    const str = displayInitials;
    for (let i = 0; i < str.length; i++) {
      hash = (hash * 31 + str.charCodeAt(i)) & 0xffffffff;
    }
    return PALETTES[Math.abs(hash) % PALETTES.length]!;
  });

  let fontSize = $derived(Math.max(9, Math.round(size * 0.36)));

  let showImage = $derived(!!src && !imgError);

  $effect(() => {
    imgError = false;
  });
</script>

<div
  class="relative flex flex-none items-center justify-center overflow-hidden rounded-full font-semibold tracking-tighter select-none shadow-xs ring-1 ring-black/10 dark:ring-white/20 {className}"
  style="width: {size}px; height: {size}px; {showImage ? 'background: var(--surface-muted);' : `background: ${palette.bg}; color: ${palette.text};`} font-size: {fontSize}px; line-height: 1;"
  aria-label={alt ?? displayInitials}
>
  {#if showImage}
    <img
      src={src!}
      {alt}
      class="h-full w-full object-cover"
      loading="lazy"
      onerror={() => (imgError = true)}
    />
  {:else}
    <span class="inline-flex items-center justify-center leading-none">{displayInitials}</span>
  {/if}
</div>