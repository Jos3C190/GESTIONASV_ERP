<script lang="ts">
  import type { VehicleKind } from './catalog';
  import { quadToMatrix3d, VEHICLE_DECALS, zoneSize, type DecalZone } from './branding';

  let {
    src,
    alt,
    kind,
    logo = null,
    zones,
    onerror
  }: {
    src: string;
    alt: string;
    kind: VehicleKind;
    logo?: string | null;
    zones?: DecalZone[];
    onerror?: () => void;
  } = $props();

  const spec = $derived(VEHICLE_DECALS[kind]);
  const decals = $derived(
    (zones ?? spec.zones).map((zone) => {
      const { width, height } = zoneSize(zone);
      return {
        id: zone.id,
        width,
        height,
        padding: (zone.inset ?? 0.02) * Math.min(width, height),
        transform: quadToMatrix3d(width, height, zone.quad)
      };
    })
  );

  let image = $state<HTMLImageElement>();
  let box = $state({ scale: 0, x: 0, y: 0 });
  let logoFailed = $state(false);

  $effect(() => {
    if (logo) logoFailed = false;
  });

  // Replica el área real que ocupa la imagen con object-fit: contain.
  function measure() {
    if (!image) return;
    const scale = Math.min(image.clientWidth / spec.width, image.clientHeight / spec.height);
    box = {
      scale,
      x: (image.clientWidth - spec.width * scale) / 2,
      y: (image.clientHeight - spec.height * scale) / 2
    };
  }

  $effect(() => {
    if (!image) return;
    void spec.width;
    measure();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(measure);
    observer.observe(image);
    return () => observer.disconnect();
  });
</script>

<div class="branded-vehicle">
  <img bind:this={image} {src} {alt} width="720" height="440" loading="lazy" {onerror} />
  {#if logo && !logoFailed && box.scale > 0}
    <div
      class="decal-layer"
      aria-hidden="true"
      style:left="{box.x}px"
      style:top="{box.y}px"
      style:width="{spec.width}px"
      style:height="{spec.height}px"
      style:transform="scale({box.scale})"
    >
      {#each decals as decal (decal.id)}
        <div
          class="decal"
          data-zone={decal.id}
          style:width="{decal.width}px"
          style:height="{decal.height}px"
          style:padding="{decal.padding}px"
          style:transform={decal.transform}
        >
          <img src={logo} alt="" onerror={() => (logoFailed = true)} />
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .branded-vehicle {
    position: relative;
    width: 100%;
    height: 100%;
  }
  .branded-vehicle > img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
  .decal-layer {
    position: absolute;
    transform-origin: 0 0;
    pointer-events: none;
    /* Deja ver sombras y brillos de la carrocería a través del logo. */
    mix-blend-mode: multiply;
  }
  .decal {
    position: absolute;
    top: 0;
    left: 0;
    box-sizing: border-box;
    transform-origin: 0 0;
  }
  .decal img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    /* Compensa el aire que suelen traer los archivos de logo. */
    transform: scale(1.2);
  }
</style>
