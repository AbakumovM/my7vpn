import { Link, useLocation, useNavigate } from 'react-router-dom'
import { logout } from '../api'

const NAV = [
  { path: '/dashboard', label: 'Кабинет',  short: 'Кабин.' },
  { path: '/payment',   label: 'Подписка', short: 'Подпис.' },
  { path: '/history',   label: 'История',  short: 'Истор.' },
  { path: '/referral',  label: 'Рефералы', short: 'Рефер.' },
]

function LogoIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="8"  y="70" width="20" height="3" fill="currentColor"/>
      <rect x="10" y="35" width="16" height="35" fill="none" stroke="currentColor" strokeWidth="2"/>
      <rect x="10" y="35" width="16" height="4" fill="currentColor"/>
      <rect x="8"  y="28" width="20" height="7" fill="currentColor"/>
      <rect x="72" y="70" width="20" height="3" fill="currentColor"/>
      <rect x="74" y="35" width="16" height="35" fill="none" stroke="currentColor" strokeWidth="2"/>
      <rect x="74" y="35" width="16" height="4" fill="currentColor"/>
      <rect x="72" y="28" width="20" height="7" fill="currentColor"/>
      <path d="M57 10 L42 50 L52 50 L43 90 L68 42 L56 42 Z" fill="currentColor"/>
    </svg>
  )
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout().catch(() => {})
    navigate('/login')
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        borderBottom: '1px solid var(--border)',
        padding: '0 40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '56px',
        position: 'sticky',
        top: 0,
        background: 'rgba(0,0,0,0.96)',
        backdropFilter: 'blur(8px)',
        zIndex: 100,
      }}>
        <Link to="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none', color: 'var(--white)' }}>
          <LogoIcon />
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.82rem', letterSpacing: '0.2em', textTransform: 'uppercase', fontWeight: 700 }}>
            MY7VPN
          </span>
        </Link>

        {/* Desktop nav */}
        <nav id="desktop-nav" style={{ display: 'flex' }}>
          {NAV.map(({ path, label }) => {
            const active = location.pathname === path
            return (
              <Link key={path} to={path} style={{
                padding: '0 16px',
                height: '56px',
                display: 'flex',
                alignItems: 'center',
                textDecoration: 'none',
                fontFamily: 'JetBrains Mono',
                fontSize: '0.64rem',
                letterSpacing: '0.16em',
                textTransform: 'uppercase',
                color: active ? 'var(--white)' : 'var(--muted)',
                borderBottom: active ? '2px solid var(--white)' : '2px solid transparent',
                transition: 'color 0.15s',
              }}
              onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.65)' }}
              onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.color = 'var(--muted)' }}
              >
                {label}
              </Link>
            )
          })}
        </nav>

        <button onClick={handleLogout} className="btn-ghost" style={{ padding: '7px 14px', fontSize: '0.62rem' }}>
          Выйти
        </button>
      </header>

      <main style={{ flex: 1, padding: '32px 40px 80px', maxWidth: '960px', margin: '0 auto', width: '100%' }}>
        {children}
      </main>

      <footer id="desktop-footer" style={{
        borderTop: '1px solid var(--border)',
        padding: '14px 40px',
        display: 'flex',
        justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: '0.62rem', color: 'var(--muted)', letterSpacing: '0.1em', fontFamily: 'JetBrains Mono' }}>MY7VPN © 2026</span>
        <span style={{ fontSize: '0.62rem', color: 'var(--border)', letterSpacing: '0.08em', fontFamily: 'JetBrains Mono' }}>SECURE · FAST · PRIVATE</span>
      </footer>

      {/* Mobile tab bar */}
      <nav id="mobile-tab" style={{
        position: 'fixed',
        bottom: 0, left: 0, right: 0,
        height: '52px',
        borderTop: '1px solid var(--border)',
        background: 'rgba(0,0,0,0.97)',
        display: 'none',
        zIndex: 100,
      }}>
        {NAV.map(({ path, short }) => {
          const active = location.pathname === path
          return (
            <Link key={path} to={path} style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textDecoration: 'none',
              fontFamily: 'JetBrains Mono',
              fontSize: '0.56rem',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: active ? 'var(--white)' : 'var(--muted)',
              borderTop: active ? '2px solid var(--white)' : '2px solid transparent',
              marginTop: '-1px',
            }}>
              {short}
            </Link>
          )
        })}
      </nav>

      <style>{`
        @media (max-width: 639px) {
          #desktop-nav    { display: none !important; }
          #desktop-footer { display: none !important; }
          #mobile-tab     { display: flex !important; }
          main { padding: 20px 16px 72px !important; }
          header { padding: 0 16px !important; }
        }
      `}</style>
    </div>
  )
}
