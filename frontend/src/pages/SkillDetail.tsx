import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiErrorMessage, evaluationApi, skillsApi, SkillFeatureExtraction, SkillRead } from '../api/client'
import { ArrowLeft, Edit, Trash2, Download, CheckCircle, Save, X, RefreshCw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

export default function SkillDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [skill, setSkill] = useState<SkillRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [editedInstruction, setEditedInstruction] = useState('')
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState('')
  const [activeTab, setActiveTab] = useState<'instructions' | 'features'>('instructions')
  const [featureExtraction, setFeatureExtraction] = useState<SkillFeatureExtraction | null>(null)
  const [syncingFeatures, setSyncingFeatures] = useState(false)
  const [loadingCachedFeatures, setLoadingCachedFeatures] = useState(false)
  const [cacheChecked, setCacheChecked] = useState(false)
  const [featureError, setFeatureError] = useState('')

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(''), 3000)
  }

  const load = () => {
    if (!id) return
    setLoading(true)
    skillsApi.get(id)
      .then(setSkill)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  useEffect(() => {
    if (!skill?.raw_content) return
    let cancelled = false
    setLoadingCachedFeatures(true)
    setCacheChecked(false)
    setFeatureError('')
    evaluationApi.getCachedFeatures(skill.raw_content, 'default')
      .then((res) => {
        if (cancelled) return
        if (res.cache_complete) {
          setFeatureExtraction(res)
        } else {
          setFeatureExtraction(null)
        }
        setCacheChecked(true)
      })
      .catch((err: any) => {
        if (cancelled) return
        setFeatureError(apiErrorMessage(err, 'Feature cache lookup failed'))
        setCacheChecked(true)
      })
      .finally(() => {
        if (!cancelled) setLoadingCachedFeatures(false)
      })
    return () => { cancelled = true }
  }, [skill?.raw_content])

  const handleDelete = async () => {
    if (!skill || !confirm(`Delete skill "${skill.name}"?`)) return
    try {
      await skillsApi.delete(skill.id)
      navigate('/skills')
    } catch (e) {
      showToast('❌ Delete failed')
    }
  }

  const handleSave = async () => {
    if (!skill) return
    setSaving(true)
    try {
      await skillsApi.update(skill.id, { full_markdown: editedInstruction })
      showToast('✅ Skill updated successfully')
      setIsEditing(false)
      load()
    } catch (err: any) {
      showToast(`❌ Update failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleSyncFeatures = async () => {
    if (!skill?.raw_content) return
    setSyncingFeatures(true)
    setFeatureError('')
    try {
      const res = await evaluationApi.syncFeatures(skill.raw_content, 'default')
      setFeatureExtraction(res)
      setCacheChecked(true)
      showToast('Features synced successfully')
    } catch (err: any) {
      const message = apiErrorMessage(err, 'Feature sync failed')
      setFeatureError(message)
      showToast(`Feature sync failed: ${message}`)
    } finally {
      setSyncingFeatures(false)
    }
  }

  if (loading) return <div className="loading-center"><div className="spinner" /></div>
  if (!skill) return <div className="empty-state">Skill not found</div>

  const stripFrontmatter = (content: string) => {
    return content.replace(/^---[\s\S]*?---\s*/, '')
  }

  const renderedContent = stripFrontmatter(skill.raw_content || '')

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <button className="btn btn-ghost" onClick={() => navigate('/skills')}>
          <ArrowLeft size={16} /> Back
        </button>
        <div className="flex-1">
          <h2 style={{ fontSize: 24, fontWeight: 700, margin: 0, fontFamily: 'var(--font-mono)' }}>{skill.name}</h2>
          <div className="flex gap-2 items-center mt-1">
            <span className={`badge badge-${skill.level}`}>{skill.level}</span>
            <span className="text-sm text-muted">{skill.category}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <a className="btn btn-secondary" href={skillsApi.exportUrl(skill.id)} download>
            <Download size={14} /> Export
          </a>
          <button className="btn btn-danger" onClick={handleDelete}>
            <Trash2 size={14} /> Delete
          </button>
        </div>
      </div>

      <div className="grid-3" style={{ gridTemplateColumns: '2fr 1fr' }}>
        <div className="flex" style={{ flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="flex justify-between items-center mb-3">
              <div>
                <h3 className="font-bold text-sm">Skill Detail</h3>
                <div className="tabs mt-3">
                  <button className={`tab ${activeTab === 'instructions' ? 'active' : ''}`} onClick={() => setActiveTab('instructions')}>Instructions</button>
                  <button className={`tab ${activeTab === 'features' ? 'active' : ''}`} onClick={() => setActiveTab('features')}>Extracted Features</button>
                </div>
              </div>
              <div className="flex gap-2">
                {activeTab === 'instructions' ? (
                  <>
                    <button
                      className={`btn btn-sm ${isEditing ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => {
                        if (isEditing) {
                          handleSave()
                        } else {
                          setEditedInstruction(skill.raw_content)
                          setIsEditing(true)
                        }
                      }}
                      disabled={saving}
                    >
                      {isEditing ? (saving ? 'Saving...' : <><Save size={12} /> Save</>) : <><Edit size={12} /> Edit</>}
                    </button>
                    {isEditing && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setIsEditing(false)}
                        disabled={saving}
                      >
                        <X size={12} /> Cancel
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={handleSyncFeatures}
                    disabled={syncingFeatures}
                  >
                    <RefreshCw size={12} /> {syncingFeatures ? 'Syncing...' : 'Sync'}
                  </button>
                )}
              </div>
            </div>

            {activeTab === 'features' ? (
              <FeatureExtractionPanel
                extraction={featureExtraction}
                error={featureError}
                syncing={syncingFeatures}
                loadingCache={loadingCachedFeatures}
                cacheChecked={cacheChecked}
                onSync={handleSyncFeatures}
              />
            ) : isEditing ? (
              <textarea
                className="form-input form-textarea"
                value={editedInstruction}
                onChange={e => setEditedInstruction(e.target.value)}
                style={{ minHeight: 600, fontFamily: 'var(--font-mono)', fontSize: 13, background: 'rgba(0,0,0,0.3)', color: '#fff' }}
                placeholder="Enter full SKILL.md content..."
              />
            ) : (
              <div className="markdown-container">
                <div className="markdown-body">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ inline, className, children, ...props }: any) {
                        const match = /language-(\w+)/.exec(className || '')
                        return !inline && match ? (
                          <SyntaxHighlighter
                            style={vscDarkPlus as any}
                            language={match[1]}
                            PreTag="div"
                            {...props}
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        ) : (
                          <code className={className} {...props}>
                            {children}
                          </code>
                        )
                      }
                    }}
                  >
                    {renderedContent || 'No content found.'}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-bold text-sm">Action Shortcuts</h3>
            </div>
            <div className="flex gap-3">
              <button className="btn btn-primary" onClick={() => navigate('/evaluation', { state: { skillId: skill.id } })}>
                <CheckCircle size={14} /> Evaluate
              </button>
            </div>
          </div>
        </div>

        <div className="flex" style={{ flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <h3 className="font-bold text-sm mb-3">Metadata</h3>
            <div className="mb-3">
              <div className="text-xs text-muted mb-1 uppercase tracking-wider">Description</div>
              <div className="text-sm">{skill.metadata?.description || '—'}</div>
            </div>
            {skill.metadata?.goal && (
              <div className="mb-3">
                <div className="text-xs text-muted mb-1 uppercase tracking-wider">Goal</div>
                <div className="text-sm">{skill.metadata.goal}</div>
              </div>
            )}
            <div className="mb-3">
              <div className="text-xs text-muted mb-1 uppercase tracking-wider">Tags</div>
              <div className="flex flex-wrap gap-2 mt-1">
                {skill.tags.map((t: string) => <span key={t} className="badge badge-tag">{t}</span>)}
              </div>
            </div>
            {(skill.metadata?.sub_skills || []).length > 0 && (
              <div className="mb-3">
                <div className="text-xs text-muted mb-1 uppercase tracking-wider">Sub Skills</div>
                <div className="flex flex-col gap-1 mt-1">
                  {(skill.metadata.sub_skills || []).map((s: string) => <div key={s} className="text-sm font-mono text-accent">{s}</div>)}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}

function FeatureExtractionPanel({
  extraction,
  error,
  syncing,
  loadingCache,
  cacheChecked,
  onSync,
}: {
  extraction: SkillFeatureExtraction | null
  error: string
  syncing: boolean
  loadingCache: boolean
  cacheChecked: boolean
  onSync: () => void
}) {
  if ((loadingCache || syncing) && !extraction) {
    return (
      <div className="loading-center" style={{ minHeight: 240, flexDirection: 'column', gap: 12 }}>
        <div className="spinner" />
        <div className="text-sm text-muted">{loadingCache ? 'Loading cached features...' : 'Syncing features...'}</div>
      </div>
    )
  }

  return (
    <div>
      {error && (
        <div className="card mb-4" style={{ borderColor: 'var(--red)', background: 'rgba(248,113,113,0.05)' }}>
          <div className="font-bold text-sm text-red">Feature sync failed</div>
          <p className="text-sm mt-2">{error}</p>
        </div>
      )}

      {!extraction ? (
        <div className="empty-state">
          <p className="mb-4">
            {cacheChecked ? 'No complete cached feature snapshot yet.' : 'Feature cache has not been checked yet.'}
          </p>
          <button className="btn btn-primary" onClick={onSync} disabled={syncing}>
            <RefreshCw size={14} /> Sync Features
          </button>
        </div>
      ) : (
        <div className="flex" style={{ flexDirection: 'column', gap: 16 }}>
          <div className="flex flex-wrap gap-2">
            <span className="badge badge-pass">Model: {extraction.model}</span>
            <span className="badge badge-tag">Profile: {extraction.profile_id}</span>
            <span className="badge badge-tag">Hash: {extraction.profile_hash.slice(0, 12)}</span>
          </div>

          <FeatureTable
            title="Format Features"
            features={extraction.format_features}
            evidence={extraction.format_feature_evidence}
          />
          <FeatureTable
            title="Content Features"
            features={extraction.content_features}
            evidence={extraction.content_feature_evidence}
          />
          <SyncLog logs={extraction.sync_log || []} />
        </div>
      )}
    </div>
  )
}

function FeatureTable({
  title,
  features,
  evidence,
}: {
  title: string
  features: Record<string, any>
  evidence: Record<string, any>
}) {
  return (
    <div>
      <h4 className="font-bold text-sm mb-3">{title}</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Feature</th>
              <th>Value</th>
              <th>Confidence</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(features).map(([key, value]) => {
              const item = evidence[key] || {}
              return (
                <tr key={key}>
                  <td><code className="font-mono text-accent">{key}</code></td>
                  <td><code>{String(value)}</code></td>
                  <td>{typeof item.confidence === 'number' ? Math.round(item.confidence * 100) + '%' : '—'}</td>
                  <td className="text-sm text-muted">{item.evidence || item.source || '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SyncLog({ logs }: { logs: Record<string, any>[] }) {
  if (!logs.length) return null
  return (
    <div>
      <h4 className="font-bold text-sm mb-3">Sync Log</h4>
      <div className="card" style={{ background: 'rgba(15,23,42,0.25)' }}>
        {logs.map((item, index) => (
          <div key={index} className="text-xs font-mono mb-2">
            {item.feature ? `[${item.status}] ${item.feature}` : item.message || JSON.stringify(item)}
          </div>
        ))}
      </div>
    </div>
  )
}
