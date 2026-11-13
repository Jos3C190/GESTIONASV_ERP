import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  makeDiscrepancy,
  makeLine,
  makeTransfer
} from '../../../../../tests/unit/fixtures/inventory-transfer';
import type { InventoryTransfer, TransferDiscrepancy } from '../transfer-documents';

const servicesMock = vi.hoisted(() => ({ listPackaging: vi.fn() }));
vi.mock('$lib/features/inventory/services', () => ({ inventoryApi: servicesMock }));

import TransferDiscrepancyPanel from './TransferDiscrepancyPanel.svelte';

type Permissions = Partial<{
  canReceive: boolean;
  canAdjust: boolean;
  canApproveAdjust: boolean;
  canSeeCost: boolean;
  canAccessOrigin: boolean;
  canAccessDestination: boolean;
}>;

const everything: Permissions = {
  canReceive: true,
  canAdjust: true,
  canApproveAdjust: true,
  canSeeCost: false,
  canAccessOrigin: true,
  canAccessDestination: true
};

function transferWith(
  discrepancies: TransferDiscrepancy[],
  patch: Partial<InventoryTransfer> = {}
): InventoryTransfer {
  return makeTransfer({
    status: 'discrepancy',
    code: 'TR-DEMO-A',
    origin_warehouse_name: 'Bodega Central',
    origin_branch_name: 'Casa matriz',
    discrepancies,
    lines: [makeLine({ id: 'line-1', inventory_item_id: 'item-1' })],
    ...patch
  });
}

function mount(
  discrepancies: TransferDiscrepancy[],
  permissions: Permissions = everything,
  patch: Partial<InventoryTransfer> = {}
) {
  const onRun = vi.fn().mockResolvedValue(null);
  render(TransferDiscrepancyPanel, {
    transfer: transferWith(discrepancies, patch),
    canReceive: false,
    canAdjust: false,
    canApproveAdjust: false,
    canAccessOrigin: false,
    canAccessDestination: false,
    formatDate: (value: string | null | undefined) => (value ? '20 oct 2026' : 'Sin fecha'),
    onRun,
    ...permissions
  });
  return onRun;
}

const damage = (patch: Partial<TransferDiscrepancy> = {}) => makeDiscrepancy(patch);
const shortage = (patch: Partial<TransferDiscrepancy> = {}) =>
  makeDiscrepancy({
    id: 'disc-short',
    kind: 'shortage',
    damage_type: null,
    quantity: '3',
    notes: 'No llegó el resto',
    location_id: null,
    location_code: null,
    handling_unit_id: null,
    handling_unit_code: null,
    ...patch
  });
const surplus = (patch: Partial<TransferDiscrepancy> = {}) =>
  makeDiscrepancy({
    id: 'disc-extra',
    kind: 'surplus',
    damage_type: null,
    quantity: '1',
    notes: 'Llegó una caja de más',
    ...patch
  });

const buttons = () => screen.queryAllByRole('button').map((button) => button.textContent?.trim());

beforeEach(() => {
  servicesMock.listPackaging.mockResolvedValue([
    {
      id: 'pack-1',
      inventory_item_id: 'item-1',
      code: 'CJ-12',
      name: 'Caja de 12',
      base_quantity: 12,
      is_current: true,
      is_active: true
    },
    {
      id: 'pack-old',
      inventory_item_id: 'item-1',
      code: 'CJ-6',
      name: 'Caja de 6 (anterior)',
      base_quantity: 6,
      is_current: false,
      is_active: true
    }
  ]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('TransferDiscrepancyPanel', () => {
  it('describe cada diferencia con su tipo, cantidad, avería, ubicación y estado', () => {
    mount([damage(), shortage(), surplus()]);
    expect(
      screen.getByText('Con discrepancia: resuelve cada diferencia para cerrar el traslado.')
    ).toBeInTheDocument();
    const rows = screen.getAllByRole('article');
    expect(rows).toHaveLength(3);
    const first = within(rows[0]!);
    expect(first.getByText('Avería')).toBeInTheDocument();
    expect(first.getByText(/2\s*u\s*·\s*Rotura/)).toBeInTheDocument();
    expect(first.getByText('Cajas rotas al descargar')).toBeInTheDocument();
    expect(first.getByText(/Ubicación QUA-01/)).toBeInTheDocument();
    expect(first.getByText('Abierta')).toBeInTheDocument();
    expect(within(rows[1]!).getByText('Faltante')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('Sobrante')).toBeInTheDocument();
    expect(
      screen.getByText('1 avería por resolver · 1 faltante por resolver · 1 sobrante por resolver')
    ).toBeInTheDocument();
  });

  it('en otros estados no repite el encabezado de discrepancia', () => {
    mount([damage({ status: 'in_claim', claim_reference: 'REC-7' })], everything, {
      status: 'closed_with_adjustment'
    });
    expect(screen.queryByText(/Con discrepancia: resuelve/)).not.toBeInTheDocument();
    expect(screen.getByText('1 avería en reclamo')).toBeInTheDocument();
    expect(screen.getByText(/En reclamo: REC-7/)).toBeInTheDocument();
  });

  it('enlaza el ajuste vinculado y muestra cómo terminó una diferencia resuelta', () => {
    mount([
      damage({
        status: 'resolved',
        resolution: 'written_off',
        resolved_at: '2026-10-21T10:00:00Z',
        resolved_by_name: 'Luis Jefe',
        resolution_notes: 'Baja aplicada',
        adjustment: { id: 'adj-1', code: 'AJ-DEMO-1', status: 'applied' }
      })
    ]);
    const link = screen.getByRole('link', { name: 'AJ-DEMO-1' });
    expect(link).toHaveAttribute('href', '/inventory/adjustments/adj-1');
    expect(screen.getAllByText('Dada de baja').length).toBeGreaterThan(0);
    expect(screen.getByText(/por Luis Jefe: Baja aplicada/)).toBeInTheDocument();
    expect(buttons()).toEqual([]);
  });

  describe('permisos y lado del traslado', () => {
    it('una avería abierta ofrece baja, reclamo y liberación a quien puede todo en el destino', () => {
      mount([damage()]);
      expect(buttons()).toEqual([
        'Preparar ajuste de baja',
        'Registrar reclamo',
        'Liberar a cuarentena'
      ]);
    });

    it('sin permiso de aprobar ajustes solo ofrece preparar la baja', () => {
      mount([damage()], { ...everything, canApproveAdjust: false });
      expect(buttons()).toEqual(['Preparar ajuste de baja']);
    });

    it('sin permiso de ajustes no ofrece preparar la baja, pero sí reclamo y liberación', () => {
      mount([damage()], { ...everything, canAdjust: false });
      expect(buttons()).toEqual(['Registrar reclamo', 'Liberar a cuarentena']);
    });

    it('sin acceso al destino no ofrece nada sobre una avería y lo explica', () => {
      mount([damage()], { ...everything, canAccessDestination: false });
      expect(buttons()).toEqual([]);
      expect(screen.getByText(/permiso de ajustes y acceso a la sucursal de destino/)).toBeInTheDocument();
    });

    it('un faltante se puede ajustar desde cualquiera de los dos lados', () => {
      mount([shortage()], {
        canAdjust: true,
        canAccessOrigin: true,
        canAccessDestination: false
      });
      expect(buttons()).toEqual(['Preparar ajuste de baja']);
      cleanup();
      mount([shortage()], {
        canAdjust: true,
        canReceive: true,
        canAccessOrigin: false,
        canAccessDestination: true
      });
      expect(buttons()).toEqual(['Preparar ajuste de baja', 'Llegó la mercadería']);
    });

    it('«Llegó la mercadería» exige permiso de recepción y el lado del destino', () => {
      mount([shortage()], { ...everything, canReceive: false });
      expect(buttons()).toEqual(['Preparar ajuste de baja']);
    });

    it('un sobrante ofrece el ajuste de ingreso y descartarlo solo en el destino', () => {
      mount([surplus()]);
      expect(buttons()).toEqual(['Preparar ajuste de ingreso', 'Descartar sobrante']);
      cleanup();
      mount([surplus()], { ...everything, canAccessDestination: false });
      expect(buttons()).toEqual([]);
    });

    it('una avería en reclamo ya no ofrece reclamar, pero sí liberar y dar de baja', () => {
      mount([damage({ status: 'in_claim', claim_reference: 'REC-7' })]);
      expect(buttons()).toEqual(['Preparar ajuste de baja', 'Liberar a cuarentena']);
    });

    it('con un ajuste en curso no ofrece prepararlo otra vez ni resolver la diferencia por otro camino', () => {
      mount([damage({ adjustment: { id: 'adj-1', code: 'AJ-DEMO-1', status: 'draft' } })]);
      expect(buttons()).toEqual([]);
      expect(screen.getByRole('link', { name: 'AJ-DEMO-1' })).toBeInTheDocument();
      expect(screen.getByText(/Hay un ajuste en curso/)).toBeInTheDocument();
      cleanup();
      mount([shortage({ adjustment: { id: 'adj-2', code: 'AJ-DEMO-2', status: 'approved' } })]);
      expect(buttons()).toEqual([]);
      cleanup();
      mount([surplus({ adjustment: { id: 'adj-3', code: 'AJ-DEMO-3', status: 'draft' } })]);
      expect(buttons()).toEqual([]);
      cleanup();
      // A cancelled adjustment no longer blocks anything.
      mount([damage({ adjustment: { id: 'adj-4', code: 'AJ-DEMO-4', status: 'cancelled' } })]);
      expect(buttons()).toEqual(['Preparar ajuste de baja', 'Registrar reclamo', 'Liberar a cuarentena']);
    });
  });

  describe('conteo en origen', () => {
    it('avisa en el lado origen y ofrece registrar el conteo de cada diferencia', async () => {
      const onRun = mount([shortage({ origin_count_required: true })], {
        canAdjust: true,
        canAccessOrigin: true,
        canAccessDestination: false
      });
      expect(screen.getByText(/Conteo pendiente en origen: cuenta las existencias de Casa matriz/)).toBeInTheDocument();
      expect(screen.getAllByText('Conteo pendiente en origen').length).toBeGreaterThan(0);
      await fireEvent.click(screen.getByRole('button', { name: 'Registrar conteo en origen' }));
      const notes = await screen.findByLabelText('Resultado del conteo en origen');
      expect(notes).toHaveFocus();
      await fireEvent.input(notes, { target: { value: 'Se contó la estantería A' } });
      await fireEvent.click(screen.getByRole('button', { name: 'Guardar conteo' }));
      await waitFor(() =>
        expect(onRun).toHaveBeenCalledWith({
          action: 'origin-count',
          discrepancy: expect.objectContaining({ id: 'disc-short' }),
          notes: 'Se contó la estantería A'
        })
      );
    });

    it('no ofrece el conteo al lado destino ni cuando ya se registró', () => {
      mount([shortage({ origin_count_required: true })], {
        ...everything,
        canAccessOrigin: false
      });
      expect(buttons()).not.toContain('Registrar conteo en origen');
      expect(screen.queryByText(/Conteo pendiente en origen: cuenta/)).not.toBeInTheDocument();
      cleanup();
      mount([
        shortage({
          origin_count_required: true,
          origin_counted_at: '2026-10-21T08:00:00Z',
          origin_counted_by_name: 'Mario Bodega',
          origin_count_notes: 'Coincide con el sistema'
        })
      ]);
      expect(buttons()).not.toContain('Registrar conteo en origen');
      expect(screen.getByText(/Conteo en origen registrado el 20 oct 2026 por Mario Bodega/)).toBeInTheDocument();
    });
  });

  describe('formularios', () => {
    it('registra un reclamo con su referencia y devuelve el foco', async () => {
      const onRun = mount([damage()]);
      await fireEvent.click(screen.getByRole('button', { name: 'Registrar reclamo' }));
      const reference = await screen.findByLabelText('Referencia del reclamo');
      expect(reference).toHaveFocus();
      await fireEvent.input(reference, { target: { value: 'ab' } });
      await fireEvent.click(screen.getByRole('button', { name: 'Guardar reclamo' }));
      expect(await screen.findByRole('alert')).toHaveTextContent(/mínimo 3 caracteres/);
      expect(onRun).not.toHaveBeenCalled();

      await fireEvent.input(reference, { target: { value: 'REC-2026-7' } });
      await fireEvent.click(screen.getByRole('button', { name: 'Guardar reclamo' }));
      await waitFor(() =>
        expect(onRun).toHaveBeenCalledWith({
          action: 'claim',
          discrepancy: expect.objectContaining({ id: 'disc-1' }),
          claimReference: 'REC-2026-7'
        })
      );
      await waitFor(() =>
        expect(screen.queryByLabelText('Referencia del reclamo')).not.toBeInTheDocument()
      );
      await waitFor(() =>
        expect(screen.getByRole('button', { name: 'Registrar reclamo' })).toHaveFocus()
      );
    });

    it('libera a cuarentena con notas y una ubicación opcional', async () => {
      const onRun = vi.fn().mockResolvedValue(null);
      render(TransferDiscrepancyPanel, {
        transfer: transferWith([damage()]),
        canReceive: true,
        canAdjust: true,
        canApproveAdjust: true,
        canAccessOrigin: true,
        canAccessDestination: true,
        locations: [{ id: 'loc-9', code: 'QUA-09', location_type: 'quarantine' }],
        formatDate: () => '20 oct 2026',
        onRun
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Liberar a cuarentena' }));
      const notes = await screen.findByLabelText('Resultado de la inspección');
      await fireEvent.input(notes, { target: { value: 'Inspección sin daño real' } });
      await fireEvent.change(screen.getByLabelText('Ubicación de cuarentena (opcional)'), {
        target: { value: 'loc-9' }
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Confirmar liberación' }));
      await waitFor(() =>
        expect(onRun).toHaveBeenCalledWith({
          action: 'release',
          discrepancy: expect.objectContaining({ id: 'disc-1' }),
          notes: 'Inspección sin daño real',
          locationId: 'loc-9'
        })
      );
    });

    it('marca que llegó un faltante y descarta un sobrante con una nota', async () => {
      const onRun = mount([shortage(), surplus()]);
      await fireEvent.click(screen.getByRole('button', { name: 'Llegó la mercadería' }));
      await fireEvent.input(await screen.findByLabelText('Cómo llegó o dónde se encontró'), {
        target: { value: 'Apareció en otra tarima' }
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Confirmar que llegó' }));
      await waitFor(() =>
        expect(onRun).toHaveBeenCalledWith(
          expect.objectContaining({ action: 'found', notes: 'Apareció en otra tarima' })
        )
      );
      await fireEvent.click(await screen.findByRole('button', { name: 'Descartar sobrante' }));
      await fireEvent.input(await screen.findByLabelText('Por qué se descarta'), {
        target: { value: 'Era de otro proveedor' }
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Confirmar descarte' }));
      await waitFor(() =>
        expect(onRun).toHaveBeenLastCalledWith(
          expect.objectContaining({ action: 'dismiss', notes: 'Era de otro proveedor' })
        )
      );
    });

    it('prepara el ajuste de baja de una avería con motivo y documento', async () => {
      const onRun = mount([damage()]);
      await fireEvent.click(screen.getByRole('button', { name: 'Preparar ajuste de baja' }));
      const reason = await screen.findByLabelText('Motivo del ajuste');
      expect(reason).toHaveValue('Baja por avería del traslado TR-DEMO-A');
      expect(screen.queryByLabelText('Costo documentado')).not.toBeInTheDocument();
      expect(screen.queryByText('Empaque del sobrante')).not.toBeInTheDocument();
      await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador del ajuste' }));
      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Indica la referencia del documento de respaldo.'
      );
      await fireEvent.input(screen.getByLabelText('Documento de respaldo (referencia)'), {
        target: { value: 'ACTA-55' }
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador del ajuste' }));
      await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
      const request = onRun.mock.calls[0]![0];
      expect(request.action).toBe('adjust');
      expect(request.form).toMatchObject({
        reason: 'Baja por avería del traslado TR-DEMO-A',
        documentReference: 'ACTA-55',
        packaging: 'source',
        costMode: 'none'
      });
      expect(request.form.operationalDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('para un sobrante pide empaque o medidas y el costo solo a quien puede verlo', async () => {
      const onRun = mount([surplus()], { ...everything, canSeeCost: true });
      await fireEvent.click(screen.getByRole('button', { name: 'Preparar ajuste de ingreso' }));
      await screen.findByLabelText('Motivo del ajuste');
      expect(screen.getByLabelText('Igual que la unidad de origen (recomendado)')).toBeChecked();
      await fireEvent.input(screen.getByLabelText('Documento de respaldo (referencia)'), {
        target: { value: 'ACTA-9' }
      });

      await fireEvent.click(screen.getByLabelText('Indicar peso y volumen reales'));
      await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador del ajuste' }));
      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Indica el peso bruto (kg) y el volumen (m³) del sobrante.'
      );
      await fireEvent.input(screen.getByLabelText('Peso bruto (kg)'), { target: { value: '12.5' } });
      await fireEvent.input(screen.getByLabelText('Volumen (m³)'), { target: { value: '0.08' } });

      await fireEvent.change(screen.getByLabelText('Costo documentado'), {
        target: { value: 'unit' }
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador del ajuste' }));
      expect(await screen.findByRole('alert')).toHaveTextContent(/Indica un costo/);
      await fireEvent.input(screen.getByLabelText('Costo por unidad base'), {
        target: { value: '4.25' }
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador del ajuste' }));
      await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
      expect(onRun.mock.calls[0]![0].form).toMatchObject({
        packaging: 'measures',
        weightKg: '12.5',
        volumeM3: '0.08',
        costMode: 'unit',
        cost: '4.25',
        documentReference: 'ACTA-9'
      });
    });

    it('permite elegir un empaque vigente del producto', async () => {
      mount([surplus()]);
      await fireEvent.click(screen.getByRole('button', { name: 'Preparar ajuste de ingreso' }));
      await fireEvent.click(await screen.findByLabelText('Elegir un empaque del producto'));
      await waitFor(() => expect(servicesMock.listPackaging).toHaveBeenCalledWith('item-1'));
      const select = await screen.findByLabelText('Empaque');
      await waitFor(() => expect(within(select).getAllByRole('option')).toHaveLength(2));
      expect(within(select).getByRole('option', { name: /Caja de 12/ })).toBeInTheDocument();
      expect(within(select).queryByRole('option', { name: /anterior/ })).not.toBeInTheDocument();
    });

    it('muestra el error del servidor junto al formulario y lo deja abierto', async () => {
      const onRun = mount([damage()]);
      onRun.mockResolvedValue('Esta avería ya tiene un ajuste activo.');
      await fireEvent.click(screen.getByRole('button', { name: 'Registrar reclamo' }));
      await fireEvent.input(await screen.findByLabelText('Referencia del reclamo'), {
        target: { value: 'REC-1' }
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Guardar reclamo' }));
      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Esta avería ya tiene un ajuste activo.'
      );
      expect(screen.getByLabelText('Referencia del reclamo')).toBeInTheDocument();
    });

    it('Escape cierra el formulario y devuelve el foco al botón', async () => {
      mount([damage()]);
      await fireEvent.click(screen.getByRole('button', { name: 'Liberar a cuarentena' }));
      await fireEvent.keyDown(await screen.findByLabelText('Resultado de la inspección'), {
        key: 'Escape'
      });
      await waitFor(() =>
        expect(screen.queryByLabelText('Resultado de la inspección')).not.toBeInTheDocument()
      );
      expect(screen.getByRole('button', { name: 'Liberar a cuarentena' })).toHaveFocus();
    });

    it('exige una nota de al menos cinco caracteres antes de liberar', async () => {
      const onRun = mount([damage()]);
      await fireEvent.click(screen.getByRole('button', { name: 'Liberar a cuarentena' }));
      await fireEvent.input(await screen.findByLabelText('Resultado de la inspección'), {
        target: { value: 'ok' }
      });
      await fireEvent.click(screen.getByRole('button', { name: 'Confirmar liberación' }));
      expect(await screen.findByRole('alert')).toHaveTextContent(/al menos 5 caracteres/);
      expect(onRun).not.toHaveBeenCalled();
    });
  });
});
