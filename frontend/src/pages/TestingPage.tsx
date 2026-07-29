import { useState, useRef, useEffect } from 'react'
import { testingApi } from '../api/client'
import { Play, Settings, Send, User, Bot, AlertCircle } from 'lucide-react'

export default function TestingPage() {
  const [messages, setMessages] = useState<{role: string, content: string}[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<'agent' | 'orchestrator'>('agent')
  const [model, setModel] = useState('deepseek-chat')
  const [apiKey, setApiKey] = useState('')
  const [showSettings, setShowSettings] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const formatOrchestrateResponse = (response: any) => {
    const plan = response.plan_executed || []
    const log = response.steps_log || []
    const finalResult = response.final_result ?? ''

    const planText = plan.length > 0
      ? plan.map((step: any, idx: number) => `  ${idx + 1}. ${step.skill_id} -> ${JSON.stringify(step.input, null, 2)}`).join('\n')
      : 'No plan generated.'

    const logText = log.length > 0
      ? log.map((entry: any) => {
          if (Array.isArray(entry) && entry.length >= 2) {
            return `  - ${entry[0]}: ${entry[1]}`
          }
          return `  - ${JSON.stringify(entry)}`
        }).join('\n')
      : 'No execution log available.'

    return `Orchestrator result:\n\nPlan executed:\n${planText}\n\nExecution log:\n${logText}\n\nFinal result:\n${typeof finalResult === 'string' ? finalResult : JSON.stringify(finalResult, null, 2)}`
  }

  const handleSend = async () => {
    if (!input.trim()) return
    
    const newMessages = [...messages, { role: 'user', content: input }]
    setMessages(newMessages)
    setInput('')
    setLoading(true)
    
    try {
      if (mode === 'orchestrator') {
        const response = await testingApi.orchestrate(input)
        setMessages([...newMessages, { role: 'assistant', content: formatOrchestrateResponse(response) }])
      } else {
        const res = await testingApi.chat(newMessages, model, apiKey)
        setMessages(res.messages)
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Chat failed'
      setMessages([...newMessages, { role: 'assistant', content: `**Error:** ${errorMsg}` }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-container flex gap-6">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-[var(--bg-card)] rounded-xl border border-[var(--border)] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-[var(--border)] bg-[rgba(0,0,0,0.2)] flex justify-between items-center">
          <div>
            <h2 className="text-lg font-bold">Agent Chat</h2>
            <p className="text-xs text-[var(--text-muted)]">Interact with an autonomous agent powered by SWE skills</p>
          </div>
          <button 
            className={`btn ${showSettings ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setShowSettings(!showSettings)}
          >
            <Settings size={16} /> {showSettings ? 'Hide Settings' : 'Settings'}
          </button>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#0a0f18]">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-[var(--text-muted)] opacity-50">
              <Bot size={48} className="mb-4" />
              <p className="text-center">Start a conversation to test the agent's capabilities.</p>
              <p className="text-xs mt-2 text-center max-w-md">
                Example: "fix bug file /home/user/buggy_code.py"<br/>
                The agent will plan and execute composite skills dynamically.
              </p>
            </div>
          ) : (
            messages.filter(m => m.role !== 'system').map((msg, i) => (
              <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  msg.role === 'user' ? 'bg-[var(--accent)] text-white' : 'bg-[#1e293b] text-[var(--accent-glow)]'
                }`}>
                  {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                </div>
                <div className={`max-w-80 rounded-lg p-4 shadow-md ${
                  msg.role === 'user' 
                    ? 'bg-opacity-20 border border-[var(--accent)] border-opacity-30' 
                    : 'bg-[var(--bg-secondary)] border border-[var(--border)]'
                }`}>
                  <pre className="font-sans whitespace-pre-wrap text-sm">{msg.content}</pre>
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="flex gap-3">
               <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-[#1e293b] text-[var(--accent-glow)]">
                  <Bot size={16} />
                </div>
                <div className="max-w-80 rounded-lg p-4 shadow-md bg-[var(--bg-secondary)] border border-[var(--border)] flex items-center gap-2 text-[var(--text-muted)] text-sm">
                  <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                  Agent is thinking and executing skills...
                </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-[var(--border)] bg-[#101726]">
          <div className="flex gap-2 relative">
            <textarea
              className="form-input flex-1 pr-12 resize-none"
              placeholder="Ask the agent to perform a task..."
              rows={2}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              style={{ background: '#0a0f18', minHeight: '60px' }}
            />
            <button 
              className="absolute right-2 bottom-2 p-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white disabled:opacity-50 transition-colors"
              onClick={handleSend}
              disabled={!input.trim() || loading}
            >
              <Send size={18} />
            </button>
          </div>
          <div className="text-[10px] text-[var(--text-muted)] mt-2 flex items-center gap-1">
            <AlertCircle size={10} /> The agent will automatically discover and execute skills based on your prompt.
          </div>
        </div>
      </div>

      {/* Settings Sidebar */}
      {showSettings && (
        <div className="w-300 shrink-0 bg-[var(--bg-card)] rounded-xl border border-[var(--border)] p-5 flex flex-col gap-5 h-fit">
          <div>
            <h3 className="font-bold text-sm mb-4 border-b border-[var(--border)] pb-2">Agent Settings</h3>
            
            <div className="form-group">
              <label className="form-label">Mode</label>
              <select
                className="form-input form-select"
                value={mode}
                onChange={e => setMode(e.target.value as 'agent' | 'orchestrator')}
              >
                <option value="agent">Agent Chat</option>
                <option value="orchestrator">Orchestrator</option>
              </select>
              <p className="text-[11px] text-[var(--text-muted)] mt-1">Agent Chat sends the message to the skill agent; Orchestrator returns a plan + execution log.</p>
            </div>

            {mode === 'agent' && (
              <div className="form-group">
                <label className="form-label">Model Selection</label>
                <select 
                  className="form-input form-select" 
                  value={model} 
                  onChange={e => setModel(e.target.value)}
                >
                  <option value="deepseek-chat">DeepSeek Chat (V3)</option>
                  <option value="deepseek-reasoner">DeepSeek Reasoner (R1)</option>
                  <option value="gpt-4o">OpenAI GPT-4o</option>
                  <option value="gpt-4o-mini">OpenAI GPT-4o-mini</option>
                </select>
                <p className="text-[11px] text-[var(--text-muted)] mt-1">DeepSeek connects via api.deepseek.com</p>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">API Key</label>
              <input 
                type="password" 
                className="form-input" 
                placeholder="sk-..." 
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
              />
              <p className="text-[11px] text-[var(--text-muted)] mt-1">Key is only stored in memory during this session.</p>
            </div>
            
          </div>
          
          <div className="mt-auto pt-4 border-t border-[var(--border)]">
             <button className="btn btn-secondary w-full justify-center" onClick={() => setMessages([])}>
                Clear Chat History
             </button>
          </div>
        </div>
      )}
    </div>
  )
}
