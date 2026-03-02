import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { getUsername, clearSession } from "../utils/auth"
import SimilaritySearch from "../components/SimilaritySearch"
import SearchHistory from "../components/SearchHistory"
import CasesBrowser from "../components/CasesBrowser"
import LawyerDocuments from "../components/LawyerDocuments"

const NAV = [
    { key: "search", icon: "🔍", label: "Case Similarity" },
    { key: "history", icon: "📋", label: "Search History" },
    { key: "docs", icon: "📂", label: "Litigation Documents" },
    { key: "cases", icon: "📁", label: "Case Browser" },
]

export default function LawyerDashboard() {
    const [tab, setTab] = useState("search")
    const [sidebarOpen, setSidebar] = useState(true)
    const navigate = useNavigate()
    const username = getUsername()

    const handleLogout = () => { clearSession(); navigate("/login") }

    return (
        <div className="flex h-screen bg-bg overflow-hidden">
            {/* ── Sidebar ──────────── */}
            <aside className={`transition-all duration-300 ${sidebarOpen ? "w-64" : "w-0"} bg-surface border-r border-border flex flex-col overflow-hidden flex-shrink-0`}>
                <div className="px-6 py-5 border-b border-border flex-shrink-0">
                    <div className="flex items-center gap-2">
                        <span className="text-2xl">⚖️</span>
                        <span className="text-gold font-bold text-lg tracking-tight">NyayaMitra</span>
                    </div>
                    <span className="badge-lawyer mt-2 inline-block">Lawyer</span>
                </div>

                <nav className="flex-1 py-4 space-y-1 overflow-y-auto">
                    {NAV.map(item => (
                        <button
                            key={item.key}
                            onClick={() => { setTab(item.key); if (window.innerWidth < 768) setSidebar(false) }}
                            className={tab === item.key ? "nav-item-active-lawyer" : "nav-item"}
                        >
                            <span>{item.icon}</span>
                            {item.label}
                        </button>
                    ))}
                </nav>

                {/* Info box */}
                <div className="mx-4 mb-3 p-3 bg-gold/5 border border-gold/20 rounded-xl text-xs text-gray-400">
                    🧠 100 SC Criminal Judgments indexed via FAISS
                </div>

                <div className="p-4 border-t border-border flex-shrink-0">
                    <button onClick={handleLogout} className="btn-danger w-full text-sm py-2.5">
                        🚪 Logout
                    </button>
                </div>
            </aside>

            {/* ── Main ──────────────── */}
            <div className="flex-1 flex flex-col overflow-hidden">
                <header className="bg-surface border-b border-border px-6 py-4 flex justify-between items-center flex-shrink-0">
                    <button onClick={() => setSidebar(!sidebarOpen)} className="text-gray-400 hover:text-white text-xl transition-colors">☰</button>
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-gradient-to-r from-gold to-goldLight rounded-full flex items-center justify-center text-black font-bold text-sm shadow-goldglow">
                            {username?.charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <div className="text-white font-medium text-sm">{username}</div>
                            <div className="text-gray-500 text-xs">Lawyer Account</div>
                        </div>
                    </div>
                </header>

                <main className="flex-1 overflow-y-auto p-8">
                    {tab === "search" && <SimilaritySearch />}
                    {tab === "history" && <SearchHistory />}
                    {tab === "docs" && <LawyerDocuments />}
                    {tab === "cases" && <CasesBrowser />}
                </main>
            </div>
        </div>
    )
}
