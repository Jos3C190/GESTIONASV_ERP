import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import ProductImagesEditor from './ProductImagesEditor.svelte';
import type { ProductImageDraft } from '$lib/types/catalog';

function gallery(): ProductImageDraft[] {
  return [
    {
      source_type: 'external',
      url: 'https://cdn.example.com/front.webp',
      media_asset_id: null,
      alt_text: 'Frontal',
      position: 0,
      is_cover: true
    },
    {
      source_type: 'external',
      url: 'https://cdn.example.com/back.webp',
      media_asset_id: null,
      alt_text: 'Posterior',
      position: 1,
      is_cover: false
    }
  ];
}

describe('ProductImagesEditor', () => {
  it('permite cambiar portada, ordenar y quitar imágenes', async () => {
    render(ProductImagesEditor, { props: { images: gallery(), companyId: 'company-1' } });

    expect(screen.getByText('2/20 imágenes')).toBeInTheDocument();
    await fireEvent.click(screen.getAllByRole('button', { name: 'Usar como portada' })[1]!);
    expect(screen.getAllByText('Portada')).toHaveLength(1);

    await fireEvent.click(screen.getAllByRole('button', { name: 'Mover arriba' })[1]!);
    await fireEvent.click(screen.getAllByRole('button', { name: 'Eliminar' })[0]!);
    expect(screen.getByText('1/20 imágenes')).toBeInTheDocument();
  });

  it('muestra la galería en modo lectura sin controles de edición', () => {
    render(ProductImagesEditor, {
      props: { images: gallery(), companyId: 'company-1', editable: false }
    });

    expect(screen.queryByRole('button', { name: 'Agregar URL' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Usar como portada' })).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('https://cdn.example.com/front.webp')).toBeDisabled();
  });
});
