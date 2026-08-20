<script lang="ts">
  import Badge from '$lib/components/ui/Badge.svelte';
  import KebabMenu, { type KebabItem } from '$lib/components/ui/KebabMenu.svelte';
  import { CAPACITY_PROFILE_LABEL, CAPACITY_STATUS_LABEL } from '$lib/features/warehouses/types';
  import type { LocationOut } from '../types';
  import { locationStatusLabel, locationTypeLabel } from '../types';
  import LocationRoute from './LocationRoute.svelte';

  interface Props {
    items: LocationOut[];
    actionsFor: (location: LocationOut) => KebabItem[];
    capacityGroupLabels?: Record<string, string>;
  }

  let { items, actionsFor, capacityGroupLabels = {} }: Props = $props();

  function statusVariant(location: LocationOut): 'success' | 'warning' | 'danger' | 'neutral' {
    if (!location.is_active || location.lifecycle_status === 'retired') return 'neutral';
    if (['blocked', 'blocked_in', 'blocked_out'].includes(location.lifecycle_status))
      return 'danger';
    if (['draft', 'maintenance'].includes(location.lifecycle_status)) return 'warning';
    return location.lifecycle_status === 'active' ? 'success' : 'neutral';
  }

  function physicalStatusVariant(
    location: LocationOut
  ): 'success' | 'warning' | 'danger' | 'neutral' {
    if (location.capacity_status === 'incomplete') return 'warning';
    if (
      ['critical', 'full', 'over_operational', 'over_certified'].includes(location.capacity_status)
    )
      return 'danger';
    return location.capacity_status === 'available' ? 'success' : 'neutral';
  }

  function metric(value: number | null, unit: 'kg' | 'm³'): string {
    return value == null ? '—' : `${value.toLocaleString('es-SV')} ${unit}`;
  }
</script>

<div class="hidden overflow-x-auto md:block">
  <table class="w-full min-w-[940px] text-sm">
    <thead class="border-b border-border bg-surface-muted/70">
      <tr>
        <th class="px-4 py-3 text-left font-semibold text-foreground">Código y ruta</th>
        <th class="px-4 py-3 text-left font-semibold text-foreground">Estructura</th>
        <th class="px-4 py-3 text-left font-semibold text-foreground">Tipo</th>
        <th class="px-4 py-3 text-right font-semibold text-foreground">Límites físicos</th>
        <th class="px-4 py-3 text-left font-semibold text-foreground">Estado</th>
        <th class="w-12 px-2 py-3"><span class="sr-only">Acciones</span></th>
      </tr>
    </thead>
    <tbody class="divide-y divide-border">
      {#each items as location (location.id)}
        {@const actions = actionsFor(location)}
        <tr class="transition-colors hover:bg-surface-muted/60">
          <td class="px-4 py-3">
            <div class="font-mono text-sm font-semibold text-foreground">{location.code}</div>
            <div class="mt-1"><LocationRoute {...location} compact /></div>
          </td>
          <td class="px-4 py-3 text-xs text-foreground-muted">
            {location.capacity_group_id
              ? (capacityGroupLabels[location.capacity_group_id] ?? 'Estructura no disponible')
              : 'Directa del almacén'}
          </td>
          <td class="px-4 py-3 text-foreground-muted"
            >{locationTypeLabel(location.location_type)}
            <div class="mt-1 text-xs text-foreground-subtle">
              {CAPACITY_PROFILE_LABEL[location.capacity_profile]}
            </div></td
          >
          <td class="px-4 py-3 text-right font-mono text-foreground text-xs">
            <div>Peso: {metric(location.operational_max_weight_kg, 'kg')}</div>
            <div class="text-foreground-muted">
              certificado {metric(location.certified_max_weight_kg, 'kg')}
            </div>
            <div class="mt-1">Volumen: {metric(location.operational_usable_volume_m3, 'm³')}</div>
            <div class="text-foreground-muted">
              certificado {metric(location.certified_usable_volume_m3, 'm³')}
            </div>
          </td>
          <td class="px-4 py-3">
            <div class="flex flex-col items-start gap-1.5">
              <Badge variant={statusVariant(location)}>
                {location.is_active ? locationStatusLabel(location.lifecycle_status) : 'Inactiva'}
              </Badge>
              <Badge variant={physicalStatusVariant(location)}>
                {CAPACITY_STATUS_LABEL[location.capacity_status]}
              </Badge>
            </div>
          </td>
          <td class="px-2 py-3 text-center">
            {#if actions.length > 0}
              <KebabMenu items={actions} ariaLabel={`Acciones para ${location.code}`} />
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<div class="divide-y divide-border md:hidden">
  {#each items as location (location.id)}
    {@const actions = actionsFor(location)}
    <article class="p-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="truncate font-mono text-sm font-semibold text-foreground">{location.code}</p>
          <p class="mt-1 text-xs text-foreground-muted">
            {locationTypeLabel(location.location_type)} · {CAPACITY_PROFILE_LABEL[
              location.capacity_profile
            ]}
          </p>
        </div>
        <div class="flex flex-none items-center gap-2">
          <Badge variant={statusVariant(location)}>
            {location.is_active ? locationStatusLabel(location.lifecycle_status) : 'Inactiva'}
          </Badge>
          <Badge variant={physicalStatusVariant(location)}>
            {CAPACITY_STATUS_LABEL[location.capacity_status]}
          </Badge>
          {#if actions.length > 0}
            <KebabMenu items={actions} ariaLabel={`Acciones para ${location.code}`} />
          {/if}
        </div>
      </div>
      <div class="mt-3 rounded-lg border border-border bg-surface-muted/40 p-3">
        <LocationRoute {...location} compact />
      </div>
      <div class="mt-3 text-xs text-foreground-muted">
        <span class="block">Estructura</span>
        <span class="font-medium text-foreground">
          {location.capacity_group_id
            ? (capacityGroupLabels[location.capacity_group_id] ?? 'Estructura no disponible')
            : 'Directa del almacén'}
        </span>
      </div>
      <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
        <div>
          <span class="block text-foreground-muted">Peso operativo / certificado</span>
          <span class="font-mono font-medium text-foreground">
            {metric(location.operational_max_weight_kg, 'kg')} / {metric(
              location.certified_max_weight_kg,
              'kg'
            )}
          </span>
        </div>
        <div>
          <span class="block text-foreground-muted">Volumen operativo / certificado</span>
          <span class="font-mono font-medium text-foreground">
            {metric(location.operational_usable_volume_m3, 'm³')} / {metric(
              location.certified_usable_volume_m3,
              'm³'
            )}
          </span>
        </div>
      </div>
    </article>
  {/each}
</div>
