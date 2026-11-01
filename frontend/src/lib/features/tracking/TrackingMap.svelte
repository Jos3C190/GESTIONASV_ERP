<script lang="ts">
  import type { ComponentProps } from 'svelte';
  import TrackingMapCanvas from './TrackingMapCanvas.svelte';

  let {
    vehicles,
    selectedKey,
    follow,
    trail,
    plannedRoute,
    originalRoute,
    geofences,
    sites,
    highlightedGeofence,
    draft,
    drawing,
    focusPoint,
    endpoints,
    simRoutes,
    simPoints,
    pilots,
    logo,
    compact,
    oninteract,
    onselect,
    ondrawpoint,
    ondrawfinish
  }: ComponentProps<typeof TrackingMapCanvas> = $props();
  let attempt = $state(0);
  let canvas = $state<{ fitRing: (ring: [number, number][]) => void }>();

  export function fitRing(ring: [number, number][]) {
    canvas?.fitRing(ring);
  }
</script>

<!-- Retrying replaces only this map and releases its WebGL resources. -->
{#key attempt}
  <TrackingMapCanvas
    bind:this={canvas}
    {vehicles}
    {selectedKey}
    {follow}
    {trail}
    {plannedRoute}
    {originalRoute}
    {geofences}
    {sites}
    {highlightedGeofence}
    {draft}
    {drawing}
    {focusPoint}
    {endpoints}
    {simRoutes}
    {simPoints}
    {pilots}
    {logo}
    {compact}
    {oninteract}
    {onselect}
    {ondrawpoint}
    {ondrawfinish}
    onretry={() => attempt++}
  />
{/key}
