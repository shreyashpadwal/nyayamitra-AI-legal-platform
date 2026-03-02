import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { getUsername, clearSession } from "../utils/auth"
import ChatHistory from "../components/ChatHistory"
import DocumentGenerator from "../components/DocumentGenerator"
import SavedDrafts from "../components/SavedDrafts"
import LegalGuides from "../components/LegalGuides"

const NAV = [
    { key: "chat", icon: "💬", label: "Chat Assistant" },
    { key: "history", icon: "🕐", label: "Chat History" },
    { key: "documents", icon: "📄", label: "Document Generator" },
    { key: "drafts", icon: "💾", label: "Saved Drafts" },
    { key: "guides", icon: "📚", label: "Legal Guides" },
]

export default function CitizenDashboard() {
    const [tab, setTab] = useState("chat")
    const [sidebarOpen, setSidebarOpen] = useState(true)
    const navigate = useNavigate()
    const username = getUsername()

    const handleLogout = () => { clearSession(); navigate("/login") }

    const renderContent = () => {
        switch (tab) {
            case "chat":
                return (
                    <div className="flex flex-col items-center justify-center h-full text-center py-20">
                        <div className="text-7xl mb-6">⚖️</div>
                        <h2 className="text-2xl font-bold text-white mb-3">Indian Legal AI Assistant</h2>
                        <p className="text-gray-400 mb-8 max-w-md">
                            Ask any question about Indian law — IPC, RTI, Constitution, Consumer Protection Act, CrPC
                        </p>
                        <button onClick={() => navigate("/chat")} className="btn-primary px-8 py-3.5 text-base">
                            Open Chat Assistant →
                        </button>
                        <div className="mt-10 grid grid-cols-2 gap-3 max-w-lg w-full">
                            {[
                                "What are my rights if police arrest me?",
                                "How do I file an RTI application?",
                                "What is punishment for theft in IPC?",
                                "What to do if a product is defective?",
                            ].map(q => (
                                <button
                                    key={q}
                                    onClick={() => navigate("/chat", { state: { question: q } })}
                                    className="text-left bg-surfaceLight border border-border hover:border-primary/40 rounded-xl p-3 text-sm text-gray-400 hover:text-white transition-all duration-200"
                                >
                                    {q}
                                </button>
                            ))}
                        </div>
                    </div>
                )
            case "history": return <ChatHistory />
            case "documents": return <DocumentGenerator />
            case "drafts": return <SavedDrafts />
            case "guides": return <LegalGuides />
            default: return null
        }
    }

    return (
        <div className="flex h-screen bg-bg overflow-hidden">
            {/* ── Sidebar ──────────────────── */}
            <aside className={`transition-all duration-300 ${sidebarOpen ? "w-64" : "w-0"} bg-surface border-r border-border flex flex-col overflow-hidden flex-shrink-0`}>
                {/* Logo */}
                <div className="px-6 py-5 border-b border-border flex-shrink-0">
                    <div className="flex items-center gap-2">
                        <span className="text-2xl">⚖️</span>
                        <span className="text-primary font-bold text-lg tracking-tight">NyayaMitra</span>
                    </div>
                    <span className="badge-citizen mt-2 inline-block">Citizen</span>
                </div>

                {/* Nav */}
                <nav className="flex-1 py-4 space-y-1 overflow-y-auto">
                    {NAV.map(item => (
                        <button
                            key={item.key}
                            onClick={() => { setTab(item.key); if (window.innerWidth < 768) setSidebarOpen(false) }}
                            className={tab === item.key ? "nav-item-active-citizen" : "nav-item"}
                        >
                            <span>{item.icon}</span>
                            {item.label}
                        </button>
                    ))}
                </nav>

                {/* Logout */}
                <div className="p-4 border-t border-border flex-shrink-0">
                    <button onClick={handleLogout} className="btn-danger w-full text-sm py-2.5">
                        🚪 Logout
                    </button>
                </div>
            </aside>

            {/* ── Main ─────────────────────── */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Header */}
                <header className="bg-surface border-b border-border px-6 py-4 flex justify-between items-center flex-shrink-0">
                    <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-gray-400 hover:text-white text-xl transition-colors">
                        ☰
                    </button>
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-gradient-to-r from-primary to-accent rounded-full flex items-center justify-center text-white font-bold text-sm shadow-glow">
                            {username?.charAt(0).toUpperCase()}
                        </div>
                        <span className="text-white font-medium text-sm">{username}</span>
                    </div>
                </header>

                {/* Content */}
                <main className="flex-1 overflow-y-auto p-8">
                    {renderContent()}
                </main>
            </div>
        </div>
    )
}
