import { Dashboard } from './pages/Dashboard'

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 px-4 py-4 md:px-6">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <h1 className="text-lg font-semibold text-slate-100">
            macd_searcher <span className="font-normal text-slate-500">dashboard</span>
          </h1>
          <span className="text-xs text-slate-600">1D MACD zero-line scanner · Hyperliquid</span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl p-4 md:p-6">
        <Dashboard />
      </main>
    </div>
  )
}
