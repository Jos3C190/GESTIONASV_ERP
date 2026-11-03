<script lang="ts">
  import BrandedVehicle from '$lib/features/fleet/BrandedVehicle.svelte';
  import { VEHICLE_DECALS, type DecalZone, type Point } from '$lib/features/fleet/branding';
  import { BASE_IMAGE_KEYS, BASE_IMAGES, type BaseImage } from '$lib/features/fleet/catalog';
  import { company } from '$lib/stores/company.svelte';

  const kinds = BASE_IMAGE_KEYS;
  let kind = $state<BaseImage>('refrigerated');
  let logo = $state(company.active?.logo ?? '');
  let zones = $state<DecalZone[]>(structuredClone(VEHICLE_DECALS.refrigerated.zones));
  let svg = $state<SVGSVGElement>();
  let dragging = $state<{ zone: number; corner: number } | null>(null);
  let copied = $state(false);

  const spec = $derived(VEHICLE_DECALS[kind]);
  const json = $derived(JSON.stringify(zones.map(({ id, quad }) => ({ id, quad }))));

  function selectKind(next: BaseImage) {
    kind = next;
    zones = structuredClone(VEHICLE_DECALS[next].zones);
  }

  function toImagePoint(event: PointerEvent): Point {
    const matrix = svg!.getScreenCTM()!.inverse();
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix);
    return [Math.round(point.x), Math.round(point.y)];
  }

  function move(event: PointerEvent) {
    if (!dragging) return;
    const zone = zones[dragging.zone];
    if (zone) zone.quad[dragging.corner as 0 | 1 | 2 | 3] = toImagePoint(event);
  }

  async function copy() {
    await navigator.clipboard.writeText(json);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }
</script>

<svelte:head><title>Calibrar branding — GestionaSV</title></svelte:head>

<section class="calibrate">
  <header>
    <h1>Calibrar zonas de logo</h1>
    <p>
      Arrastra las esquinas (TL, TR, BR, BL) de cada zona y copia el resultado a <code
        >branding.ts</code
      >.
    </p>
  </header>

  <div class="controls">
    <select value={kind} onchange={(event) => selectKind(event.currentTarget.value as BaseImage)}>
      {#each kinds as option (option)}<option value={option}>{BASE_IMAGES[option].label}</option
        >{/each}
    </select>
    <input bind:value={logo} placeholder="URL del logo" />
    <button type="button" onclick={() => selectKind(kind)}>Restablecer</button>
    <button type="button" onclick={copy}>{copied ? 'Copiado' : 'Copiar JSON'}</button>
  </div>

  <div class="stage">
    <BrandedVehicle src={BASE_IMAGES[kind].image} alt={kind} {kind} logo={logo || null} {zones} />
    <svg
      bind:this={svg}
      viewBox="0 0 {spec.width} {spec.height}"
      preserveAspectRatio="xMidYMid meet"
      role="application"
      onpointermove={move}
      onpointerup={() => (dragging = null)}
      onpointerleave={() => (dragging = null)}
    >
      {#each zones as zone, zoneIndex (zone.id)}
        <polygon points={zone.quad.map((point) => point.join(',')).join(' ')} />
        {#each zone.quad as [x, y], corner (corner)}
          <circle
            cx={x}
            cy={y}
            r={spec.width / 120}
            role="presentation"
            onpointerdown={(event) => {
              svg?.setPointerCapture(event.pointerId);
              dragging = { zone: zoneIndex, corner };
            }}
          />
        {/each}
      {/each}
    </svg>
  </div>

  <pre>{json}</pre>
</section>

<style>
  .calibrate {
    display: grid;
    gap: 16px;
    padding: 24px;
  }
  h1 {
    font-size: 20px;
    font-weight: 600;
  }
  p {
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .controls > * {
    height: 34px;
    padding: 0 10px;
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: transparent;
    font-size: 13px;
  }
  .controls input {
    flex: 1;
    min-width: 220px;
  }
  .stage {
    position: relative;
    height: min(70vh, 640px);
    background: #f4f4f5;
    border-radius: 12px;
  }
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    touch-action: none;
  }
  polygon {
    fill: rgb(14 165 233 / 0.08);
    stroke: rgb(14 165 233);
    stroke-width: 2;
    vector-effect: non-scaling-stroke;
  }
  circle {
    fill: white;
    stroke: rgb(14 165 233);
    stroke-width: 2;
    vector-effect: non-scaling-stroke;
    cursor: grab;
  }
  pre {
    overflow-x: auto;
    padding: 12px;
    border-radius: 8px;
    background: rgb(var(--surface-muted, 24 24 27));
    font-size: 12px;
  }
</style>
