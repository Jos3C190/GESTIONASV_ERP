import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import HandlingUnitLotIdentity from './HandlingUnitLotIdentity.svelte';

describe('HandlingUnitLotIdentity', () => {
  it('distingue el lote de fabricante del detalle y cabecera de recepción', () => {
    render(HandlingUnitLotIdentity, {
      props: {
        manufacturerLot: 'FAB-2026-09',
        receiptLot: 'LOT-COM-00017-D1',
        receiptLotHeader: 'LOT-COM-00017'
      }
    });

    expect(screen.getByText('Fabricante: FAB-2026-09')).toBeVisible();
    expect(screen.getByText('Recepción: LOT-COM-00017-D1')).toBeVisible();
    expect(screen.getByText('Recepción agrupada: LOT-COM-00017')).toBeVisible();
  });

  it('muestra el lote de recepción aunque no haya lote de fabricante', () => {
    render(HandlingUnitLotIdentity, {
      props: {
        manufacturerLot: null,
        receiptLot: 'LOT-COM-00017-D1',
        receiptLotHeader: 'LOT-COM-00017'
      }
    });

    expect(screen.queryByText(/Fabricante:/)).not.toBeInTheDocument();
    expect(screen.getByText('Recepción: LOT-COM-00017-D1')).toBeVisible();
    expect(screen.getByText('Recepción agrupada: LOT-COM-00017')).toBeVisible();
    expect(screen.queryByText('Sin lote registrado')).not.toBeInTheDocument();
  });

  it('identifica las unidades históricas sin lote sin inventar un código', () => {
    render(HandlingUnitLotIdentity, {
      props: { manufacturerLot: null, receiptLot: null, receiptLotHeader: null }
    });

    expect(screen.getByText('Sin lote registrado')).toBeVisible();
  });
});
