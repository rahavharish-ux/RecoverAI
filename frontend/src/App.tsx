import { useState } from 'react'
import { AgentActivity } from './components/AgentActivity'
import { CaseIntelligence } from './components/CaseIntelligence'
import { CasesList } from './components/CasesList'
import { Dashboard } from './components/Dashboard'
import { DemoCenter } from './components/DemoCenter'
import { ModelIntelligence } from './components/ModelIntelligence'
import { Shell, type View } from './components/Shell'

function App() {
  const [view, setView] = useState<View>('dashboard')
  const [selectedCaseId, setSelectedCaseId] = useState(1)

  const openCase = (caseId: number) => {
    setSelectedCaseId(caseId)
    setView('case-intelligence')
  }

  return (
    <Shell view={view} onNavigate={setView}>
      {view === 'dashboard' && <Dashboard onOpenCase={openCase} />}
      {view === 'cases' && <CasesList onOpenCase={openCase} />}
      {view === 'case-intelligence' && <CaseIntelligence initialCaseId={selectedCaseId} key={selectedCaseId} />}
      {view === 'agent-activity' && <AgentActivity onOpenCase={openCase} />}
      {view === 'model-intelligence' && <ModelIntelligence />}
      {view === 'demo-center' && <DemoCenter onOpenCase={openCase} />}
    </Shell>
  )
}

export default App
