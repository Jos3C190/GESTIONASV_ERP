<script lang="ts">
  /** Badge — badge de estado con variante suave (fondo tenue + borde). */

  type Variant = 'success' | 'warning' | 'danger' | 'neutral' | 'primary';

  interface Props {
    variant?: Variant;
    children: import('svelte').Snippet;
  }

  let { variant = 'neutral', children }: Props = $props();

  let classes = $derived(`badge-${variant} inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium`);
</script>

<span class={classes}>
  {@render children()}
</span>