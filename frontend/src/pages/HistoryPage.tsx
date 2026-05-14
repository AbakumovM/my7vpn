import { useEffect, useState } from 'react'
import { getPaymentHistory } from '../api'
import type { PaymentHistoryItem } from '../types'

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
function fmtPlan(m: number) { return `${m} мес` }
function fmtMethod(m: string) {
  return ({ yookassa: 'YooKassa', balance: 'Баланс', free: 'Бесплатно' } as Record<string, string>)[m] ?? m
}

const LABEL: React.CSSProperties = {
  fontFamily: 'JetBrains Mono', fontSize: '0.6rem',
  letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--muted)',
}
const VAL: React.CSSProperties = { fontFamily: 'JetBrains Mono', fontSize: '0.74rem', color: 'var(--white)' }
const COLS = '1.2fr 0.8fr 0.8fr 0.8fr 1fr'

export default function HistoryPage() {
  const [items, setItems] = useState<PaymentHistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getPaymentHistory().then(r => setItems(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '80px' }}>
      <div className="loader" style={{ width: '28px', height: '28px' }} />
    </div>
  )

  if (items.length === 0) return (
    <div style={{ textAlign: 'center', paddingTop: '60px' }}>
      <p style={{ fontFamily: 'JetBrains Mono', color: 'var(--muted)', fontSize: '0.8rem', letterSpacing: '0.12em' }}>
        Платежей пока нет
      </p>
    </div>
  )

  const total = items.reduce((s, i) => s + i.amount, 0)

  return (
    <div>
      {/* Desktop table */}
      <div id="hist-table" style={{ border: '1px solid var(--border)', borderLeft: '2px solid var(--white)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: COLS, background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
          {['Дата', 'Сумма', 'Период', 'Устройства', 'Метод'].map(h => (
            <div key={h} style={{ padding: '12px 16px' }}><span style={LABEL}>{h}</span></div>
          ))}
        </div>
        {items.map(item => (
          <div key={item.id} style={{ display: 'grid', gridTemplateColumns: COLS, background: 'var(--surface)', borderTop: '1px solid var(--border)' }}>
            <div style={{ padding: '14px 16px' }}><span style={VAL}>{fmtDate(item.date)}</span></div>
            <div style={{ padding: '14px 16px' }}><span style={VAL}>{item.amount} ₽</span></div>
            <div style={{ padding: '14px 16px' }}><span style={VAL}>{fmtPlan(item.plan)}</span></div>
            <div style={{ padding: '14px 16px' }}><span style={VAL}>{item.device_limit}</span></div>
            <div style={{ padding: '14px 16px' }}><span style={VAL}>{fmtMethod(item.payment_method)}</span></div>
          </div>
        ))}
      </div>

      {/* Mobile cards */}
      <div id="hist-cards" style={{ display: 'none', flexDirection: 'column', gap: '8px' }}>
        {items.map(item => (
          <div key={item.id} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: '2px solid var(--white)', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={LABEL}>{fmtDate(item.date)}</span>
              <span style={{ fontFamily: 'Cormorant Garamond', fontSize: '1.2rem', fontWeight: 600, color: 'var(--white)' }}>
                {item.amount} ₽
              </span>
            </div>
            <span style={LABEL}>{fmtPlan(item.plan)} · {item.device_limit} устр. · {fmtMethod(item.payment_method)}</span>
          </div>
        ))}
      </div>

      <div style={{ marginTop: '14px', display: 'flex', justifyContent: 'space-between' }}>
        <span style={LABEL}>Всего платежей: {items.length}</span>
        <span style={LABEL}>Потрачено: {total} ₽</span>
      </div>

      <style>{`
        @media (max-width: 639px) {
          #hist-table { display: none !important; }
          #hist-cards { display: flex !important; }
        }
      `}</style>
    </div>
  )
}
