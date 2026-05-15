import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { requestOtp, verifyBotToken, verifyOtp } from '../api'

type Step = 'email' | 'otp' | 'bot-verifying'

const S: Record<string, React.CSSProperties> = {
  center: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' },
  card:   { background: 'var(--surface)', border: '1px solid var(--border)', padding: '40px', width: '100%', maxWidth: '380px', position: 'relative' },
  label:  { display: 'block', fontSize: '0.6rem', letterSpacing: '0.2em', textTransform: 'uppercase' as const, color: 'var(--muted)', marginBottom: '8px', fontFamily: 'JetBrains Mono' },
  hint:   { fontSize: '0.74rem', color: 'var(--muted)', fontFamily: 'JetBrains Mono', lineHeight: 1.5 },
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const otpRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const token = searchParams.get('token')
    if (!token) return
    setStep('bot-verifying')
    verifyBotToken(token)
      .then(() => navigate('/dashboard', { replace: true }))
      .catch(() => { setStep('email'); setError('Ссылка устарела. Войдите через email.') })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function submitEmail(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true); setError(null)
    try {
      await requestOtp(email.trim())
      setStep('otp')
      setTimeout(() => otpRef.current?.focus(), 50)
    } catch {
      setError('Не удалось отправить код. Проверьте email.')
    } finally { setLoading(false) }
  }

  async function submitOtp(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true); setError(null)
    try {
      await verifyOtp(email.trim(), code.trim())
      navigate('/dashboard', { replace: true })
    } catch {
      setError('Неверный или просроченный код.')
    } finally { setLoading(false) }
  }

  if (step === 'bot-verifying') {
    return (
      <div style={S.center}>
        <div style={S.card}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
            <div className="loader" style={{ width: '28px', height: '28px' }} />
          </div>
          <p style={{ ...S.hint, textAlign: 'center' }}>Выполняется вход...</p>
        </div>
      </div>
    )
  }

  return (
    <div style={S.center}>
      <div style={S.card} className="fade-in-up">
        <div style={{ textAlign: 'center', marginBottom: '36px' }}>
          <h1 style={{ fontFamily: 'Cormorant Garamond', fontSize: '2rem', fontWeight: 300, letterSpacing: '0.06em', marginBottom: '4px' }}>
            ZEVSgate
          </h1>
          <p style={{ ...S.label, margin: 0, textAlign: 'center' }}>Личный кабинет</p>
        </div>

        {step === 'email' ? (
          <form onSubmit={submitEmail}>
            <label style={S.label}>Email</label>
            <input className="input" type="email" placeholder="you@example.com"
              value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
            {error && <p className="error-text">{error}</p>}
            <button type="submit" className="btn-primary" disabled={loading}
              style={{ width: '100%', marginTop: '24px' }}>
              {loading ? <span className="loader" style={{ width: '12px', height: '12px' }} /> : 'Получить код'}
            </button>
          </form>
        ) : (
          <form onSubmit={submitOtp}>
            <p style={{ ...S.hint, marginBottom: '20px' }}>
              Отправили код на <span style={{ color: 'var(--white)' }}>{email}</span>
            </p>
            <label style={S.label}>Код подтверждения</label>
            <input ref={otpRef} className="input" type="text" inputMode="numeric"
              placeholder="000000" value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              style={{ textAlign: 'center', letterSpacing: '0.4em', fontSize: '1.4rem' }}
              required />
            {error && <p className="error-text">{error}</p>}
            <button type="submit" className="btn-primary" disabled={loading}
              style={{ width: '100%', marginTop: '24px' }}>
              {loading ? <span className="loader" style={{ width: '12px', height: '12px' }} /> : 'Войти →'}
            </button>
            <button type="button"
              onClick={() => { setStep('email'); setCode(''); setError(null) }}
              style={{ display: 'block', width: '100%', marginTop: '14px', background: 'none', border: 'none', cursor: 'pointer', ...S.hint, textAlign: 'center' }}>
              ← Изменить email
            </button>
          </form>
        )}

        <hr className="divider" style={{ marginTop: '32px' }} />
        <p style={{ ...S.hint, textAlign: 'center' }}>
          Или войдите через бот командой{' '}
          <span style={{ color: 'var(--white)' }}>/web</span>
        </p>
      </div>
    </div>
  )
}
