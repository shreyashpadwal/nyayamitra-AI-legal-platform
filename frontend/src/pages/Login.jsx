import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { API, setSession } from "../utils/auth"

export default function Login() {
    const [form, setForm] = useState({ email: "", password: "" })
    const [error, setError] = useState("")
    const [loading, setLoading] = useState(false)
    const navigate = useNavigate()

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError("")
        setLoading(true)
        try {
            const res = await fetch(`${API}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(form)
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || "Login failed")

            setSession(data.access_token, data.username, data.role)
            navigate(data.role === "lawyer" ? "/lawyer" : "/citizen")
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-bg flex items-center justify-center px-4 bg-hero-gradient">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-10">
                    <div className="text-5xl mb-3">⚖️</div>
                    <h1 className="text-2xl font-bold text-white">Welcome back</h1>
                    <p className="text-gray-400 mt-1 text-sm">Sign in to your legal account</p>
                </div>

                {/* Card */}
                <div className="card p-8">
                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">Email address</label>
                            <input
                                type="email"
                                value={form.email}
                                onChange={e => setForm({ ...form, email: e.target.value })}
                                placeholder="you@example.com"
                                required
                                className="input"
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
                                className="input"
                            />
                        </div>

                        {error && (
                            <div className="bg-red-500/10 border border-red-400/30 rounded-xl px-4 py-3 text-red-400 text-sm">
                                {error}
                            </div>
                        )}

                        <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2">
                            {loading ? <><div className="spinner" /> Signing in...</> : "Sign in →"}
                        </button>
                    </form>
                </div>

                <p className="text-center text-gray-500 text-sm mt-6">
                    Don't have an account?{" "}
                    <Link to="/register" className="text-primary hover:text-accent transition-colors">
                        Create one
                    </Link>
                </p>
                <p className="text-center mt-3">
                    <Link to="/" className="text-gray-600 hover:text-gray-400 text-xs transition-colors">
                        ← Back to home
                    </Link>
                </p>
            </div>
        </div>
    )
}
