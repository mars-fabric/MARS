import { getApiUrl } from './config'

/**
 * Fetch wrapper with automatic retry for transient network errors
 * (e.g. ECONNRESET / socket hang up through the Next.js proxy).
 *
 * Only retries on *network* failures (TypeError from fetch); HTTP error
 * responses (4xx/5xx) are returned as-is for the caller to handle.
 */
export async function apiFetchWithRetry(
  path: string,
  options?: RequestInit,
  retries = 1,
): Promise<Response> {
  const url = getApiUrl(path)
  const init: RequestInit = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  }
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fetch(url, init)
    } catch (err) {
      // Only retry on network-level errors (ECONNRESET surfaces as TypeError)
      if (attempt < retries && err instanceof TypeError) {
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)))
        continue
      }
      throw err
    }
  }
  // Unreachable, but satisfies TS
  throw new Error('Fetch failed after retries')
}
