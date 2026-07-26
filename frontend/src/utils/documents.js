import { API } from "./auth"

/**
 * Downloads a litigation document as an editable DOCX file.
 * Unicode-safe: handles ₹, em-dashes, smart quotes, and all LLM output.
 * @param {{ content: string, case_title: string }} doc
 */
export async function downloadDOCX(doc) {
    try {
        const response = await fetch(`${API}/lawyer/documents/export-docx`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${localStorage.getItem("legal_token")}`
            },
            body: JSON.stringify({ content: doc.content, title: doc.case_title })
        })
        if (!response.ok) throw new Error(`Server error ${response.status}`)
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `${doc.case_title.replace(/\s+/g, "_").replace(/\//g, "-")}.docx`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
    } catch (err) {
        alert("DOCX download failed: " + err.message)
    }
}

/**
 * Downloads a litigation document as a PDF.
 * Uses DejaVu Sans (Unicode-capable) on the backend — handles ₹ and special chars.
 * @param {{ content: string, case_title: string }} doc
 */
export async function downloadPDF(doc) {
    try {
        const response = await fetch(`${API}/lawyer/documents/export-pdf`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${localStorage.getItem("legal_token")}`
            },
            body: JSON.stringify({ content: doc.content, title: doc.case_title })
        })
        if (!response.ok) throw new Error(`Server error ${response.status}`)
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `${doc.case_title.replace(/\s+/g, "_").replace(/\//g, "-")}.pdf`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
    } catch (err) {
        alert("PDF download failed: " + err.message)
    }
}
