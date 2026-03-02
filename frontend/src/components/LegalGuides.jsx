import { useNavigate } from "react-router-dom"

const GUIDES = [
    {
        icon: "🚔",
        title: "Arrest & Police Rights",
        badge: "Know Your Rights",
        color: "border-primary/40 hover:border-primary/60 hover:shadow-glow",
        badgeClass: "badge-citizen",
        points: [
            "You have the right to know the reason for your arrest (Article 22)",
            "You must be produced before a magistrate within 24 hours",
            "You have the right to remain silent — anything you say can be used against you",
            "You have the right to consult a lawyer of your choice",
            "Police cannot hold you for more than 24 hours without magistrate's order",
            "You can apply for bail — most offences are bailable",
            "Torture or third-degree interrogation is illegal (Article 20, 21)",
            "You have the right to inform a family member of your arrest",
        ],
        action: "File a police complaint if rights are violated"
    },
    {
        icon: "💻",
        title: "Cyber Fraud — Act Fast!",
        badge: "Act in 30 Minutes",
        color: "border-gold/40 hover:border-gold/60 hover:shadow-goldglow",
        badgeClass: "badge-lawyer",
        points: [
            "🔴 IMMEDIATELY call the National Cyber Crime Helpline: 1930",
            "Report at cybercrime.gov.in — required for bank reversal",
            "Contact your bank immediately to freeze the transaction",
            "File a complaint at your nearest police station (Cyber Cell)",
            "Collect all evidence: screenshots, emails, transaction IDs, chat logs",
            "Do NOT pay any 'recovery agent' who contacts you — it's a second scam",
            "Cases reported within 30 minutes have the highest recovery rate",
            "Under IT Act 2000 Section 66C/66D — fraud carries 3 years imprisonment",
        ],
        action: "Call 1930 NOW if you're a victim"
    },
    {
        icon: "🛒",
        title: "Consumer Rights",
        badge: "Consumer Protection",
        color: "border-green-400/40 hover:border-green-400/60",
        badgeClass: "badge-green",
        points: [
            "Defective product? File complaint within 2 years of purchase",
            "You can file at District Consumer Forum for claims up to ₹50 Lakhs",
            "State Commission handles ₹50L – ₹2 Crore claims",
            "National Commission handles claims above ₹2 Crore",
            "E-commerce products covered under Consumer Protection Act 2019",
            "You can claim compensation for mental agony and legal costs",
            "RTI can be used to get info about product safety standards",
            "Unfair trade practices and misleading ads are punishable",
        ],
        action: "Use Document Generator to draft your complaint"
    },
]

export default function LegalGuides() {
    const navigate = useNavigate()
    return (
        <div>
            <h2 className="text-xl font-bold text-white mb-2">📚 Legal Guides</h2>
            <p className="text-gray-400 text-sm mb-8">Quick reference guides for common legal situations in India.</p>
            <div className="space-y-6">
                {GUIDES.map(g => (
                    <div key={g.title} className={`card border p-6 transition-all duration-300 ${g.color}`}>
                        <div className="flex items-start gap-4 mb-4">
                            <div className="text-3xl">{g.icon}</div>
                            <div>
                                <span className={`${g.badgeClass} inline-block mb-2`}>{g.badge}</span>
                                <h3 className="text-white font-bold text-lg">{g.title}</h3>
                            </div>
                        </div>
                        <ul className="space-y-2 mb-4">
                            {g.points.map((p, i) => (
                                <li key={i} className="flex gap-2 text-gray-300 text-sm">
                                    <span className="text-primary mt-0.5 flex-shrink-0">→</span>
                                    {p}
                                </li>
                            ))}
                        </ul>
                        <div className="flex items-center gap-3 pt-4 border-t border-border">
                            <span className="text-gray-500 text-xs flex-1">{g.action}</span>
                            <button onClick={() => navigate("/chat")} className="btn-primary text-xs py-2 px-4">
                                Ask AI →
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
