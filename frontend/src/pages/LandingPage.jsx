import { useNavigate, Link } from "react-router-dom"
import { isAuthenticated, isLawyer } from "../utils/auth"

const CITIZEN_FEATURES = [
    { icon: "💬", title: "Legal Q&A Chatbot", desc: "Ask anything about IPC, Constitution, RTI, Consumer Protection in plain English" },
    { icon: "📄", title: "Document Generator", desc: "Generate Police Complaints, RTI Applications, Consumer Complaints instantly" },
    { icon: "📚", title: "Legal Guides", desc: "Know your rights when arrested, what to do in cyber fraud cases" },
    { icon: "🕐", title: "History & Drafts", desc: "All your conversations and generated documents saved securely" },
]

const LAWYER_FEATURES = [
    { icon: "🔍", title: "Case Similarity Search", desc: "Find Supreme Court judgments most similar to your current case" },
    { icon: "🧠", title: "AI Litigation Strategy", desc: "Get LLaMA-powered strategy based on real SC precedents" },
    { icon: "📊", title: "100 SC Judgments Indexed", desc: "Criminal cases from 2000–present, all searchable via FAISS" },
    { icon: "💾", title: "Search History", desc: "Review past similarity searches and strategies" },
]

export default function LandingPage() {
    const navigate = useNavigate()
    const loggedIn = isAuthenticated()
    const lawyer = isLawyer()

    return (
        <div className="min-h-screen bg-bg">

            {/* ── Nav ─────────────────────────────────────── */}
            <nav className="border-b border-border px-6 py-4 flex items-center justify-between max-w-7xl mx-auto">
                <div className="flex items-center gap-2">
                    <span className="text-2xl">⚖️</span>
                    <span className="font-bold text-white text-lg tracking-tight">NyayaMitra</span>
                </div>
                <div className="flex items-center gap-3">
                    {loggedIn ? (
                        <button
                            onClick={() => navigate(lawyer ? "/lawyer" : "/citizen")}
                            className="btn-primary text-sm py-2 px-5"
                        >
                            Dashboard →
                        </button>
                    ) : (
                        <>
                            <Link to="/login" className="btn-ghost text-sm py-2">Sign in</Link>
                            <Link to="/register" className="btn-primary text-sm py-2 px-5">Get started</Link>
                        </>
                    )}
                </div>
            </nav>

            {/* ── Hero ─────────────────────────────────────── */}
            <section className="bg-hero-gradient text-center pt-24 pb-20 px-6">
                <div className="inline-block bg-primary/15 border border-primary/30 text-primary text-xs font-semibold px-4 py-1.5 rounded-full mb-6">
                    🇮🇳 Built for Indian Law
                </div>
                <h1 className="text-5xl md:text-6xl font-black text-white mb-6 leading-tight">
                    Your AI<br />
                    <span className="gradient-text">NyayaMitra</span>
                </h1>
                <p className="text-gray-400 text-lg max-w-2xl mx-auto mb-10">
                    Citizens get instant legal answers. Lawyers find Supreme Court precedents.
                    All powered by RAG, FAISS and Groq LLaMA.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                    <button
                        onClick={() => navigate("/register?role=citizen")}
                        className="btn-primary text-base px-8 py-3.5"
                    >
                        👤 I'm a Citizen
                    </button>
                    <button
                        onClick={() => navigate("/register?role=lawyer")}
                        className="btn-gold text-base px-8 py-3.5"
                    >
                        👨‍⚖️ I'm a Lawyer
                    </button>
                </div>
            </section>

            {/* ── Stats ────────────────────────────────────── */}
            <section className="border-y border-border py-10 px-6">
                <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
                    {[
                        { value: "5", label: "Indian Laws Indexed" },
                        { value: "100", label: "SC Judgments" },
                        { value: "3", label: "Document Types" },
                        { value: "Free", label: "Local Embeddings" },
                    ].map(s => (
                        <div key={s.label}>
                            <div className="text-3xl font-black gradient-text">{s.value}</div>
                            <div className="text-gray-500 text-sm mt-1">{s.label}</div>
                        </div>
                    ))}
                </div>
            </section>

            {/* ── Citizen Features ─────────────────────────── */}
            <section className="py-20 px-6 max-w-7xl mx-auto">
                <div className="text-center mb-12">
                    <div className="badge-citizen inline-block mb-4">For Citizens</div>
                    <h2 className="text-3xl font-bold text-white">Understand your legal rights</h2>
                    <p className="text-gray-400 mt-2">No legal jargon. Plain English answers from IPC, Constitution, RTI & more.</p>
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
                    {CITIZEN_FEATURES.map(f => (
                        <div key={f.title} className="card-hover p-6">
                            <div className="text-3xl mb-4">{f.icon}</div>
                            <h3 className="text-white font-semibold mb-2">{f.title}</h3>
                            <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* ── Lawyer Features ──────────────────────────── */}
            <section className="py-20 px-6 max-w-7xl mx-auto border-t border-border">
                <div className="text-center mb-12 bg-gold-gradient">
                    <div className="badge-lawyer inline-block mb-4">For Lawyers</div>
                    <h2 className="text-3xl font-bold text-white">AI-Powered Case Research</h2>
                    <p className="text-gray-400 mt-2">Find similar Supreme Court judgments instantly with FAISS vector search.</p>
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
                    {LAWYER_FEATURES.map(f => (
                        <div key={f.title} className="card-gold p-6">
                            <div className="text-3xl mb-4">{f.icon}</div>
                            <h3 className="text-white font-semibold mb-2">{f.title}</h3>
                            <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* ── CTA ──────────────────────────────────────── */}
            <section className="py-20 px-6 text-center border-t border-border bg-hero-gradient">
                <h2 className="text-3xl font-bold text-white mb-4">Get started for free</h2>
                <p className="text-gray-400 mb-8">No credit card. No legal fees. Just answers.</p>
                <Link to="/register" className="btn-primary text-base px-10 py-4 inline-block">
                    Create free account →
                </Link>
            </section>

            {/* ── Footer ───────────────────────────────────── */}
            <footer className="border-t border-border py-8 text-center text-gray-600 text-sm">
                ⚖️ NyayaMitra · Built with FastAPI, FAISS, Groq LLaMA
                <span className="mx-2">·</span>
                <span className="text-xs">*Not a substitute for professional legal advice*</span>
            </footer>
        </div>
    )
}
