// Direct API client — bypasses Vercel proxy (which has 10s timeout)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://newsletter-says.onrender.com";

export async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  const url = `${API_BASE}${path}`;
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
}
