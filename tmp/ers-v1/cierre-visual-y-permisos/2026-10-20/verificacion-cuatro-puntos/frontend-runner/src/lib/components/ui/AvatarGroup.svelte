<script lang="ts">
  /** AvatarGroup — grupo de avatares superpuestos con burbuja "+N". */

  import Avatar from './Avatar.svelte';

  interface Props {
    members: { name: string; initials: string }[];
    max?: number;
    size?: number;
  }

  let { members, max = 4, size = 28 }: Props = $props();

  let visible = $derived(members.slice(0, max));
  let overflow = $derived(members.length - max);
</script>

<div class="flex items-center">
  {#each visible as m, i (m.name)}
    <div style="margin-left: {i === 0 ? 0 : -8}px; z-index: {visible.length - i};">
      <Avatar initials={m.initials} {size} />
    </div>
  {/each}
  {#if overflow > 0}
    <div
      class="flex items-center justify-center rounded-full bg-surface-muted font-medium text-foreground-muted ring-2 ring-surface-elevated"
      style="width: {size}px; height: {size}px; margin-left: -8px; font-size: {size * 0.36}px;"
    >
      +{overflow}
    </div>
  {/if}
</div>