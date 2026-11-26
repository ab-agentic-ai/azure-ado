import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Activity, ArrowUp, ArrowUpRight, Bot, Check, ChevronDown, CircleHelp, Command, Database, FolderGit2, KeyRound, LockKeyhole, MessageSquareText, PanelLeftClose, ShieldCheck, Sparkles, TerminalSquare, UsersRound, Workflow, X } from 'lucide-react'

type Reply = { answer: string; data?: Record<string, unknown>[]; error?: boolean; suggestions?: string[]; truncated?: boolean }
type Message = { role: 'user' | 'assistant'; text: string; data?: Record<string, unknown>[]; error?: boolean; time: string }

const capabilities = [
  { label: 'Projects', icon: FolderGit2, prompt: 'List my Azure DevOps projects' },
  { label: 'Permissions', icon: UsersRound, prompt: 'Show project permissions' },
  { label: 'Repository policies', icon: ShieldCheck, prompt: 'Show repository policies' },
  { label: 'Agent pools', icon: Workflow, prompt: 'List agent pools' },
  { label: 'Library groups', icon: Database, prompt: 'Show library group pipeline and security permissions' },
  { label: 'Environments', icon: Activity, prompt: 'List environment pipeline permissions' },
]

const initialMessage: Message = {
  role: 'assistant',
  text: 'Hi, I’m ADO-MCP. I can help you inspect Azure DevOps configuration and access. Connect your organization, then ask a question in plain language.',
  time: 'NOW',
}

function timeLabel() { return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(new Date()) }

export default function App() {
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')
  const [organization, setOrganization] = useState('')
  const [project, setProject] = useState('')
  const [mode, setMode] = useState<'pat' | 'sso'>('pat')
  const [pat, setPat] = useState('')
  const [messages, setMessages] = useState<Message[]>([initialMessage])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [connected, setConnected] = useState(false)
  const [showSettings, setShowSettings] = useState(true)
  const [health, setHealth] = useState<'checking' | 'online' | 'offline'>('checking')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let alive = true
    fetch(`${apiBase.replace(/\/$/, '')}/api/health`, { credentials: 'include' }).then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(() => { if (alive) setHealth('online') }).catch(() => { if (alive) setHealth('offline') })
    return () => { alive = false }
  }, [apiBase])
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }) }, [messages, busy])

  async function send(event?: FormEvent, text = draft) {
    event?.preventDefault()
    const prompt = text.trim()
    if (!prompt || busy) return
    setMessages(prev => [...prev, { role: 'user', text: prompt, time: timeLabel() }])
    setDraft(''); setBusy(true)
    try {
      if (!organization.trim()) throw new Error('Add your Azure DevOps organization in Connection settings first.')
      if (mode === 'pat' && !pat) throw new Error('Enter a PAT in Connection settings first.')
      const response = await fetch(`${apiBase.replace(/\/$/, '')}/api/chat`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, organization, project: project || null, auth: { mode, ...(mode === 'pat' ? { pat } : {}) } }),
      })
      const result = await response.json() as Reply
      if (!response.ok) throw new Error(result.answer || `Request failed (${response.status})`)
      setMessages(prev => [...prev, { role: 'assistant', text: result.answer, data: result.data, error: result.error, time: timeLabel() }])
      setConnected(!result.error)
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', text: err instanceof Error ? err.message : 'Something went wrong.', error: true, time: timeLabel() }])
      setConnected(false)
    } finally { setBusy(false); setPat('') }
  }

  return <div className="shell">
    <aside className="rail">
      <div className="brand-mark"><Command size={19} strokeWidth={2.3} /></div>
      <div className="rail-rule" />
      <button className="rail-button active" aria-label="Chat"><MessageSquareText size={18} /></button>
      <button className="rail-button" aria-label="Connections" onClick={() => setShowSettings(true)}><KeyRound size={18} /></button>
      <div className="rail-bottom"><button className="rail-button" aria-label="Help"><CircleHelp size={18} /></button><div className="avatar">A</div></div>
    </aside>

    <main className="main-pane">
      <header className="topbar">
        <div className="breadcrumbs"><span>Workspace</span><span className="slash">/</span><strong>ADO-MCP</strong><ChevronDown size={14} /></div>
        <div className="top-actions"><div className={`service-pill ${health}`}><span className="pulse" />{health === 'online' ? 'API online' : health === 'offline' ? 'API offline' : 'Checking API'}</div><button className="icon-button" title="Connection settings" onClick={() => setShowSettings(!showSettings)}><PanelLeftClose size={17} /></button></div>
      </header>

      <section className="conversation" ref={scrollRef}>
        <div className="conversation-inner">
          <div className="date-divider"><span>YOUR WORKSPACE</span></div>
          {messages.length === 1 && <div className="welcome">
            <div className="welcome-icon"><Bot size={24} /></div>
            <div className="eyebrow"><Sparkles size={13} /> AZURE DEVOPS COMPLIANCE AGENT</div>
            <h1>Good afternoon.<br /><span>What should we look into?</span></h1>
            <p>Inspect your Azure DevOps setup using plain language. Your queries are read-only and run through your local agent.</p>
            <div className="capability-grid">{capabilities.map(item => <button className="capability" key={item.label} onClick={() => send(undefined, item.prompt)}><item.icon size={16} /><span>{item.label}</span><ArrowUpRight size={13} className="cap-arrow" /></button>)}</div>
          </div>}
          {messages.map((message, i) => <div className={`message-row ${message.role}`} key={`${i}-${message.time}`}>
            <div className={`message-avatar ${message.role}`}>{message.role === 'assistant' ? <Bot size={16} /> : 'A'}</div>
            <div className="message-content"><div className="message-meta"><strong>{message.role === 'assistant' ? 'ADO-MCP' : 'You'}</strong><span>{message.time}</span></div><div className={`message-bubble ${message.error ? 'error' : ''}`}>{message.text}</div>
              {message.data && message.data.length > 0 && <DataTable rows={message.data} />}
            </div>
          </div>)}
          {busy && <div className="message-row assistant"><div className="message-avatar assistant"><Bot size={16} /></div><div className="message-content"><div className="message-meta"><strong>ADO-MCP</strong><span>WORKING</span></div><div className="typing"><i /><i /><i /></div></div></div>}
          {messages.length === 1 && <div className="welcome-note"><LockKeyhole size={13} /> Read-only access <span>·</span> Credentials stay in this session</div>}
        </div>
      </section>

      <footer className="composer-area">
        <div className="composer-wrap"><form className="composer" onSubmit={send}><textarea value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() } }} placeholder="Ask about your Azure DevOps organization..." rows={1} /><div className="composer-bottom"><div className="composer-hint"><span className="kbd">↵</span> to send <span className="kbd">⇧ ↵</span> new line</div><button className="send-button" disabled={!draft.trim() || busy} aria-label="Send message"><ArrowUp size={16} /></button></div></form><div className="composer-disclaimer">ADO-MCP can make mistakes. Verify important permission and policy findings.</div></div>
      </footer>
    </main>

    {showSettings && <aside className="settings-panel">
      <div className="settings-heading"><div><div className="settings-kicker">CONFIGURATION</div><h2>Connection</h2></div><button className="icon-button close-settings" aria-label="Close settings" onClick={() => setShowSettings(false)}><X size={17} /></button></div>
      <div className="settings-status"><span className={`status-dot ${health}`} /><div><strong>{connected ? `Connected to ${organization}` : health === 'online' ? 'Local agent is ready' : health === 'offline' ? 'Agent not reachable' : 'Checking local agent'}</strong><small>{apiBase}</small></div><button className="text-icon" onClick={() => { setHealth('checking'); fetch(`${apiBase.replace(/\/$/, '')}/api/health`, { credentials: 'include' }).then(r => { if (!r.ok) throw new Error(); setHealth('online') }).catch(() => setHealth('offline')) }} title="Refresh status"><Activity size={15} /></button></div>
      <label className="field-label" htmlFor="api-url">LOCAL API URL</label><input id="api-url" className="field" value={apiBase} onChange={e => setApiBase(e.target.value)} placeholder="http://localhost:8000" />
      <div className="section-label">AZURE DEVOPS</div>
      <label className="field-label" htmlFor="organization">ORGANIZATION</label><div className="input-prefix"><span>dev.azure.com/</span><input id="organization" value={organization} onChange={e => setOrganization(e.target.value)} placeholder="your-org" /></div>
      <label className="field-label" htmlFor="project">PROJECT <span className="optional">OPTIONAL</span></label><input id="project" className="field" value={project} onChange={e => setProject(e.target.value)} placeholder="Project name" />
      <div className="section-label auth-label">AUTHENTICATION</div><div className="auth-toggle"><button className={mode === 'pat' ? 'selected' : ''} onClick={() => setMode('pat')}><KeyRound size={14} /> PAT</button><button className={mode === 'sso' ? 'selected' : ''} onClick={() => setMode('sso')}><ShieldCheck size={14} /> CLI SSO</button></div>
      {mode === 'pat' ? <><label className="field-label" htmlFor="pat">PERSONAL ACCESS TOKEN</label><input id="pat" className="field" type="password" autoComplete="off" value={pat} onChange={e => setPat(e.target.value)} placeholder="Paste token when ready" /><div className="field-hint"><LockKeyhole size={12} /> Used only for your next request, then cleared.</div></> : <div className="sso-info"><TerminalSquare size={16} /><span>Sign in on your Mac mini with <code>az login</code>. The local Docker agent reads that session.</span></div>}
      <div className="settings-divider" />
      <div className="scope-heading"><span>AVAILABLE INSPECTIONS</span><span>06</span></div>
      <div className="scope-list">{capabilities.map((item, index) => <div className="scope-item" key={item.label}><span className="scope-number">0{index + 1}</span><span>{item.label}</span><Check size={14} /></div>)}</div>
      <div className="settings-footer"><span className="foot-dot" /> Local-first · Read-only API</div>
    </aside>}
  </div>
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = Object.keys(rows[0] ?? {}).slice(0, 4)
  return <div className="data-card"><div className="data-card-head"><span><Database size={13} /> RESULTS</span><span>{rows.length} {rows.length === 1 ? 'ITEM' : 'ITEMS'}</span></div><div className="table-scroll"><table><thead><tr>{columns.map(key => <th key={key}>{key.replace(/([A-Z])/g, ' $1')}</th>)}</tr></thead><tbody>{rows.slice(0, 12).map((row, i) => <tr key={i}>{columns.map(key => <td key={key}>{typeof row[key] === 'object' ? JSON.stringify(row[key]) : String(row[key] ?? '—')}</td>)}</tr>)}</tbody></table></div>{rows.length > 12 && <div className="data-more">Showing first 12 results</div>}</div>
}
