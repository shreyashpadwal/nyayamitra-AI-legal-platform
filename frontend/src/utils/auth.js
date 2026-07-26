// ── Token & Session ─────────────────────────
const TOKEN_KEY = "legal_token"
const USERNAME_KEY = "legal_username"
const ROLE_KEY = "legal_role"

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const getUsername = () => localStorage.getItem(USERNAME_KEY)
export const getRole = () => localStorage.getItem(ROLE_KEY)

export const setSession = (token, username, role) => {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USERNAME_KEY, username)
    localStorage.setItem(ROLE_KEY, role)
}

export const clearSession = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(ROLE_KEY)
}

export const isAuthenticated = () => {
    const token = getToken()
    if (!token) return false
    try {
        const payload = JSON.parse(atob(token.split(".")[1]))
        return payload.exp * 1000 > Date.now()
    } catch {
        return false
    }
}

export const isLawyer = () => getRole() === "lawyer"

// ── Fetch helpers ────────────────────────────
// ── API Base URL ─────────────────────────────
// Set VITE_API_URL in Vercel project settings (Environment Variables) to your
// Hugging Face Space URL, e.g.:  https://your-username-nyayamitra.hf.space
// Falls back to localhost for local development.
export const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

export const API = `${BASE_URL}/api`

export const authHeaders = () => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`
})

export const apiGet = async (path) => {
    const res = await fetch(`${API}${path}`, { headers: authHeaders() })
    if (!res.ok) throw new Error((await res.json()).detail || "Request failed")
    return res.json()
}

export const apiPost = async (path, body) => {
    const res = await fetch(`${API}${path}`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(body)
    })
    if (!res.ok) throw new Error((await res.json()).detail || "Request failed")
    return res.json()
}

export const apiDelete = async (path) => {
    const res = await fetch(`${API}${path}`, { method: "DELETE", headers: authHeaders() })
    if (!res.ok) {
        // Use text() fallback so a non-JSON error body doesn't throw a second time
        const text = await res.text()
        let detail = text
        try { detail = JSON.parse(text).detail || text } catch {}
        throw new Error(detail || "Request failed")
    }
    // 204 No Content has no body — attempting .json() throws "Unexpected end of JSON input"
    if (res.status === 204 || res.headers.get("content-length") === "0") return null
    return res.json()
}
