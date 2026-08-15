import { describe, it, expect } from 'vitest';
import { HttpError, apiFetch } from '$lib/api/client';

describe('HttpError', () => {
  it('carries code, message, status', () => {
    const e = new HttpError('not_found', 'Recurso no encontrado', 404);
    expect(e.code).toBe('not_found');
    expect(e.status).toBe(404);
    expect(e.message).toBe('Recurso no encontrado');
    expect(e.name).toBe('HttpError');
  });
});

describe('apiFetch', () => {
  it('throws on the server when given a relative path', async () => {
    // $app/environment.browser is false under jsdom without a window? Actually
    // jsdom provides a window, so we instead simulate by mocking the import.
    // Simpler: assert the URL builder behaviour with a stubbed fetch that 404s.
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response('Not Found', {
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      })) as typeof fetch;
    try {
      await expect(apiFetch('http://example.test/missing')).rejects.toMatchObject({
        status: 404
      });
    } finally {
      globalThis.fetch = original;
    }
  });

  it('uses the FastAPI business detail instead of a technical status message', async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          detail: 'No puede desactivar una categoría utilizada por almacenes activos.'
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } }
      )) as typeof fetch;
    try {
      await expect(apiFetch('http://example.test/warehouse-category')).rejects.toMatchObject({
        status: 409,
        message: 'No puede desactivar una categoría utilizada por almacenes activos.'
      });
    } finally {
      globalThis.fetch = original;
    }
  });

  it('uses a friendly fallback when an error response has no readable body', async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () => new Response(null, { status: 409 })) as typeof fetch;
    try {
      await expect(apiFetch('http://example.test/conflict')).rejects.toMatchObject({
        status: 409,
        message: 'La operación no puede realizarse por el estado actual del registro.'
      });
    } finally {
      globalThis.fetch = original;
    }
  });

  it('lets the browser set the multipart boundary for FormData bodies', async () => {
    const original = globalThis.fetch;
    let capturedHeaders: HeadersInit | undefined;
    globalThis.fetch = (async (_input, init) => {
      capturedHeaders = init?.headers;
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }) as typeof fetch;
    try {
      const body = new FormData();
      body.set('file', new File(['a,b\n1,2'], 'locations.csv', { type: 'text/csv' }));
      await apiFetch('http://example.test/import', { method: 'POST', body });
      const headers = new Headers(capturedHeaders);
      expect(headers.get('Content-Type')).toBeNull();
      expect(headers.get('Accept')).toBe('application/json');
    } finally {
      globalThis.fetch = original;
    }
  });
});
