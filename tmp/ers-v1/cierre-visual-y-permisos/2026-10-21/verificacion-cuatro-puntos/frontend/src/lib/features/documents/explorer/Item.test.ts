import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import Item from './Item.svelte';
import type { ExplorerItem } from './types';

const fileItem: ExplorerItem = {
  kind: 'file',
  id: 'entry-1',
  name: 'manual.pdf',
  updatedAt: null,
  entry: {
    id: 'entry-1',
    kind: 'file',
    name: 'manual.pdf',
    parent_id: null,
    document_id: 'doc-1',
    updated_at: null
  },
  document: {
    id: 'doc-1',
    title: 'Manual',
    original_filename: 'manual.pdf',
    extension: '.pdf',
    technical_status: 'active',
    business_status: 'current',
    size_bytes: 1024,
    category_name: null
  }
};

function renderItem(oncontextmenu = vi.fn(), compact = false) {
  return render(Item, {
    props: {
      item: fileItem,
      selected: false,
      compact,
      canRename: true,
      canMove: true,
      canDelete: true,
      canRestore: false,
      onselect: vi.fn(),
      onopen: vi.fn(),
      oncontextmenu,
      ondragstart: vi.fn(),
      ondragend: vi.fn(),
      ondragover: vi.fn(),
      ondrop: vi.fn(),
      onkeydown: vi.fn()
    }
  });
}

describe('Document explorer item', () => {
  it('keeps a single roving tab stop inside each explorer item', () => {
    const { container } = renderItem();
    expect(container.querySelector('.explorer-item-main')).toHaveAttribute('tabindex', '0');
    expect(container.querySelector('.kebab')).toHaveAttribute('tabindex', '-1');
  });
  it('does not bubble drops over files to the explorer root', async () => {
    const { container } = renderItem();
    const item = container.querySelector('.explorer-item')!;
    let bubbled = false;
    container.addEventListener('drop', () => (bubbled = true));
    container.addEventListener('dragover', () => (bubbled = true));

    await fireEvent.dragOver(item, { dataTransfer: { dropEffect: 'move' } });
    await fireEvent.drop(item, { dataTransfer: { dropEffect: 'move' } });

    expect(bubbled).toBe(false);
  });

  it('keeps grid tiles to artwork and name only', () => {
    const { container } = renderItem(vi.fn(), true);

    expect(container.querySelector('.tile-artwork')).toBeInTheDocument();
    expect(container.querySelector('.entry-name')).toHaveTextContent('manual.pdf');
    expect(container.querySelector('.entry-metadata')).not.toBeInTheDocument();
    expect(container.querySelector('.entry-type')).not.toBeInTheDocument();
    expect(container.querySelector('.entry-updated')).not.toBeInTheDocument();
    expect(container.querySelector('.entry-size')).not.toBeInTheDocument();
  });
});
