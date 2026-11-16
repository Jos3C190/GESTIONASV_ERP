import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { fiscalApi } = vi.hoisted(() => ({
  fiscalApi: {
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    listActivities: vi.fn(),
    listBranchOptions: vi.fn(),
    listEstablishments: vi.fn(),
    createEstablishment: vi.fn(),
    listDocumentTypes: vi.fn(),
    updateDocumentType: vi.fn()
  }
}));

vi.mock('$lib/api/fiscal', () => ({ fiscalApi }));
vi.mock('$lib/api/client', () => ({
  HttpError: class HttpError extends Error {
    code = 'error';
    status = 422;
  }
}));

import type { DocumentTypeSetting, Establishment, FiscalProfile } from '$lib/types/fiscal';
import FiscalDocumentsPanel from './FiscalDocumentsPanel.svelte';
import FiscalEstablishmentsPanel from './FiscalEstablishmentsPanel.svelte';
import FiscalProfilePanel from './FiscalProfilePanel.svelte';

const profile: FiscalProfile = {
  company_id: 'company-1',
  company_name: 'Empresa ficticia, S.A. de C.V.',
  commercial_name: 'Empresa ficticia',
  nit: '0614-000000-000-0',
  nrc: '000000',
  taxpayer_category: 'medium',
  person_type: '2',
  operating_mode: 'simulated',
  dte_email: null,
  dte_phone: null,
  configured: true,
  updated_at: null,
  production_blockers: ['Habilita al menos un tipo de documento.']
};

const establishment: Establishment = {
  id: 'est-1',
  branch_id: 'branch-1',
  branch_name: 'Casa matriz ficticia',
  establishment_type: '02',
  code: 'M001',
  activity_id: null,
  activity_code: null,
  is_active: true,
  address: {
    department: 'San Salvador',
    department_code: '06',
    municipality: 'San Salvador Centro',
    municipality_code: '23',
    district: 'San Salvador',
    district_code: '14',
    complement: 'Calle ficticia',
    complete: true
  },
  phone: null,
  email: null,
  points_of_sale: [
    { id: 'pos-1', establishment_id: 'est-1', code: 'P001', name: 'Caja 1', is_active: true }
  ]
};

const invoice: DocumentTypeSetting = {
  document_type: '01',
  name: 'Factura',
  is_enabled: false,
  certification_status: 'pending',
  certified_at: null,
  notes: null
};

describe('fiscal settings panels', () => {
  beforeEach(() => {
    for (const fn of Object.values(fiscalApi)) fn.mockReset();
    fiscalApi.getProfile.mockResolvedValue(profile);
    fiscalApi.listActivities.mockResolvedValue([]);
  });

  it('shows what is missing before production and the company identity', async () => {
    render(FiscalProfilePanel, { canManage: true });
    expect(await screen.findByText('Empresa ficticia, S.A. de C.V.')).toBeInTheDocument();
    expect(screen.getByText('Para emitir en producción falta:')).toBeInTheDocument();
    expect(screen.getByText('Habilita al menos un tipo de documento.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar perfil' })).toBeInTheDocument();
  });

  it('is read only without the manage permission', async () => {
    render(FiscalProfilePanel, { canManage: false });
    await screen.findByText('Empresa ficticia, S.A. de C.V.');
    expect(screen.queryByRole('button', { name: 'Guardar perfil' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Categoría de contribuyente')).toBeDisabled();
  });

  it('lists establishments with their Hacienda codes and points of sale', async () => {
    fiscalApi.listEstablishments.mockResolvedValue([establishment]);
    fiscalApi.listBranchOptions.mockResolvedValue([
      {
        id: 'branch-1',
        name: 'Casa matriz ficticia',
        code: null,
        is_headquarters: true,
        establishment_id: 'est-1'
      },
      {
        id: 'branch-2',
        name: 'Tienda ficticia',
        code: 'T1',
        is_headquarters: false,
        establishment_id: null
      }
    ]);
    render(FiscalEstablishmentsPanel, { canManage: true });
    expect(await screen.findByText('M001')).toBeInTheDocument();
    expect(screen.getByText(/Departamento 06 · municipio 23/)).toBeInTheDocument();
    expect(screen.getByText('P001')).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Registrar establecimiento' }));
    // La tienda libre es una sucursal: el código sugerido usa la letra S.
    expect(screen.getByLabelText('Código')).toHaveValue('S001');
  });

  it('shows the empty state when there are no establishments', async () => {
    fiscalApi.listEstablishments.mockResolvedValue([]);
    fiscalApi.listBranchOptions.mockResolvedValue([]);
    render(FiscalEstablishmentsPanel, { canManage: true });
    expect(await screen.findByText('Aún no hay establecimientos')).toBeInTheDocument();
  });

  it('enables a document and shows the server rule when it is rejected', async () => {
    fiscalApi.listDocumentTypes.mockResolvedValue([invoice]);
    const { HttpError } = await import('$lib/api/client');
    fiscalApi.updateDocumentType.mockRejectedValueOnce(
      new HttpError('En producción solo se habilita «Factura» después de aprobar sus pruebas.')
    );
    render(FiscalDocumentsPanel, { canManage: true });
    const toggle = await screen.findByRole('checkbox');
    await fireEvent.click(toggle);
    await waitFor(() =>
      expect(fiscalApi.updateDocumentType).toHaveBeenCalledWith('01', {
        is_enabled: true,
        certification_status: 'pending',
        notes: null
      })
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('después de aprobar sus pruebas');
    // El servidor rechazó el cambio: la casilla vuelve a mostrarse deshabilitada.
    expect(toggle).not.toBeChecked();
  });
});
