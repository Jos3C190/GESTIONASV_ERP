<script lang="ts">
  import type { Snippet } from 'svelte';

  type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'warning' | 'success';
  type Size = 'sm' | 'md' | 'lg';

  interface Props {
    variant?: Variant;
    size?: Size;
    disabled?: boolean;
    type?: 'button' | 'submit' | 'reset';
    onclick?: (e: MouseEvent) => void;
    children: Snippet;
    class?: string;
  }

  let {
    variant = 'primary',
    size = 'md',
    disabled = false,
    type = 'button',
    onclick,
    children,
    class: className = ''
  }: Props = $props();

  const base =
    'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none focus-visible:shadow-glow';

  const variants: Record<Variant, string> = {
    primary: 'bg-foreground text-surface hover:bg-foreground-muted',
    secondary:
      'bg-surface-elevated text-foreground border border-border hover:bg-surface-hover hover:border-border-strong shadow-soft',
    ghost: 'bg-transparent text-foreground-muted hover:bg-surface-hover hover:text-foreground',
    danger: 'bg-danger text-danger-foreground hover:opacity-90 shadow-soft',
    warning: 'bg-warning text-warning-foreground hover:opacity-90 shadow-soft',
    success: 'bg-success text-success-foreground hover:opacity-90 shadow-soft'
  };

  const sizes: Record<Size, string> = {
    sm: 'h-8 px-3 text-xs gap-1.5',
    md: 'h-9 px-3.5 text-sm gap-2',
    lg: 'h-11 px-5 text-sm gap-2'
  };

  const classes = $derived(`${base} ${variants[variant]} ${sizes[size]} ${className}`);
</script>

<button {type} {disabled} {onclick} class={classes}>
  {@render children()}
</button>
