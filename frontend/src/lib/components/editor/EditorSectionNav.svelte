<script lang="ts">
  interface Props {
    sections: readonly (readonly [string, string])[];
    activeSection: string;
    onselect: (id: string) => void;
  }

  let { sections, activeSection, onselect }: Props = $props();
</script>

<nav aria-label="Secciones del formulario" class="hidden lg:block">
  <div class="sticky top-28 space-y-1 rounded-xl border border-border bg-surface-elevated p-2">
    {#each sections as section}
      <button
        type="button"
        aria-current={activeSection === section[0] ? 'step' : undefined}
        onclick={() => onselect(section[0])}
        class="block w-full rounded-lg px-3 py-2 text-left text-sm transition-colors {activeSection ===
        section[0]
          ? 'bg-surface-hover text-foreground'
          : 'text-foreground-muted hover:bg-surface-hover hover:text-foreground'}"
        >{section[1]}</button
      >
    {/each}
  </div>
</nav>
