<script lang="ts">
  const paths = {
    truck:
      'M3 5h11v12H3z M14 9h4l3 4v4h-7 M7 19a2 2 0 100-4 2 2 0 000 4 M17 19a2 2 0 100-4 2 2 0 000 4',
    route:
      'M5 5a2 2 0 100 4 2 2 0 000-4 M19 15a2 2 0 100 4 2 2 0 000-4 M7 7h8a4 4 0 010 8H9a2 2 0 000 4h8',
    check: 'M20 6L9 17l-5-5',
    wrench: 'M14 6a4 4 0 004 4l3-3a6 6 0 01-8 7L6 21a2 2 0 01-3-3l7-7a6 6 0 017-8z',
    search: 'M21 21l-5-5 M18 10a8 8 0 11-16 0 8 8 0 0116 0',
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    list: 'M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01',
    plus: 'M12 5v14 M5 12h14',
    chevron: 'M9 5l7 7-7 7',
    close: 'M6 6l12 12 M18 6L6 18',
    camera: 'M4 8h3l2-3h6l2 3h3v12H4z M15.5 13.5a3.5 3.5 0 11-7 0 3.5 3.5 0 017 0',
    arrow: 'M4 12h16 M14 6l6 6-6 6',
    pin: 'M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1116 0 M15 10a3 3 0 11-6 0 3 3 0 016 0',
    fuel: 'M4 21V4h9v17 M3 21h11 M5 6h6v5H5 M16 5l3 3v9a2 2 0 01-4 0v-4h-2',
    clock: 'M12 8v4l3 2 M21 12a9 9 0 11-18 0 9 9 0 0118 0',
    file: 'M14 2H5v20h14V7z M14 2v5h5 M8 12h8 M8 16h6',
    info: 'M12 11v5 M12 7h.01 M21 12a9 9 0 11-18 0 9 9 0 0118 0',
    calendar: 'M4 5h16v16H4z M16 3v4 M8 3v4 M4 10h16',
    refresh: 'M20 7v5h-5 M4 17v-5h5 M6 6a8 8 0 0113 2 M18 18a8 8 0 01-13-2',
    shield: 'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M8 12l3 3 5-6',
    alert: 'M12 3l10 18H2z M12 10v4 M12 17h.01',
    image: 'M3 5h18v14H3z M3 16l5-5 4 4 3-3 6 6 M15 9h.01',
    chevronLeft: 'M15 5l-7 7 7 7',
    zoomIn: 'M21 21l-5-5 M18 10a8 8 0 11-16 0 8 8 0 0116 0 M10 7v6 M7 10h6',
    zoomOut: 'M21 21l-5-5 M18 10a8 8 0 11-16 0 8 8 0 0116 0 M7 10h6',
    fit: 'M4 9V4h5 M20 9V4h-5 M4 15v5h5 M20 15v5h-5',
    upload: 'M12 16V4 M7 9l5-5 5 5 M4 20h16',
    trash: 'M4 7h16 M9 7V4h6v3 M6 7l1 14h10l1-14',
    navigation: 'M12 3l7 18-7-4-7 4z',
    battery: 'M3 7h15v10H3z M21 11v2',
    power: 'M12 3v9 M6.5 7a8 8 0 1011 0',
    crosshair: 'M12 2v4 M12 18v4 M2 12h4 M18 12h4 M19 12a7 7 0 11-14 0 7 7 0 0114 0'
  };
  let {
    name,
    size = 18,
    class: className = ''
  }: { name: keyof typeof paths; size?: number; class?: string } = $props();
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.6"
  stroke-linecap="round"
  stroke-linejoin="round"
  class={className}
  aria-hidden="true"><path d={paths[name]} /></svg
>
