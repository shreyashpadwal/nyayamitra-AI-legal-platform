import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { API, setSession } from "../utils/auth"

const ROLES = [
    { key: "citizen", icon: "👤", label: "Citizen", desc: "Legal Q&A, document drafting" },
    { key: "lawyer", icon: "👨‍⚖️", label: "Lawyer", desc: "Case similarity search, SC judgments" },
]

export default function Register() {
    const [form, setForm] = useState({ username: "", email: "", password: "", role: "citizen" })
    const [error, setError] = useState("")
    const [loading, setLoading] = useState(false)
    const navigate = useNavigate()

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError("")
        setLoading(true)
        try {
            const res = await fetch(`${API}/auth/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(form)
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || "Registration failed")

            // Auto-login
            const loginRes = await fetch(`${API}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: form.email, password: form.password })
            })
            const loginData = await loginRes.json()
            if (!loginRes.ok) throw new Error(loginData.detail || "Login failed")

            setSession(loginData.access_token, loginData.username, loginData.role)
            navigate(loginData.role === "lawyer" ? "/lawyer" : "/citizen")
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-bg flex items-center justify-center px-4 bg-hero-gradient">
            <div className="w-full max-w-md">
                <div className="text-center mb-10">
                    <div className="text-5xl mb-3">⚖️</div>
                    <h1 className="text-2xl font-bold text-white">Create your account</h1>
                    <p className="text-gray-400 mt-1 text-sm">Join the AI Legal Platform</p>
                </div>

                <div className="card p-8">
                    <form onSubmit={handleSubmit} className="space-y-5">

                        {/* Role selector */}
                        <div>
                            <label className="block text-sm text-gray-400 mb-3">I am a...</label>
                            <div className="grid grid-cols-2 gap-3">
                                {ROLES.map(r => (
                                    <button
                                        key={r.key}
                                        type="button"
                                        onClick={() => setForm({ ...form, role: r.key })}
                                        className={`p-4 rounded-xl border text-left transition-all duration-200
                      ${form.role === r.key
                                                ? r.key === "lawyer"
                                                    ? "border-gold/50 bg-gold/10"
                                                    : "border-primary/50 bg-primary/10"
                                                : "border-border hover:border-gray-600"
                                            }`}
                                    >
                                        <div className="text-2xl mb-1">{r.icon}</div>
                                        <div className="text-white font-semibold text-sm">{r.label}</div>
                                        <div className="text-gray-500 text-xs mt-0.5">{r.desc}</div>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Username</label>
                            <input
                                type="text"
                                value={form.username}
                                onChange={e => setForm({ ...form, username: e.target.value })}
                                placeholder="legaluser123"
                                required
                                className={form.role === "lawyer" ? "input-gold" : "input"}
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Email address</label>
                            <input
                                type="email"
                                value={form.email}
                                onChange={e => setForm({ ...form, email: e.target.value })}
                                placeholder="you@example.com"
                                required
                                className={form.role === "lawyer" ? "input-gold" : "input"}
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Password</label>
                            <input
                                type="password"
                                value={form.password}
                                onChange={e => setForm({ ...form, password: e.target.value })}
                                placeholder="••••••••"
                                required
                                minLength={6}
                                className={form.role === "lawyer" ? "input-gold" : "input"}
                            />
                        </div>

                        {error && (
                            <div className="bg-red-500/10 border border-red-400/30 rounded-xl px-4 py-3 text-red-400 text-sm">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            className={`w-full flex items-center justify-center gap-2
                ${form.role === "lawyer" ? "btn-gold" : "btn-primary"}`}
                        >
                            {loading ? <><div className={form.role === "lawyer" ? "spinner-gold" : "spinner"} /> Creating account...</> : "Create account →"}
                        </button>
                    </form>
                </div>

                <p className="text-center text-gray-500 text-sm mt-6">
                    Already have an account?{" "}
                    <Link to="/login" className="text-primary hover:text-accent transition-colors">Sign in</Link>
                </p>
            </div>
        </div>
    )
}
