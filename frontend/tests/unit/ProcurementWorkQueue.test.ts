import { render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ProcurementWorkQueue from '$lib/features/purchase-quotations/components/ProcurementWorkQueue.svelte';

const mocks = vi.hoisted(() => ({
  branchId: null as string | null,
  accessAllBranches: true,
  branchLabel: 'Todas las sucursales',
  selectBranch: vi.fn(),
  hasPermission: vi.fn(),
  requests: vi.fn(),
  quotations: vi.fn(),
  purchases: vi.fn()
}));

vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    get id() {
      return mocks.branchId;
    },
    get accessAllBranches() {
      return mocks.accessAllBranches;
    },
    get label() {
      return mocks.branchLabel;
    },
    select(branchId: string | null) {
      mocks.selectBranch(branchId);
    }
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

vi.mock('$lib/api/purchase-requests', () => ({
  purchaseRequestsApi: {
    list: mocks.requests
  }
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    list: mocks.quotations
  }
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    list: mocks.purchases
  }
}));

function page(total: number) {
  return Promise.resolve({ items: [], meta: { page: 1, size: 1, total, pages: total } });
}

describe('ProcurementWorkQueue', () => {
  beforeEach(() => {
    mocks.branchId = null;
    mocks.accessAllBranches = true;
    mocks.branchLabel = 'Todas las sucursales';
    mocks.selectBranch.mockReset();
    mocks.requests.mockReset();
    mocks.quotations.mockReset();
    mocks.purchases.mockReset();
    mocks.hasPermission.mockReset();

    const granted = new Set([
      'purchase_requests:read',
      'purchase_requests:approve',
      'purchase_quotations:read',
      'purchase_quotations:manage',
      'purchases:read',
      'purchases:verify'
    ]);
    mocks.hasPermission.mockImplementation((code: string) => granted.has(code));
    mocks.requests.mockImplementation((params: { status: string }) =>
      page(params.status === 'submitted' ? 4 : 2)
    );
    mocks.quotations.mockImplementation((params: { status: string }) =>
      page(params.status === 'received' ? 3 : 1)
    );
    mocks.purchases.mockResolvedValue(page(5));
  });

  it('shows permitted queues and scopes request counts to the active branch', async () => {
    mocks.branchId = 'branch-001';
    mocks.accessAllBranches = false;
    mocks.branchLabel = 'Sucursal Centro';

    render(ProcurementWorkQueue);

    expect(screen.getByRole('heading', { name: 'Cola de compras' })).toBeInTheDocument();
    expect(
      screen.getByText(
        'La cola de cotizaciones no se muestra porque el módulo aún no filtra por sucursal.'
      )
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(mocks.requests).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'submitted', branch_id: 'branch-001' })
      );
      expect(screen.getByLabelText('4 pendientes')).toBeInTheDocument();
      expect(screen.getByLabelText('5 pendientes')).toBeInTheDocument();
    });

    expect(
      screen.getByRole('link', {
        name: /Por aprobar.*4 pendientes.*Solicitudes de compra enviadas.*Revisar solicitudes/
      })
    ).toHaveAttribute('href', '/purchase-requests?status=submitted');
    expect(mocks.quotations).not.toHaveBeenCalled();
    expect(screen.queryByRole('link', { name: /Ofertas registradas/ })).not.toBeInTheDocument();
  });

  it('does not render workflow actions when their required permissions are absent', () => {
    mocks.hasPermission.mockReturnValue(false);

    render(ProcurementWorkQueue);

    expect(screen.queryByRole('region', { name: 'Cola de compras' })).not.toBeInTheDocument();
    expect(mocks.requests).not.toHaveBeenCalled();
    expect(mocks.quotations).not.toHaveBeenCalled();
    expect(mocks.purchases).not.toHaveBeenCalled();
  });

  it('shows company-wide quotation queues while a branch is selected', async () => {
    mocks.branchId = 'branch-001';
    mocks.branchLabel = 'Sucursal Centro';

    render(ProcurementWorkQueue);

    await waitFor(() => {
      expect(mocks.quotations).toHaveBeenCalledWith({
        status: 'received',
        page: 1,
        size: 1
      });
      expect(screen.getByLabelText('3 pendientes')).toBeInTheDocument();
    });

    expect(
      screen.getByRole('link', { name: /En evaluación.*Continuar evaluación/ })
    ).toHaveAttribute('href', '/purchase-quotations?status=under_evaluation');
    expect(
      screen.getByRole('link', {
        name: /Ofertas registradas.*3 pendientes.*Respuestas de proveedores ingresadas manualmente.*Revisar respuestas/
      })
    ).toHaveAttribute('href', '/purchase-quotations?status=received');
    expect(screen.getByText(/Cotizaciones: todas las sucursales/)).toBeInTheDocument();
    await screen.getByRole('button', { name: 'Ver todas las sucursales' }).click();
    expect(mocks.selectBranch).toHaveBeenCalledWith(null);
  });

  it('allows authorized all-branch readers to consult quotation queues', async () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_quotations:read');

    render(ProcurementWorkQueue);

    expect(
      screen.getByRole('link', { name: /Ofertas registradas.*Revisar respuestas/ })
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Aprobadas para cotizar/ })).not.toBeInTheDocument();

    await waitFor(() => {
      expect(mocks.quotations).toHaveBeenCalledWith({
        status: 'received',
        page: 1,
        size: 1
      });
      expect(screen.getByLabelText('3 pendientes')).toBeInTheDocument();
    });
  });

  it('offers an accessible retry when a queue count fails', async () => {
    mocks.requests.mockRejectedValueOnce(new Error('Servicio temporalmente no disponible'));

    render(ProcurementWorkQueue);

    expect(
      await screen.findByText(
        'No se pudo cargar el conteo. Puedes abrir la lista o reintentar las tarjetas.'
      )
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar conteos' })).toBeInTheDocument();

    await screen.getByRole('button', { name: 'Reintentar conteos' }).click();

    expect(await screen.findByLabelText('4 pendientes')).toBeInTheDocument();
    expect(mocks.requests).toHaveBeenCalledTimes(4);
  });
});
