import ClaimsWorkbench from './pages/ClaimsWorkbench'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center gap-3 border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-600 text-lg font-bold text-white">
          C
        </div>
        <div>
          <div className="font-semibold text-gray-900">ClaustraRCM</div>
          <div className="text-xs text-gray-500">Claim Validation</div>
        </div>
      </header>
      <main>
        <ClaimsWorkbench />
      </main>
    </div>
  )
}

export default App
