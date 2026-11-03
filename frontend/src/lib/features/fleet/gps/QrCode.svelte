<script lang="ts">
  import QRCode from 'qrcode';

  let { value, alt, size = 280 }: { value: string; alt: string; size?: number } = $props();

  let source = $state<string | null>(null);
  let failed = $state(false);

  $effect(() => {
    const text = value;
    let stale = false;
    failed = false;
    QRCode.toDataURL(text, { width: 512, margin: 4, errorCorrectionLevel: 'M' })
      .then((url) => {
        if (!stale) source = url;
      })
      .catch(() => {
        if (!stale) failed = true;
      });
    return () => {
      stale = true;
    };
  });
</script>

<!-- Fondo blanco también en modo oscuro: los lectores necesitan ese contraste. -->
<div class="qr" style:--qr-size={`${size}px`}>
  {#if source}
    <img src={source} {alt} width="512" height="512" />
  {:else if failed}
    <p role="alert">No se pudo generar el código. Usa los datos para copiar.</p>
  {/if}
</div>

<style>
  .qr {
    display: flex;
    width: min(72vw, var(--qr-size));
    aspect-ratio: 1;
    margin-inline: auto;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    border-radius: 16px;
    background: #fff;
    box-shadow: 0 0 0 1px rgb(var(--border));
  }
  img {
    width: 100%;
    height: 100%;
  }
  p {
    margin: 0;
    padding: 16px;
    color: #1a1a1a;
    font-size: 14px;
    text-align: center;
  }
</style>
