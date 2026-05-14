import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { confirmPayment, getMe, getSubscriptionInfo, getTariffs, initiatePayment } from '../api'
import type { SubscriptionInfo, Tariffs, User } from '../types'

type DeviceLimit = 1 | 2 | 3
type Plan = 1 | 3 | 6 | 12

const DEVICES: DeviceLimit[] = [1, 2, 3]
const PLANS: { months: Plan; label: string; discount?: string }[] = [
  { months: 1,  label: '1 месяц' },
  { months: 3,  label: '3 месяца',  discount: '−10%' },
  { months: 6,  label: '6 месяцев', discount: '−15%' },
  { months: 12, label: '1 год',     discount: '−20%' },
]

const LABEL: React.CSSProperties = {
  fontFamily: 'JetBrains Mono', fontSize: '0.6rem',
  letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '12px',
}
const SECTION: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)',
  borderLeft: '2px solid var(--white)', padding: '20px 24px',
}

export default function PaymentPage() {
  const navigate = useNavigate()
  const [tariffs, setTariffs] = useState<Tariffs | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [sub, setSub] = useState<SubscriptionInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [deviceLimit, setDeviceLimit] = useState<DeviceLimit>(1)
  const [plan, setPlan] = useState<Plan>(1)
  const [paying, setPaying] = useState(false)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    Promise.all([
      getTariffs().then(r => r.data),
      getMe().then(r => r.data),
      getSubscriptionInfo().then(r => r.data).catch(() => null),
    ])
      .then(([t, u, s]) => { setTariffs(t); setUser(u); setSub(s) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (!tariffs || !user) return <p className="hint-text">Не удалось загрузить тарифы.</p>

  const price = tariffs[String(deviceLimit)]?.[String(plan)] ?? 0
  const balanceUsed = Math.min(user.balance, price)
  const finalAmount = price - balanceUsed
  const hasActive = sub?.end_date !== null && sub?.end_date !== undefined
    && new Date(sub.end_date).getTime() > Date.now()
  const action = hasActive ? 'renew' : 'new'

  async function handlePay() {
    if (paying) return
    setPaying(true)
    try {
      const { data } = await initiatePayment(action, plan, deviceLimit)
      if (data.final_amount > 0 && data.payment_url) {
        window.open(data.payment_url, '_blank')
        navigate(`/payment/polling?pending_id=${data.pending_id}`)
      } else {
        await confirmPayment(data.pending_id)
        setSuccess(true)
      }
    } catch {
      alert('Ошибка при создании платежа.')
    } finally {
      setPaying(false)
    }
  }

  if (success) {
    return (
      <div style={{ textAlign: 'center', paddingTop: '60px' }} className="fade-in-up">
        <h2 style={{ fontFamily: 'Cormorant Garamond', fontSize: '2.5rem', fontWeight: 300, marginBottom: '8px' }}>
          Активировано ⚡
        </h2>
        <p className="hint-text" style={{ marginBottom: '28px' }}>Подписка активирована</p>
        <button className="btn-primary" onClick={() => navigate('/dashboard')}>В кабинет →</button>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '560px' }}>

      {/* Step 1: Devices */}
      <div style={SECTION}>
        <p style={LABEL}>Шаг 1 — Устройства</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1px', background: 'var(--dim)' }}>
          {DEVICES.map(d => (
            <button key={d} onClick={() => setDeviceLimit(d)} style={{
              padding: '12px',
              background: deviceLimit === d ? 'var(--white)' : 'var(--surface)',
              color: deviceLimit === d ? 'var(--black)' : 'var(--muted)',
              border: 'none', cursor: 'pointer',
              fontFamily: 'JetBrains Mono', fontSize: '0.64rem',
              letterSpacing: '0.12em', textTransform: 'uppercase',
              fontWeight: deviceLimit === d ? 700 : 400,
              transition: 'background 0.15s, color 0.15s',
            }}>
              {d} {d === 1 ? 'устройство' : 'устройства'}
            </button>
          ))}
        </div>
      </div>

      {/* Step 2: Period */}
      <div style={SECTION}>
        <p style={LABEL}>Шаг 2 — Период</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', background: 'var(--dim)' }}>
          {PLANS.map(({ months, label, discount }) => {
            const cellPrice = tariffs[String(deviceLimit)]?.[String(months)] ?? 0
            const selected = plan === months
            return (
              <button key={months} onClick={() => setPlan(months)} style={{
                padding: '16px', background: selected ? 'var(--white)' : 'var(--surface)',
                border: 'none', cursor: 'pointer', textAlign: 'left', transition: 'background 0.15s',
              }}>
                <div style={{
                  fontFamily: 'JetBrains Mono', fontSize: '0.58rem', letterSpacing: '0.12em',
                  textTransform: 'uppercase', color: selected ? 'rgba(0,0,0,0.5)' : 'var(--muted)', marginBottom: '6px',
                }}>
                  {label}{discount && <span style={{ marginLeft: '6px', opacity: 0.7 }}>{discount}</span>}
                </div>
                <div style={{
                  fontFamily: 'Cormorant Garamond', fontSize: '1.5rem', fontWeight: 600, lineHeight: 1,
                  color: selected ? 'var(--black)' : 'var(--white)',
                }}>
                  {cellPrice} ₽
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Summary */}
      <div style={{ ...SECTION, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
        <div>
          <p style={LABEL}>Итого</p>
          <p style={{ fontFamily: 'Cormorant Garamond', fontSize: '2rem', fontWeight: 600, color: 'var(--white)', lineHeight: 1 }}>
            {price} ₽
          </p>
          {balanceUsed > 0 && (
            <p style={{ fontFamily: 'JetBrains Mono', fontSize: '0.7rem', color: 'var(--muted)', marginTop: '6px' }}>
              Баланс −{balanceUsed} ₽ → к оплате{' '}
              <span style={{ color: 'var(--white)' }}>{finalAmount} ₽</span>
            </p>
          )}
        </div>
        <button
          className="btn-primary"
          onClick={handlePay}
          disabled={paying}
          style={{ flexShrink: 0 }}
        >
          {paying
            ? <span className="loader" style={{ width: '12px', height: '12px' }} />
            : finalAmount === 0 ? 'Активировать' : 'Оплатить →'}
        </button>
      </div>
    </div>
  )
}

function Spinner() {
  return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '80px' }}>
    <div className="loader" style={{ width: '28px', height: '28px' }} />
  </div>
}
