import { useState } from 'react'
import { Dashboard } from './pages/Dashboard'
import { Outcomes } from './pages/Outcomes'

type Tab = 'dashboard' | 'outcomes'

const TABS: { value: Tab; label: string }[] = [
  { value: 'dashboard', label: 'Dashboard' },
  { value: 'outcomes', label: 'Outcomes' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 px-4 py-4 md:px-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-6">
            <h1 className="text-lg font-semibold text-slate-100">
              macd_searcher <span className="font-normal text-slate-500">dashboard</span>
            </h1>
            <nav className="flex gap-1">
              {TABS.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTab(t.value)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    tab === t.value
                      ? 'bg-slate-800 text-slate-100'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          </div>
          <span className="text-xs text-slate-600">1D MACD zero-line scanner · Hyperliquid</span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl p-4 md:p-6">
        {tab === 'dashboard' ? <Dashboard /> : <Outcomes />}
      </main>
    </div>
  )
}
