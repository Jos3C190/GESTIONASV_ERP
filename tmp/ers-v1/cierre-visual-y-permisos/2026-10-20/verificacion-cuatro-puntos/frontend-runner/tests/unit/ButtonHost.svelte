<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';

  let {
    label = 'Click',
    variant = 'primary',
    disabled = false
  }: { label?: string; variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; disabled?: boolean } = $props();
</script>

<Button {variant} {disabled}>{label}</Button>