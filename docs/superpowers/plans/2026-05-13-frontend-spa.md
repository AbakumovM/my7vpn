# Frontend SPA (MY7VPN Personal Cabinet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-featured React + Vite + TypeScript SPA personal cabinet on top of the existing FastAPI backend.

**Architecture:** Pure B&W design (Cormorant Garamond serif + JetBrains Mono monospace). SPA lives in `frontend/`, Vite proxies `/api/*` to FastAPI in dev. Auth is an httpOnly JWT cookie set by the backend; the axios 401 interceptor handles redirect to `/login`. All protected pages just render — 401 kicks in if unauthenticated.

**Tech Stack:** React 19, Vite 8, TypeScript, react-router-dom 7, axios (already installed), qrcode.react. Backend additions: one new method + one new endpoint.

---

## File Map

### Backend (one task)
- Modify: `src/apps/device/application/interfaces/view.py` — add Protocol method
- Modify: `src/apps/device/adapters/view.py` — implement method
- Modify: `src/apps/device/controllers/http/router.py` — add endpoint
- Test: `tests/unit/device/test_device_view.py`

### Frontend (ten tasks)
- Rewrite: `frontend/index.html`
- Rewrite: `frontend/src/index.css`
- Clear: `frontend/src/App.css`
- Modify: `frontend/src/api/index.ts` — add `verifyBotToken`
- Rewrite: `frontend/src/App.tsx`
- Create stubs: `frontend/src/pages/HistoryPage.tsx`, `ReferralPage.tsx`, `PollingPage.tsx`
- Rewrite: `frontend/src/components/Layout.tsx`
- Rewrite: `frontend/src/pages/LoginPage.tsx`
- Rewrite: `frontend/src/pages/DashboardPage.tsx`
- Rewrite: `frontend/src/pages/PaymentPage.tsx`
- Rewrite: `frontend/src/pages/PollingPage.tsx`
- Rewrite: `frontend/src/pages/HistoryPage.tsx`
- Rewrite: `frontend/src/pages/ReferralPage.tsx`

---

## Task 1: Backend — GET /api/v1/devices/subscription

The dashboard needs subscription info keyed by `user_id` (JWT), not `telegram_id`. The existing `get_subscription_info(telegram_id)` won't work for web-only users. We add a parallel method that queries by `user_id` directly.

**Files:**
- Modify: `src/apps/device/application/interfaces/view.py`
- Modify: `src/apps/device/adapters/view.py`
- Modify: `src/apps/device/controllers/http/router.py`
- Test: `tests/unit/device/test_device_view.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/device/test_device_view.py`:

```python
@pytest.mark.asyncio
async def test_get_subscription_info_by_user_id_returns_none_for_unknown():
    """Returns None when no subscription found for this user_id."""
    session = AsyncMock()
    session.execute.return_value = MagicMock(first=MagicMock(return_value=None))
    view = SQLAlchemyDeviceView(session)
    result = await view.get_subscription_info_by_user_id(user_id=999)
    assert result is None
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/unit/device/test_device_view.py::test_get_subscription_info_by_user_id_returns_none_for_unknown -v
```

Expected: `FAILED` — `AttributeError: ... has no attribute 'get_subscription_info_by_user_id'`

- [ ] **Step 3: Add to Protocol**

In `src/apps/device/application/interfaces/view.py`, after the `get_subscription_info` line:

```python
    async def get_subscription_info_by_user_id(self, user_id: int) -> SubscriptionInfo | None: ...
```

- [ ] **Step 4: Implement in adapter**

In `src/apps/device/adapters/view.py`, after the `get_subscription_info` method:

```python
    async def get_subscription_info_by_user_id(self, user_id: int) -> SubscriptionInfo | None:
        """Works for both Telegram users and web-only users (no telegram_id needed)."""
        row_result = await self._session.execute(
            select(
                UserSubscriptionORM.end_date,
                UserSubscriptionORM.device_limit,
                UserORM.subscription_url,
            )
            .join(UserORM, UserSubscriptionORM.user_id == UserORM.id)
            .where(UserSubscriptionORM.user_id == user_id)
            .order_by(UserSubscriptionORM.end_date.desc())
            .limit(1)
        )
        row = row_result.first()
        if row is None:
            return None
        last_payment_result = await self._session.execute(
            select(UserPaymentORM.amount)
            .where(UserPaymentORM.user_id == user_id)
            .order_by(UserPaymentORM.payment_date.desc())
            .limit(1)
        )
        last_amount = last_payment_result.scalar_one_or_none()
        return SubscriptionInfo(
            end_date=row.end_date,
            device_limit=row.device_limit,
            last_payment_amount=last_amount,
            subscription_url=row.subscription_url,
        )
```

- [ ] **Step 5: Run test — expect pass**

```bash
uv run pytest tests/unit/device/test_device_view.py::test_get_subscription_info_by_user_id_returns_none_for_unknown -v
```

Expected: `PASSED`

- [ ] **Step 6: Add HTTP endpoint**

In `src/apps/device/controllers/http/router.py`, add before the `/{device_id}` route:

```python
@router.get("/subscription")
async def get_subscription(
    user_id: CurrentUser,
    device_view: FromDishka[DeviceView],
) -> dict | None:
    info = await device_view.get_subscription_info_by_user_id(user_id)
    if info is None:
        return None
    return {
        "end_date": info.end_date.isoformat() if info.end_date else None,
        "device_limit": info.device_limit,
        "last_payment_amount": info.last_payment_amount,
        "subscription_url": info.subscription_url,
    }
```

- [ ] **Step 7: Run all device tests**

```bash
uv run pytest tests/unit/device/ -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/apps/device/application/interfaces/view.py \
        src/apps/device/adapters/view.py \
        src/apps/device/controllers/http/router.py \
        tests/unit/device/test_device_view.py
git commit -m "feat: add get_subscription_info_by_user_id and GET /api/v1/devices/subscription"
```

---

## Task 2: Design system

Rewrite `index.css` with the pure B&W palette. Remove amber/danger/success variables that were in the old version.

**Files:**
- Rewrite: `frontend/index.html`
- Rewrite: `frontend/src/index.css`
- Clear: `frontend/src/App.css`

- [ ] **Step 1: Update index.html**

```html
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MY7VPN — Личный кабинет</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Rewrite index.css**

```css
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=JetBrains+Mono:wght@300;400;700&display=swap');

@import "tailwindcss";

:root {
  --black:     #000000;
  --surface:   #0D0D0D;
  --surface-2: #1C1C1C;
  --border:    #282828;
  --white:     #FFFFFF;
  --muted:     #444444;
  --dim:       #222222;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; -webkit-font-smoothing: antialiased; }

body {
  background-color: var(--black);
  color: var(--white);
  font-family: 'JetBrains Mono', monospace;
  font-weight: 300;
  min-height: 100vh;
  overflow-x: hidden;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(255,255,255,0.018) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255,255,255,0.018) 1px, transparent 1px);
  background-size: 80px 80px;
  pointer-events: none;
  z-index: 0;
}

#root { position: relative; z-index: 1; }

h1, h2, h3 {
  font-family: 'Cormorant Garamond', serif;
  font-weight: 300;
  letter-spacing: 0.02em;
  color: var(--white);
}

/* ── Кнопки ─────────────────────────────────────── */
.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 13px 30px;
  background: var(--white);
  color: var(--black);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px));
  text-decoration: none;
}
.btn-primary:hover  { opacity: 0.85; transform: translateY(-1px); }
.btn-primary:active { transform: translateY(0); }
.btn-primary:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }

.btn-ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 29px;
  background: transparent;
  color: var(--white);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  font-weight: 400;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: border-color 0.15s;
  text-decoration: none;
}
.btn-ghost:hover    { border-color: var(--white); }
.btn-ghost:disabled { opacity: 0.35; cursor: not-allowed; }

/* ── Карточки ────────────────────────────────────── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 28px;
  position: relative;
}
.card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 2px;
  height: 100%;
  background: var(--white);
}

/* ── Инпуты ──────────────────────────────────────── */
.input {
  width: 100%;
  padding: 13px 16px;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--white);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.15s;
}
.input:focus  { border-color: var(--white); }
.input::placeholder { color: var(--muted); }

/* ── Данные ──────────────────────────────────────── */
.data-value {
  font-family: 'Cormorant Garamond', serif;
  font-size: 2.2rem;
  font-weight: 600;
  color: var(--white);
  line-height: 1;
}
.data-label {
  font-size: 0.6rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}

/* ── Вспомогательный текст ───────────────────────── */
.divider    { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
.error-text { color: rgba(255,255,255,0.45); font-size: 0.75rem; margin-top: 6px; }
.hint-text  { color: var(--muted); font-size: 0.75rem; margin-top: 6px; font-family: 'JetBrains Mono', monospace; }

/* ── Анимации ────────────────────────────────────── */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes spin  { to { transform: rotate(360deg); } }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.fade-in-up   { animation: fadeInUp 0.35s ease both; }
.fade-in-up-1 { animation-delay: 0.05s; }
.fade-in-up-2 { animation-delay: 0.10s; }
.fade-in-up-3 { animation-delay: 0.15s; }

.loader {
  width: 20px; height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--white);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}

.pulse { animation: pulse 2s ease-in-out infinite; }
```

- [ ] **Step 3: Clear App.css**

Replace `frontend/src/App.css` content with:

```css
/* App-level styles — use index.css globals */
```

- [ ] **Step 4: Verify dev server starts**

```bash
cd frontend && npm run dev
```

Open http://localhost:5173 — page must be black (boilerplate content still, that's fine). No CSS errors in console.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/src/index.css frontend/src/App.css
git commit -m "feat: design system — pure B&W palette, Cormorant+Mono"
```

---

## Task 3: API client update + install qrcode.react

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/package.json` (via npm)

- [ ] **Step 1: Add verifyBotToken**

In `frontend/src/api/index.ts`, add after `verifyOtp`:

```ts
export const verifyBotToken = (token: string) =>
  api.get<{ access_token: string; user_id: number }>(`/auth/bot-token/${token}`)
```

- [ ] **Step 2: Install qrcode.react**

```bash
cd frontend && npm install qrcode.react
```

`qrcode.react` ships its own TypeScript types — no `@types/` package needed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/index.ts frontend/package.json frontend/package-lock.json
git commit -m "feat: add verifyBotToken, install qrcode.react"
```

---

## Task 4: App.tsx router + page stubs

**Files:**
- Rewrite: `frontend/src/App.tsx`
- Create: `frontend/src/pages/HistoryPage.tsx`
- Create: `frontend/src/pages/ReferralPage.tsx`
- Create: `frontend/src/pages/PollingPage.tsx`

- [ ] **Step 1: Create stub pages**

`frontend/src/pages/HistoryPage.tsx`:
```tsx
export default function HistoryPage() {
  return <p style={{ color: 'var(--muted)', fontFamily: 'JetBrains Mono' }}>История платежей</p>
}
```

`frontend/src/pages/ReferralPage.tsx`:
```tsx
export default function ReferralPage() {
  return <p style={{ color: 'var(--muted)', fontFamily: 'JetBrains Mono' }}>Рефералы</p>
}
```

`frontend/src/pages/PollingPage.tsx`:
```tsx
export default function PollingPage() {
  return <p style={{ color: 'var(--muted)', fontFamily: 'JetBrains Mono' }}>Ожидание оплаты...</p>
}
```

- [ ] **Step 2: Rewrite App.tsx**

```tsx
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
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx \
        frontend/src/pages/HistoryPage.tsx \
        frontend/src/pages/ReferralPage.tsx \
        frontend/src/pages/PollingPage.tsx
git commit -m "feat: router with all routes, page stubs"
```

---

## Task 5: Layout component

Desktop: sticky header 56px (logo + nav + logout). Mobile (< 640px): header 48px + tab bar pinned to bottom 52px. Active tab = white text + white 2px border.

**Files:**
- Rewrite: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Rewrite Layout.tsx**

```tsx
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
```

- [ ] **Step 2: Visual check**

`npm run dev` → http://localhost:5173/dashboard. Verify header is black with logo/nav. On mobile viewport (DevTools < 640px) — nav disappears, tab bar appears at bottom.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Layout.tsx
git commit -m "feat: Layout — B&W header, desktop nav, mobile tab bar"
```

---

## Task 6: LoginPage

Two-step: email → OTP. Also handles `?token=xxx` param from bot magic link (auto-calls `/auth/bot-token/{token}`).

**Files:**
- Rewrite: `frontend/src/pages/LoginPage.tsx`

- [ ] **Step 1: Rewrite LoginPage.tsx**

```tsx
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

  async function submitEmail(e: React.FormEvent) {
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

  async function submitOtp(e: React.FormEvent) {
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
            MY7VPN
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
```

- [ ] **Step 2: Visual check**

http://localhost:5173/login — black page, centered card, no color accents. Submit email → OTP step with large centered input field.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx
git commit -m "feat: LoginPage — email/OTP two-step, bot-token auto-login"
```

---

## Task 7: DashboardPage

Parallel fetches: `GET /users/me` + `GET /devices/subscription` + `GET /users/referral`. Renders: big days counter + progress bar + metrics row (devices / balance / referrals) + subscription URL + QR toggle + connection instructions. CTA block when no subscription.

**Files:**
- Rewrite: `frontend/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Rewrite DashboardPage.tsx**

```tsx
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
```

- [ ] **Step 2: Visual check**

Log in, navigate to /dashboard. Verify: loading spinner → data renders. If no subscription, CTA block. Days counter is large serif font. QR toggle works.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx
git commit -m "feat: DashboardPage — counter, progress, metrics, QR code, instructions"
```

---

## Task 8: PaymentPage + PollingPage

PaymentPage: device toggle (3 buttons) → period grid (2×2) → summary → pay. On `final_amount > 0`: open YooKassa URL + redirect to polling. On `final_amount == 0`: confirm directly → show success.

PollingPage: polls `GET /payments/{pending_id}/status` every 3s → confirmed → redirect to dashboard.

**Files:**
- Rewrite: `frontend/src/pages/PaymentPage.tsx`
- Rewrite: `frontend/src/pages/PollingPage.tsx`

- [ ] **Step 1: Rewrite PaymentPage.tsx**

```tsx
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
        <button className="btn-primary" onClick={handlePay} disabled={paying}>
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
```

- [ ] **Step 2: Rewrite PollingPage.tsx**

```tsx
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
```

- [ ] **Step 3: Visual check**

Navigate to `/payment`. Verify: device buttons toggle correctly (white = selected), period 2×2 grid, summary price updates. Click "Активировать" when balance covers full amount → success screen → back to dashboard.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/PaymentPage.tsx frontend/src/pages/PollingPage.tsx
git commit -m "feat: PaymentPage — tariff selector, payment flow; PollingPage — status polling"
```

---

## Task 9: HistoryPage

Table on desktop, cards on mobile (< 640px). Empty state. Summary row.

**Files:**
- Rewrite: `frontend/src/pages/HistoryPage.tsx`

- [ ] **Step 1: Rewrite HistoryPage.tsx**

```tsx
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
```

- [ ] **Step 2: Visual check**

Navigate to `/history`. Desktop: table with 5 columns. Mobile: card layout. Empty state when no payments.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/HistoryPage.tsx
git commit -m "feat: HistoryPage — payment history table, mobile cards, empty state"
```

---

## Task 10: ReferralPage

Referral link with copy button, invited count, mechanics explanation.

**Files:**
- Rewrite: `frontend/src/pages/ReferralPage.tsx`

- [ ] **Step 1: Rewrite ReferralPage.tsx**

```tsx
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
```

- [ ] **Step 2: Visual check**

Navigate to `/referral`. Verify: referral link with copy, count renders as large serif number, mechanics list.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ReferralPage.tsx
git commit -m "feat: ReferralPage — link copy, invited count, mechanics"
```

---

## Self-review

**Spec coverage:**
- ✅ Login: email → OTP two-step; bot-token auto-login from `?token=`
- ✅ Dashboard B: big serif days counter + progress bar + expiry date
- ✅ Dashboard: metrics row (devices / balance / referrals)
- ✅ Dashboard: subscription URL + QR (client-side via qrcode.react) + connection instructions
- ✅ Dashboard: CTA when no subscription; expiry warning ≤7 days + Продлить button
- ✅ Payment A: device toggle (3 buttons) + period 2×2 grid
- ✅ Payment: balance deduction shown in summary
- ✅ Payment: `final_amount == 0` → instant confirm → "Активировано" screen
- ✅ Payment: `final_amount > 0` → open payment URL + navigate to polling
- ✅ PollingPage: polls every 3s, confirmed → redirect, rejected → error
- ✅ History: desktop table + mobile cards + empty state + totals
- ✅ Referral: link + count + mechanics
- ✅ Design system: pure B&W (no amber), Cormorant Garamond + JetBrains Mono
- ✅ Cards: left 2px white border
- ✅ Buttons: primary (white bg + black text + clip-path), ghost (border)
- ✅ Navigation C: header + tab bar; mobile: bottom tab bar
- ✅ Body grid texture (in index.css)
- ✅ Backend: `GET /api/v1/devices/subscription` works for all users

**Type consistency check:**
- `SubscriptionInfo.end_date: string | null` — used as `new Date(sub.end_date)` inside null guard ✅
- `Tariffs` indexed as `tariffs[String(deviceLimit)][String(plan)]` matches backend string keys ✅
- `PaymentHistoryItem.plan: number` → `fmtPlan(item.plan)` ✅
- `Referral.invited_count: number` → used directly ✅
- `verifyBotToken` added in Task 3, used in LoginPage Task 6 ✅
