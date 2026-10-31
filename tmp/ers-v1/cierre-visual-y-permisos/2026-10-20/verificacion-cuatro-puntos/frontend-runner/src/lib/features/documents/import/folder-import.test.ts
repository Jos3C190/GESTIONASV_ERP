import { describe, expect, it } from 'vitest';
import { buildFolderManifest, formatImportBytes, selectionFromPicker } from './folder-import';

describe('recursive folder import manifest', () => {
  it('preserves the selected root and synthesizes parent folders', () => {
    const selection = selectionFromPicker([
      Object.assign(new File(['pdf'], 'contrato.pdf', { type: 'application/pdf' }), { webkitRelativePath: 'Contratos/2026/contrato.pdf' })
    ]);
    const result = buildFolderManifest(selection);

    expect(selection.rootName).toBe('Contratos');
    expect(result.manifest.map((item) => item.relative_path)).toEqual([
      'Contratos',
      'Contratos/2026',
      'Contratos/2026/contrato.pdf'
    ]);
    expect(result.validFiles).toHaveLength(1);
  });

  it('keeps empty folders and reports unsupported files without uploading them', () => {
    const selection = {
      rootName: 'Empresa',
      folders: ['Empresa', 'Empresa/Vacía'],
      files: [{ file: new File([''], 'malware.exe'), relativePath: 'Empresa/malware.exe' }]
    };
    const result = buildFolderManifest(selection);

    expect(result.manifest.map((item) => item.relative_path)).toEqual(['Empresa', 'Empresa/Vacía']);
    expect(result.invalidFiles[0]?.reason).toContain('vacío');
    expect(result.totalBytes).toBe(0);
  });

  it('formats large import sizes for the summary', () => {
    expect(formatImportBytes(1024 * 1024)).toBe('1.0 MB');
    expect(formatImportBytes(1024 * 1024 * 1024)).toBe('1.00 GB');
  });
  it('deduplicates duplicate picker paths and explains size failures', () => {
    const file = Object.assign(new File(['pdf'], 'contrato.pdf', { type: 'application/pdf' }), { webkitRelativePath: 'Contratos/contrato.pdf' });
    const duplicate = Object.assign(new File(['pdf'], 'contrato.pdf', { type: 'application/pdf' }), { webkitRelativePath: 'Contratos/contrato.pdf' });
    const result = buildFolderManifest(selectionFromPicker([file, duplicate]), 2);

    expect(result.validFiles).toHaveLength(0);
    expect(result.invalidFiles[0]?.reason).toContain('Supera');
  });
});
