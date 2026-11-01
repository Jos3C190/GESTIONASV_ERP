<script lang="ts">
  let {
    name,
    initials,
    src,
    large = false
  }: { name: string; initials: string; src: string | null; large?: boolean } = $props();
  let failed = $state(false);
  $effect(() => {
    void src;
    failed = false;
  });
</script>

<span class="avatar" class:large aria-hidden="true">
  {#if src && !failed}<img
      {src}
      alt=""
      width={large ? 64 : 34}
      height={large ? 64 : 34}
      onerror={() => (failed = true)}
    />{:else}{initials || name.slice(0, 2).toUpperCase()}{/if}
</span>

<style>
  .avatar {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 34px;
    height: 34px;
    border: 1px solid rgb(var(--border));
    border-radius: 50%;
    background: rgb(var(--surface-hover));
    color: rgb(var(--foreground));
    font-size: 11px;
    font-weight: 650;
    overflow: hidden;
  }
  .avatar.large {
    width: 64px;
    height: 64px;
    font-size: 21px;
  }
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
</style>
