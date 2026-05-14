import { QRCodeSVG } from 'qrcode.react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMe, getReferral, getSubscriptionInfo } from '../api'
import type { Referral, SubscriptionInfo, User } from '../types'

const LABEL: React.CSSProperties = {
  fontFamily: 'JetBrains Mono', fontSize: '0.6rem',
  letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--muted)',
}
const BLOCK: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)',
  borderLeft: '2px solid var(--white)', padding: '24px 28px',
}

function daysWord(n: number) {
  if (n % 10 === 1 && n % 100 !== 11) return 'день'
  if ([2,3,4].includes(n % 10) && ![12,13,14].includes(n % 100)) return 'дня'
  return 'дней'
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [sub, setSub] = useState<SubscriptionInfo | null>(null)
  const [ref, setRef] = useState<Referral | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [qrVisible, setQrVisible] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    Promise.all([
      getMe().then(r => r.data),
      getSubscriptionInfo().then(r => r.data).catch(() => null),
      getReferral().then(r => r.data).catch(() => null),
    ])
      .then(([u, s, r]) => { setUser(u); setSub(s); setRef(r) })
      .catch(() => setError('Не удалось загрузить данные.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (error || !user) return <p className="hint-text">{error ?? 'Ошибка загрузки'}</p>

  const endDate = sub?.end_date ? new Date(sub.end_date) : null
  const daysLeft = endDate ? Math.max(0, Math.ceil((endDate.getTime() - Date.now()) / 86_400_000)) : 0
  const hasActive = endDate !== null && daysLeft > 0

  // Progress bar assumes 30-day reference period
  const progressPct = hasActive ? Math.min(100, Math.round((daysLeft / 30) * 100)) : 0

  async function copyUrl() {
    if (!sub?.subscription_url) return
    await navigator.clipboard.writeText(sub.subscription_url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* Status block */}
      {hasActive && endDate && sub ? (
        <div className="fade-in-up" style={BLOCK}>
          <p style={{ ...LABEL, marginBottom: '0' }}>
            {daysLeft <= 7 ? '⚠ Подписка истекает' : '● Подписка активна'}
          </p>
          <div style={{ textAlign: 'center', padding: '20px 0 16px' }}>
            <div style={{ fontFamily: 'Cormorant Garamond', fontSize: '72px', fontWeight: 600, color: 'var(--white)', lineHeight: 1 }}>
              {daysLeft}
            </div>
            <div style={{ ...LABEL, textAlign: 'center', marginTop: '6px', marginBottom: 0 }}>
              {daysWord(daysLeft)} осталось
            </div>
          </div>
          <div style={{ background: 'var(--surface-2)', height: '3px', width: '100%', marginBottom: '8px' }}>
            <div style={{ background: 'var(--white)', height: '3px', width: `${progressPct}%`, transition: 'width 0.6s ease' }} />
          </div>
          <p style={{ ...LABEL, textAlign: 'right', marginBottom: 0 }}>
            до {endDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
          {daysLeft <= 7 && (
            <button className="btn-primary" style={{ width: '100%', marginTop: '16px' }} onClick={() => navigate('/payment')}>
              Продлить →
            </button>
          )}
        </div>
      ) : (
        <div className="fade-in-up" style={{ ...BLOCK, textAlign: 'center', padding: '48px 28px' }}>
          <h2 style={{ fontFamily: 'Cormorant Garamond', fontSize: '1.8rem', fontWeight: 300, marginBottom: '10px' }}>
            Нет активной подписки
          </h2>
          <p style={{ ...LABEL, textAlign: 'center', marginBottom: '28px' }}>Подключите VPN чтобы начать</p>
          <button className="btn-primary" onClick={() => navigate('/payment')}>
            Выбрать план →
          </button>
        </div>
      )}

      {/* Metrics row */}
      <div className="fade-in-up fade-in-up-1"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1px', background: 'var(--dim)' }}>
        {[
          { label: 'Устройств', value: sub?.device_limit ?? '—' },
          { label: 'Баланс',    value: `${user.balance} ₽` },
          { label: 'Рефералов', value: ref?.invited_count ?? 0 },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: 'var(--surface)', padding: '16px', textAlign: 'center' }}>
            <p style={{ ...LABEL, textAlign: 'center', marginBottom: '6px' }}>{label}</p>
            <p style={{ fontFamily: 'Cormorant Garamond', fontSize: '1.6rem', fontWeight: 600, color: 'var(--white)', lineHeight: 1 }}>
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Subscription URL + QR */}
      {hasActive && sub?.subscription_url && (
        <div className="fade-in-up fade-in-up-2" style={BLOCK}>
          <p style={{ ...LABEL, marginBottom: '12px' }}>Ссылка подписки</p>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <input className="input" readOnly value={sub.subscription_url}
              style={{ fontSize: '0.68rem', flex: 1 }} onFocus={e => e.target.select()} />
            <button className="btn-ghost" style={{ padding: '0 14px', flexShrink: 0, fontSize: '0.62rem' }} onClick={copyUrl}>
              {copied ? '✓' : 'Копировать'}
            </button>
          </div>

          <button className="btn-ghost"
            style={{ padding: '7px 14px', fontSize: '0.6rem', marginBottom: qrVisible ? '16px' : 0 }}
            onClick={() => setQrVisible(v => !v)}>
            {qrVisible ? 'Скрыть QR' : 'Показать QR'}
          </button>

          {qrVisible && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px', paddingTop: '4px' }}>
              <div style={{ background: 'var(--black)', padding: '12px', border: '1px solid var(--border)' }}>
                <QRCodeSVG value={sub.subscription_url} size={180} bgColor="#000000" fgColor="#FFFFFF" level="M" />
              </div>
              <div style={{ width: '100%', maxWidth: '320px' }}>
                <p style={{ ...LABEL, marginBottom: '10px' }}>Как подключить</p>
                {[
                  'Скопируйте ссылку или отсканируйте QR',
                  'Откройте Hiddify, NekoBox или v2rayNG',
                  'Нажмите «Добавить подписку» → вставьте ссылку',
                ].map((step, i) => (
                  <p key={i} style={{ fontFamily: 'JetBrains Mono', fontSize: '0.7rem', color: 'var(--muted)', lineHeight: 1.6, marginBottom: '4px' }}>
                    <span style={{ color: 'var(--white)', fontWeight: 700, marginRight: '8px' }}>{i + 1}.</span>
                    {step}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '80px' }}>
    <div className="loader" style={{ width: '28px', height: '28px' }} />
  </div>
}
