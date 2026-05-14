import { useEffect, useState } from 'react'
import { getReferral } from '../api'
import type { Referral } from '../types'

const LABEL: React.CSSProperties = {
  fontFamily: 'JetBrains Mono', fontSize: '0.6rem',
  letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '12px',
}
const BLOCK: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)',
  borderLeft: '2px solid var(--white)', padding: '24px 28px',
}

export default function ReferralPage() {
  const [data, setData] = useState<Referral | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    getReferral().then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  async function copyLink() {
    if (!data?.referral_link) return
    await navigator.clipboard.writeText(data.referral_link)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '80px' }}>
      <div className="loader" style={{ width: '28px', height: '28px' }} />
    </div>
  )

  if (!data) return <p className="hint-text">Не удалось загрузить реферальные данные.</p>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '560px' }}>

      <div style={BLOCK} className="fade-in-up">
        <p style={LABEL}>Ваша реферальная ссылка</p>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
          <input className="input" readOnly value={data.referral_link}
            style={{ fontSize: '0.74rem', flex: 1 }} onFocus={e => e.target.select()} />
          <button className="btn-ghost" style={{ padding: '0 14px', flexShrink: 0, fontSize: '0.62rem' }} onClick={copyLink}>
            {copied ? '✓' : 'Копировать'}
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
          <span style={{ fontFamily: 'Cormorant Garamond', fontSize: '2.5rem', fontWeight: 600, color: 'var(--white)', lineHeight: 1 }}>
            {data.invited_count}
          </span>
          <span style={LABEL}>приглашено человек</span>
        </div>
      </div>

      <div style={BLOCK} className="fade-in-up fade-in-up-1">
        <p style={LABEL}>Как это работает</p>
        {[
          'Поделитесь ссылкой с другом',
          'Друг регистрируется и получает бесплатный месяц',
          'Вы получаете 50 ₽ на баланс за каждого приглашённого',
        ].map((text, i) => (
          <div key={i} style={{ display: 'flex', gap: '14px', alignItems: 'flex-start', marginBottom: '12px' }}>
            <span style={{ fontFamily: 'Cormorant Garamond', fontSize: '1.1rem', fontWeight: 600, color: 'var(--white)', flexShrink: 0, width: '18px', textAlign: 'right', lineHeight: 1.4 }}>
              {i + 1}
            </span>
            <p style={{ fontFamily: 'JetBrains Mono', fontSize: '0.72rem', color: 'var(--muted)', lineHeight: 1.6 }}>
              {text}
            </p>
          </div>
        ))}
      </div>

    </div>
  )
}
