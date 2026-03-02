import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { isAuthenticated, isLawyer } from "./utils/auth"

import LandingPage from "./pages/LandingPage"
import Login from "./pages/Login"
import Register from "./pages/Register"
import CitizenDashboard from "./pages/CitizenDashboard"
import LawyerDashboard from "./pages/LawyerDashboard"
import ChatPage from "./pages/ChatPage"

function ProtectedRoute({ children }) {
    return isAuthenticated() ? children : <Navigate to="/login" replace />
}

function LawyerRoute({ children }) {
    if (!isAuthenticated()) return <Navigate to="/login" replace />
    if (!isLawyer()) return <Navigate to="/citizen" replace />
    return children
}

export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                {/* Public */}
                <Route path="/" element={<LandingPage />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />

                {/* Citizen */}
                <Route path="/citizen" element={
                    <ProtectedRoute><CitizenDashboard /></ProtectedRoute>
                } />
                <Route path="/chat" element={
                    <ProtectedRoute><ChatPage /></ProtectedRoute>
                } />

                {/* Lawyer */}
                <Route path="/lawyer" element={
                    <LawyerRoute><LawyerDashboard /></LawyerRoute>
                } />

                {/* Fallback */}
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </BrowserRouter>
    )
}
