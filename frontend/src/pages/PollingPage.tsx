import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getPaymentStatus } from '../api'

type PollState = 'polling' | 'confirmed' | 'rejected' | 'error'

export default function PollingPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const pendingId = Number(params.get('pending_id'))
  const [state, setState] = useState<PollState>('polling')
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!pendingId) { navigate('/dashboard', { replace: true }); return }

    timer.current = setInterval(async () => {
      try {
        const { data } = await getPaymentStatus(pendingId)
        if (data.status === 'confirmed') {
          clearInterval(timer.current!); setState('confirmed')
          setTimeout(() => navigate('/dashboard', { replace: true }), 3000)
        } else if (data.status === 'rejected') {
          clearInterval(timer.current!); setState('rejected')
        }
      } catch {
        clearInterval(timer.current!); setState('error')
      }
    }, 3000)

    return () => { if (timer.current) clearInterval(timer.current) }
  }, [pendingId]) // eslint-disable-line react-hooks/exhaustive-deps

  const center: React.CSSProperties = {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', minHeight: '60vh', gap: '24px', textAlign: 'center',
  }

  return (
    <div style={center}>
      {state === 'polling' && (
        <>
          <div className="loader" style={{ width: '32px', height: '32px' }} />
          <div>
            <h2 style={{ fontFamily: 'Cormorant Garamond', fontSize: '1.8rem', fontWeight: 300, marginBottom: '8px' }}>
              Ожидание оплаты
            </h2>
            <p className="hint-text">Окно оплаты открылось в новой вкладке</p>
          </div>
        </>
      )}
      {state === 'confirmed' && (
        <div className="fade-in-up">
          <h2 style={{ fontFamily: 'Cormorant Garamond', fontSize: '2.2rem', fontWeight: 300, marginBottom: '8px' }}>
            Оплата прошла ⚡
          </h2>
          <p className="hint-text">Перенаправляем в кабинет...</p>
        </div>
      )}
      {state === 'rejected' && (
        <div className="fade-in-up">
          <h2 style={{ fontFamily: 'Cormorant Garamond', fontSize: '2rem', fontWeight: 300, marginBottom: '8px' }}>
            Платёж отклонён
          </h2>
          <p className="hint-text" style={{ marginBottom: '24px' }}>Попробуйте ещё раз</p>
          <button className="btn-ghost" onClick={() => navigate('/payment')}>← Вернуться к оплате</button>
        </div>
      )}
      {state === 'error' && (
        <div className="fade-in-up">
          <p className="hint-text" style={{ marginBottom: '16px' }}>Ошибка при проверке статуса</p>
          <button className="btn-ghost" onClick={() => navigate('/dashboard')}>← В кабинет</button>
        </div>
      )}
    </div>
  )
}
