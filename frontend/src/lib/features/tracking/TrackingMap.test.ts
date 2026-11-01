import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TrackingMap from './TrackingMap.svelte';

const loader = vi.hoisted(() => vi.fn());
vi.mock('./maplibre', () => ({
  DEFAULT_CENTER: [-88.18, 13.48],
  MAP_STYLE: 'test-style',
  loadMapLibre: loader
}));

class TestMap {
  static instances: TestMap[] = [];
  handlers = new Map<string, () => void>();
  remove = vi.fn();
  resize = vi.fn();
  doubleClickZoom = { enable: vi.fn(), disable: vi.fn() };
  canvas = document.createElement('canvas');
  constructor() {
    TestMap.instances.push(this);
  }
  addControl() {}
  on(name: string, handler: () => void) {
    this.handlers.set(name, handler);
  }
  getCanvas() {
    return this.canvas;
  }
  emit(name: string) {
    this.handlers.get(name)?.();
  }
}
class TestControl {}

beforeEach(() => {
  TestMap.instances = [];
  loader.mockReset().mockResolvedValue({
    Map: TestMap,
    NavigationControl: TestControl,
    FullscreenControl: TestControl,
    ScaleControl: TestControl
  });
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    }
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('map loading and recovery', () => {
  it('announces loading until the cartography is ready', async () => {
    render(TrackingMap, { vehicles: [], onselect: vi.fn() });
    expect(screen.getByRole('status')).toHaveTextContent('Cargando mapa');
    await waitFor(() => expect(TestMap.instances).toHaveLength(1));
    TestMap.instances[0]!.emit('load');
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  });

  it('retries a failed library download', async () => {
    loader.mockRejectedValueOnce(new Error('network'));
    render(TrackingMap, { vehicles: [], onselect: vi.fn() });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('No se pudo cargar'));
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar mapa' }));
    await waitFor(() => expect(TestMap.instances).toHaveLength(1));
    TestMap.instances[0]!.emit('load');
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it('recovers from an asynchronous style error and releases the failed map', async () => {
    render(TrackingMap, { vehicles: [], onselect: vi.fn() });
    await waitFor(() => expect(TestMap.instances).toHaveLength(1));
    const failed = TestMap.instances[0]!;
    failed.emit('error');
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('cartografía'));
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar mapa' }));
    await waitFor(() => expect(TestMap.instances).toHaveLength(2));
    expect(failed.remove).toHaveBeenCalledOnce();
    TestMap.instances[1]!.emit('load');
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });

  it('keeps a loaded map visible when one resource fails', async () => {
    const { container } = render(TrackingMap, { vehicles: [], onselect: vi.fn() });
    await waitFor(() => expect(TestMap.instances).toHaveLength(1));
    TestMap.instances[0]!.emit('load');
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
    TestMap.instances[0]!.emit('error');
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('posiciones GPS'));
    expect(container.querySelector('.map-error')).toHaveClass('partial');
    expect(TestMap.instances[0]!.remove).not.toHaveBeenCalled();
  });
});
