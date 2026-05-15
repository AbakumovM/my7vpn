export interface User {
  user_id: number
  telegram_id: number | null
  balance: number
  referral_code: string | null
}

export interface SubscriptionInfo {
  end_date: string | null
  device_limit: number
  last_payment_amount: number | null
  subscription_url: string | null
}

export interface Tariffs {
  [deviceLimit: string]: {
    [months: string]: number
  }
}

export interface PendingPayment {
  pending_id: number
  amount: number
  balance_used: number
  final_amount: number
  payment_url: string | null
}

export interface PaymentStatus {
  status: 'pending' | 'confirmed' | 'rejected'
  subscription_url: string | null
  end_date: string | null
}

export interface PaymentHistoryItem {
  id: number
  amount: number
  date: string
  plan: number
  device_limit: number
  payment_method: string
  status: string
}

export interface Referral {
  referral_code: string
  referral_link: string
  invited_count: number
}
