import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import HistoryPage from './pages/HistoryPage'
import LoginPage from './pages/LoginPage'
import PaymentPage from './pages/PaymentPage'
import PollingPage from './pages/PollingPage'
import ReferralPage from './pages/ReferralPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/payment/polling" element={<Layout><PollingPage /></Layout>} />
        <Route path="/dashboard"       element={<Layout><DashboardPage /></Layout>} />
        <Route path="/payment"         element={<Layout><PaymentPage /></Layout>} />
        <Route path="/history"         element={<Layout><HistoryPage /></Layout>} />
        <Route path="/referral"        element={<Layout><ReferralPage /></Layout>} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
