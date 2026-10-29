import { describe, expect, it } from 'vitest';
import {
  buildPutawayAllocations,
  subtractBaseQuantities,
  sumBaseQuantities
} from './putaway-group';

describe('grouped putaway planning', () => {
  it('splits one pending handling unit across two locations without exceeding its balance', () => {
    const result = buildPutawayAllocations(
      [{ id: 'hu-20', code: 'HU-20', pending_quantity_base: '20.000000' }],
      [
        { destination_location_id: 'loc-a', quantity_base: '12' },
        { destination_location_id: 'loc-b', quantity_base: '8' }
      ]
    );

    expect(result).toEqual({
      allocations: [
        { handling_unit_id: 'hu-20', destination_location_id: 'loc-a', quantity_base: '12' },
        { handling_unit_id: 'hu-20', destination_location_id: 'loc-b', quantity_base: '8' }
      ],
      error: null
    });
  });

  it('allocates a product group across its source units in stable code order', () => {
    const result = buildPutawayAllocations(
      [
        { id: 'hu-b', code: 'HU-B', pending_quantity_base: '5' },
        { id: 'hu-a', code: 'HU-A', pending_quantity_base: '7' }
      ],
      [{ destination_location_id: 'loc-a', quantity_base: '10' }]
    );

    expect(result.allocations).toEqual([
      { handling_unit_id: 'hu-a', destination_location_id: 'loc-a', quantity_base: '7' },
      { handling_unit_id: 'hu-b', destination_location_id: 'loc-a', quantity_base: '3' }
    ]);
  });

  it('rejects a plan above the pending balance and preserves six-decimal arithmetic', () => {
    const overPlan = buildPutawayAllocations(
      [{ id: 'hu-1', code: 'HU-1', pending_quantity_base: '1.25' }],
      [{ destination_location_id: 'loc-a', quantity_base: '1.250001' }]
    );
    expect(overPlan).toMatchObject({ allocations: null });
    expect(overPlan.error).toContain('supera');
    expect(sumBaseQuantities(['0.1', '0.2', '0.000001'])).toBe('0.300001');
    expect(subtractBaseQuantities('20', '12')).toBe('8');
  });

  it('rejects empty locations, zero amounts, and precision beyond six decimals', () => {
    const source = [{ id: 'hu-1', code: 'HU-1', pending_quantity_base: '4' }];
    expect(
      buildPutawayAllocations(source, [{ destination_location_id: '', quantity_base: '1' }]).error
    ).toMatch(/ubicación/i);
    expect(
      buildPutawayAllocations(source, [{ destination_location_id: 'loc-a', quantity_base: '0' }])
        .error
    ).toMatch(/mayor que cero/i);
    expect(
      buildPutawayAllocations(source, [
        { destination_location_id: 'loc-a', quantity_base: '1.0000001' }
      ]).error
    ).toMatch(/mayor que cero/i);
  });
});
