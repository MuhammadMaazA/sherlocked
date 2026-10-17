const prefix = import.meta.env.BASE_URL.replace(/\/$/, "")

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`
  return `${prefix}${normalized}`
}

export function routerBasename(): string {
  return prefix
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === "string") return body.detail
    if (body.detail) return JSON.stringify(body.detail)
  } catch {
    /* response was not JSON */
  }
  return response.statusText || "Request failed"
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  const response = await fetch(apiUrl(path), { ...init, headers })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<T>
}
