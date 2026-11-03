<script lang="ts">
  import FleetIcon from '../FleetIcon.svelte';
  import CopyField from './CopyField.svelte';
  import QrCode from './QrCode.svelte';
  import { ANDROID_APP, detectPlatform, IOS_APP, type SetupStep } from './setup-flow';

  let {
    step,
    configUri,
    serverUrl,
    identifier,
    permissions = $bindable()
  }: {
    step: SetupStep;
    configUri: string | null;
    serverUrl: string | null;
    identifier: string | null;
    permissions: boolean[];
  } = $props();

  const platform = detectPlatform(navigator.userAgent);
  // Un teléfono no puede escanear su propia pantalla: ahí lo primero es copiar.
  const onPhone = window.matchMedia?.('(pointer: coarse)').matches ?? false;

  const stores = [
    { key: 'android', label: 'Android', store: 'Google Play', href: ANDROID_APP },
    { key: 'ios', label: 'iPhone', store: 'App Store', href: IOS_APP }
  ].sort((a, b) => Number(b.key === platform) - Number(a.key === platform));

  const CHECKS = [
    {
      title: 'Permite la ubicación siempre',
      detail:
        'Elige “Permitir todo el tiempo” en Android o “Siempre” en iPhone. Así sigue enviándola con la pantalla apagada.'
    },
    {
      title: 'Quita el ahorro de batería',
      detail: 'En Android, deja la batería de la app “Sin restricciones”. En iPhone no hace falta.'
    },
    {
      title: 'Activa el seguimiento',
      detail: 'Enciende el interruptor en la pantalla principal de Traccar Client.'
    }
  ];
</script>

{#snippet manual()}
  <div class="fields">
    {#if serverUrl}
      <CopyField label="Servidor" value={serverUrl} hint="En la app: Server URL" />
    {/if}
    {#if identifier}
      <CopyField label="Identificador" value={identifier} hint="En la app: Device identifier" />
    {/if}
  </div>
{/snippet}

{#if step === 'install'}
  {#if onPhone}
    <div class="stores">
      {#each stores as item, index (item.key)}
        <a
          class="store"
          class:recommended={index === 0 && platform !== 'other'}
          href={item.href}
          target="_blank"
          rel="noreferrer"
        >
          <FleetIcon name="phone" size={20} />
          <span class="store-text">
            <strong>{item.label}</strong>
            <span>Abrir en {item.store}</span>
          </span>
          <FleetIcon name="external" size={16} />
        </a>
      {/each}
    </div>
  {:else}
    <!-- Desde un PC, abrir la tienda aquí no sirve: el código lleva la tienda al teléfono. -->
    <div class="store-codes">
      {#each stores as item (item.key)}
        <div class="store-code">
          <QrCode value={item.href} alt={`Código QR de ${item.store}`} size={150} />
          <strong>{item.label}</strong>
          <span>{item.store}</span>
        </div>
      {/each}
    </div>
    <p class="note">Escanea el código con la cámara del teléfono.</p>
  {/if}
  <p class="note">La app se llama <strong>Traccar Client</strong> y es gratuita.</p>
{:else if step === 'scan'}
  {#if onPhone}
    <ol class="how">
      <li>Abre Traccar Client y entra a sus ajustes.</li>
      <li>Copia estos dos datos en los campos que se indican.</li>
    </ol>
    {@render manual()}
    <details>
      <summary>Mostrar código QR para escanearlo con otro teléfono</summary>
      <div class="details-body">
        {#if configUri}<QrCode value={configUri} alt="Código QR para configurar la app" />{/if}
      </div>
    </details>
  {:else}
    {#if configUri}<QrCode value={configUri} alt="Código QR para configurar la app" />{/if}
    <ol class="how">
      <li>Abre Traccar Client en el teléfono y entra a sus ajustes.</li>
      <li>Toca el ícono de código QR, arriba a la derecha.</li>
      <li>Apunta la cámara a este código.</li>
    </ol>
    <details>
      <summary>¿No puedes escanear? Escribe los datos</summary>
      <div class="details-body">{@render manual()}</div>
    </details>
  {/if}
{:else if step === 'permissions'}
  <ul class="checks">
    {#each CHECKS as check, index (check.title)}
      <li>
        <label class:done={permissions[index]}>
          <input type="checkbox" bind:checked={permissions[index]} />
          <span>
            <strong>{check.title}</strong>
            <small>{check.detail}</small>
          </span>
        </label>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .stores,
  .fields,
  .checks {
    display: grid;
    gap: 10px;
  }
  .store {
    display: flex;
    min-height: 64px;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    color: rgb(var(--foreground));
    background: rgb(var(--surface-elevated));
    text-decoration: none;
  }
  .store:hover {
    background: rgb(var(--surface-hover));
  }
  .store:focus-visible,
  summary:focus-visible {
    outline: 2px solid rgb(var(--foreground));
    outline-offset: 2px;
  }
  .store.recommended {
    border-color: rgb(var(--foreground));
  }
  .store-text {
    display: flex;
    min-width: 0;
    flex: 1;
    flex-direction: column;
  }
  .store-text strong {
    font-size: 15px;
    font-weight: 600;
  }
  .store-text span {
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .store-codes {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
  .store-code {
    display: grid;
    justify-items: center;
    gap: 2px;
    color: rgb(var(--foreground));
    font-size: 15px;
    text-align: center;
  }
  .store-code strong {
    margin-top: 8px;
    font-weight: 600;
  }
  .store-code span {
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
  .note {
    margin: 0;
    color: rgb(var(--foreground-muted));
    font-size: 14px;
  }
  .note strong {
    color: rgb(var(--foreground));
    font-weight: 600;
  }
  .how {
    display: grid;
    gap: 6px;
    margin: 0;
    padding-left: 22px;
    color: rgb(var(--foreground));
    font-size: 15px;
    list-style: decimal;
  }
  details {
    border-top: 1px solid rgb(var(--border));
    padding-top: 4px;
  }
  summary {
    display: flex;
    min-height: 44px;
    align-items: center;
    gap: 8px;
    border-radius: 8px;
    color: rgb(var(--foreground));
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    list-style: none;
  }
  summary::-webkit-details-marker {
    display: none;
  }
  summary::before {
    content: '';
    width: 7px;
    height: 7px;
    flex: none;
    border-right: 2px solid currentColor;
    border-bottom: 2px solid currentColor;
    transform: rotate(-45deg);
    transition: transform 0.15s;
  }
  details[open] summary::before {
    transform: rotate(45deg);
  }
  @media (prefers-reduced-motion: reduce) {
    summary::before {
      transition: none;
    }
  }
  .details-body {
    display: grid;
    gap: 10px;
    padding-top: 8px;
  }
  .checks {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .checks label {
    display: flex;
    min-height: 64px;
    align-items: flex-start;
    gap: 12px;
    padding: 14px;
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    background: rgb(var(--surface-elevated));
    cursor: pointer;
  }
  .checks label.done {
    border-color: rgb(var(--success) / 50%);
  }
  .checks input {
    width: 20px;
    height: 20px;
    flex: none;
    margin-top: 1px;
    accent-color: rgb(var(--success));
  }
  .checks strong {
    display: block;
    color: rgb(var(--foreground));
    font-size: 15px;
    font-weight: 600;
  }
  .checks small {
    display: block;
    margin-top: 2px;
    color: rgb(var(--foreground-muted));
    font-size: 13px;
  }
</style>
