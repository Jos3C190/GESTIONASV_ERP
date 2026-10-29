import { cleanup, fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import FleetWorkspace from './FleetWorkspace.svelte';
import { DEMO_VEHICLES } from './mock-data';

const availableCount = DEMO_VEHICLES.filter((vehicle) => vehicle.status === 'Disponible').length;

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('fleet UI prototype', () => {
  it.each([
    ['Panel compacto', 'FL-010', 'compact-panel-van.png', '750 kg'],
    ['Con lona', 'FL-011', 'curtain-side-truck.png', '8,000 kg'],
    ['Tráiler', 'FL-012', 'semi-trailer-truck.png', '24,000 kg'],
    ['Cisterna', 'FL-013', 'tanker-truck.png', '12,000 kg']
  ])('opens the correct image and capacity for %s', async (kind, id, filename, capacity) => {
    render(FleetWorkspace);
    await fireEvent.change(screen.getByLabelText('Tipo de vehículo'), {
      target: { value: kind }
    });
    expect(screen.getAllByRole('button', { name: /^Ver detalle de/ })).toHaveLength(1);
    const card = screen.getByRole('button', { name: `Ver detalle de ${id}` });
    expect(within(card).getByRole('img')).toHaveAttribute('src', `/images/fleet/${filename}`);
    await fireEvent.click(card);
    const detail = screen.getByRole('complementary', { name: `Detalle de ${id}` });
    expect(within(detail).getByRole('img')).toHaveAttribute('src', `/images/fleet/${filename}`);
    expect(within(detail).getByText(kind, { exact: true })).toBeVisible();
    expect(within(detail).getByText(capacity, { exact: true })).toBeVisible();
  });

  it('filters the new vehicle types and keeps the matching image in the detail', async () => {
    render(FleetWorkspace);
    await fireEvent.change(screen.getByLabelText('Tipo de vehículo'), {
      target: { value: 'Pickup' }
    });
    expect(screen.getAllByRole('button', { name: /^Ver detalle de/ })).toHaveLength(2);
    await fireEvent.click(screen.getByRole('button', { name: /^Disponibles / }));
    expect(screen.getAllByRole('button', { name: /^Ver detalle de/ })).toHaveLength(1);
    await fireEvent.click(screen.getByRole('button', { name: 'Ver detalle de FL-008' }));
    const detail = screen.getByRole('complementary', { name: 'Detalle de FL-008' });
    expect(within(detail).getByRole('img', { name: /Toyota Hilux/ })).toHaveAttribute(
      'src',
      '/images/fleet/pickup.png'
    );
    await fireEvent.keyDown(window, { key: 'Escape' });
    await fireEvent.click(screen.getByRole('button', { name: /^Todos los vehículos / }));
    await fireEvent.change(screen.getByLabelText('Tipo de vehículo'), {
      target: { value: 'Plataforma' }
    });
    expect(screen.getByRole('button', { name: 'Ver detalle de FL-007' })).toBeVisible();
    expect(screen.getByRole('img', { name: /Isuzu NPR 75/ })).toHaveAttribute(
      'src',
      '/images/fleet/flatbed-truck.png'
    );
    await fireEvent.change(screen.getByLabelText('Tipo de vehículo'), {
      target: { value: 'Carga seca' }
    });
    expect(screen.getByRole('button', { name: 'Ver detalle de FL-003' })).toBeVisible();
    expect(screen.getByRole('img', { name: /Hino Serie 300/ })).toHaveAttribute(
      'src',
      '/images/fleet/dry-box-truck.png'
    );
  });

  it('combines status, type and text filters and recovers from an empty result', async () => {
    render(FleetWorkspace);
    await fireEvent.click(screen.getByRole('button', { name: /^Disponibles / }));
    expect(screen.getAllByRole('button', { name: /^Ver detalle de/ })).toHaveLength(availableCount);
    await fireEvent.change(screen.getByLabelText('Tipo de vehículo'), {
      target: { value: 'Refrigerado' }
    });
    expect(screen.getByLabelText('Tipo de vehículo')).toHaveValue('Refrigerado');
    expect(screen.getByText('No encontramos vehículos')).toBeVisible();
    await fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    expect(screen.getAllByRole('button', { name: /^Ver detalle de/ })).toHaveLength(
      DEMO_VEHICLES.length
    );
    await fireEvent.input(screen.getByLabelText('Buscar vehículos'), {
      target: { value: 'C 345-678' }
    });
    expect(screen.getAllByRole('button', { name: /^Ver detalle de/ })).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Ver detalle de FL-003' })).toBeVisible();
  });

  it('previews vehicle sections without calling a backend and closes with Escape', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    render(FleetWorkspace);
    await fireEvent.click(screen.getByRole('button', { name: 'Ver detalle de FL-001' }));
    expect(screen.getByRole('complementary', { name: 'Detalle de FL-001' })).toBeVisible();
    await fireEvent.click(screen.getByRole('button', { name: 'Documentos' }));
    expect(screen.getByText('Tarjeta de circulación')).toBeVisible();
    await fireEvent.click(screen.getByRole('button', { name: 'Mantenimiento' }));
    expect(screen.getByText('Cambio de aceite y filtros')).toBeVisible();
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(
      screen.queryByRole('complementary', { name: 'Detalle de FL-001' })
    ).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('shows document alerts on the cards', () => {
    render(FleetWorkspace);
    const card = screen.getByRole('button', { name: 'Ver detalle de FL-001' });
    expect(within(card).getByText('Seguro vence en 5 días')).toBeVisible();
    const overdue = screen.getByRole('button', { name: 'Ver detalle de FL-004' });
    expect(within(overdue).getByText('Servicio vencido')).toBeVisible();
    const clear = screen.getByRole('button', { name: 'Ver detalle de FL-006' });
    expect(within(clear).getByText('Documentos y servicio al día')).toBeVisible();
  });

  it('adds gallery photos and browses them in the viewer', async () => {
    let created = 0;
    vi.spyOn(URL, 'createObjectURL').mockImplementation(() => `blob:photo-${++created}`);
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const { container } = render(FleetWorkspace);
    await fireEvent.click(screen.getByRole('button', { name: 'Ver detalle de FL-002' }));
    const detail = screen.getByRole('complementary', { name: 'Detalle de FL-002' });
    await fireEvent.click(within(detail).getByRole('button', { name: 'Galería' }));
    expect(within(detail).getByText('Agrega fotos de esta unidad')).toBeVisible();

    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const files = ['frente.jpg', 'lateral.png'].map(
      (name) => new File(['x'], name, { type: name.endsWith('png') ? 'image/png' : 'image/jpeg' })
    );
    Object.defineProperty(input, 'files', { value: files, configurable: true });
    await fireEvent.change(input);

    await fireEvent.click(within(detail).getByRole('button', { name: 'Ampliar foto 1' }));
    const viewer = screen.getByRole('dialog', { name: 'FL-002 · Ford Transit' });
    expect(within(viewer).getByText('1 / 2')).toBeVisible();
    await fireEvent.click(within(viewer).getByRole('button', { name: 'Imagen siguiente' }));
    expect(within(viewer).getByText('2 / 2')).toBeVisible();
    await fireEvent.click(within(viewer).getByRole('button', { name: 'Acercar' }));
    expect(within(viewer).getByText('150%')).toBeVisible();
    await fireEvent.keyDown(within(viewer).getByRole('button', { name: 'Cerrar visor' }), {
      key: 'Escape'
    });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: 'Detalle de FL-002' })).toBeVisible();
  });

  it('keeps filtered results when switching between cards and list', async () => {
    render(FleetWorkspace);
    await fireEvent.input(screen.getByLabelText('Buscar vehículos'), {
      target: { value: 'Sofia' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Vista de lista' }));
    expect(screen.getByRole('table', { name: 'Vehículos de demostración' })).toBeVisible();
    expect(screen.getByText('Sofía Castro')).toBeVisible();
    expect(screen.getAllByRole('button', { name: /^Ver detalle de/ })).toHaveLength(1);
    await fireEvent.click(screen.getByRole('button', { name: 'Vista de tarjetas' }));
    expect(screen.getByRole('button', { name: 'Ver detalle de FL-006' })).toBeVisible();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
