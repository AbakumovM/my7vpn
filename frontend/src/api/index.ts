import api from './client'
import type {
  User, SubscriptionInfo, Tariffs, PendingPayment,
  PaymentStatus, PaymentHistoryItem, Referral,
} from '../types'

// ── Auth ──────────────────────────────────────────────────────────────
export const requestOtp = (email: string) =>
  api.post('/auth/otp/request', { email })

export const verifyOtp = (email: string, code: string) =>
  api.post<{ access_token: string; user_id: number }>('/auth/otp/verify', { email, code })

export const verifyBotToken = (token: string) =>
  api.get<{ access_token: string; user_id: number }>(`/auth/bot-token/${token}`)

export const logout = () =>
  api.post('/auth/logout')

export const getAuthMe = () =>
  api.get<{ user_id: number }>('/auth/me')

// ── User ──────────────────────────────────────────────────────────────
export const getMe = () =>
  api.get<User>('/users/me')

export const getReferral = () =>
  api.get<Referral>('/users/referral')

// ── Tariffs ───────────────────────────────────────────────────────────
export const getTariffs = () =>
  api.get<Tariffs>('/tariffs')

// ── Payments ──────────────────────────────────────────────────────────
export const initiatePayment = (action: string, plan: number, device_limit: number) =>
  api.post<PendingPayment>('/payments/initiate', { action, plan, device_limit })

export const confirmPayment = (pendingId: number) =>
  api.post<{ subscription_url: string | null; end_date: string }>(`/payments/${pendingId}/confirm`)

export const getPaymentStatus = (pendingId: number) =>
  api.get<PaymentStatus>(`/payments/${pendingId}/status`)

export const getPaymentHistory = () =>
  api.get<PaymentHistoryItem[]>('/payments/history')

// ── Subscription ─────────────────────────────────────────────────────
export const getSubscriptionInfo = () =>
  api.get<SubscriptionInfo | null>('/devices/subscription')
