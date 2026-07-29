import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiErrorMessage, evaluationApi, FeatureDefinition, skillsApi, SkillSummary } from '../api/client'
import { Search, Plus, Upload, RefreshCw, X, Folder, FolderOpen, FileText, Play, CheckCircle } from 'lucide-react'

interface TreeNode {
  name: string
  skills: SkillSummary[]
  children: { [key: string]: TreeNode }
}

type BatchSyncStatus = 'pending' | 'checking_cache' | 'cache_hit' | 'llm_calling' | 'success' | 'fail'

interface BatchSyncItem {
  skill: SkillSummary
  status: BatchSyncStatus
  message?: string
}

interface FeatureViewItem {
  skill: SkillSummary
  cacheComplete: boolean
  features: Record<string, any> | null
  error?: string
}

function buildTree(skills: SkillSummary[]): TreeNode {
  const root: TreeNode = { name: 'Root', skills: [], children: {} }
  
  skills.forEach(skill => {
    const parts = skill.category.split('/')
    let current = root
    parts.forEach(part => {
      if (!current.children[part]) {
        current.children[part] = { name: part, skills: [], children: {} }
      }
      current = current.children[part]
    })
    current.skills.push(skill)
  })
  
  return root
}

export default function SkillBrowser() {
  const [skills, setSkills] = useState<SkillSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQ, setSearchQ] = useState('')
  const [searching, setSearching] = useState(false)
  const [filterLevel, setFilterLevel] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [importing, setImporting] = useState(false)
  const [toast, setToast] = useState('')
  const [viewMode, setViewMode] = useState<'list' | 'grid' | 'tree' | 'features'>('list')
  const [currentPage, setCurrentPage] = useState(1)
  const [showFeatureSync, setShowFeatureSync] = useState(false)
  const [featureDefinitions, setFeatureDefinitions] = useState<FeatureDefinition[]>([])
  const [featureRows, setFeatureRows] = useState<FeatureViewItem[]>([])
  const [loadingFeatureView, setLoadingFeatureView] = useState(false)
  const [featureViewError, setFeatureViewError] = useState('')
  const pageSize = 10
  const navigate = useNavigate()

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(''), 3000)
  }

  const load = useCallback(() => {
    setLoading(true)
    skillsApi.list({ level: filterLevel || undefined, category: filterCategory || undefined })
      .then(d => setSkills(d.items))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [filterLevel, filterCategory])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    setCurrentPage(1)
  }, [searchQ, filterLevel, filterCategory, skills])

  const handleSearch = async () => {
    if (!searchQ.trim()) return load()
    setSearching(true)
    try {
      const res = await skillsApi.search(searchQ, 100)
      setSkills(res.results.map(r => r.skill))
    } finally {
      setSearching(false)
    }
  }

  const filteredSkills = skills.filter(skill => {
    const q = searchQ.toLowerCase().trim()
    if (!q) return true
    return (
      skill.name.toLowerCase().includes(q) ||
      (skill.description && skill.description.toLowerCase().includes(q)) ||
      skill.category.toLowerCase().includes(q) ||
      skill.tags.some(t => t.toLowerCase().includes(q))
    )
  })

  const totalPages = Math.ceil(filteredSkills.length / pageSize)
  const startIndex = (currentPage - 1) * pageSize
  const paginatedSkills = filteredSkills.slice(startIndex, startIndex + pageSize)

  const getPaginationGroup = () => {
    let pages = []
    for (let i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || (i >= currentPage - 1 && i <= currentPage + 1)) {
        pages.push(i)
      } else if (i === 2 && currentPage > 3) {
        pages.push('ellipsis-start')
      } else if (i === totalPages - 1 && currentPage < totalPages - 2) {
        pages.push('ellipsis-end')
      }
    }
    const result: (number | string)[] = []
    pages.forEach(p => {
      if (typeof p === 'string') {
        if (result[result.length - 1] !== '...') {
          result.push('...')
        }
      } else {
        result.push(p)
      }
    })
    return result
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    try {
      await skillsApi.importFile(file)
      showToast('✅ Skill imported successfully')
      load()
    } catch (err: any) {
      showToast(`❌ Import failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setImporting(false)
      e.target.value = ''
    }
  }

  const handleDelete = async (id: string, name: string, ev: React.MouseEvent) => {
    ev.stopPropagation()
    if (!confirm(`Delete skill "${name}"?`)) return
    try {
      await skillsApi.delete(id)
      showToast('Skill deleted')
      load()
    } catch { showToast('Delete failed') }
  }

  const categories = [...new Set(skills.map(s => s.category))].sort()

  const loadFeatureView = useCallback(async () => {
    setLoadingFeatureView(true)
    setFeatureViewError('')
    try {
      const [profile, list] = await Promise.all([
        evaluationApi.getDefaultProfile(),
        skillsApi.list(),
      ])
      setFeatureDefinitions(profile.features)
      const rows = await Promise.all(list.items.map(async (skill): Promise<FeatureViewItem> => {
        try {
          const detail = await skillsApi.get(skill.id)
          const cached = await evaluationApi.getCachedFeatures(detail.raw_content, profile.id)
          return {
            skill,
            cacheComplete: Boolean(cached.cache_complete),
            features: cached.cache_complete ? cached.content_features : null,
          }
        } catch (err: any) {
          return {
            skill,
            cacheComplete: false,
            features: null,
            error: apiErrorMessage(err, 'Feature cache lookup failed'),
          }
        }
      }))
      setFeatureRows(rows)
    } catch (err: any) {
      setFeatureViewError(apiErrorMessage(err, 'Could not load feature distributions'))
    } finally {
      setLoadingFeatureView(false)
    }
  }, [])

  useEffect(() => {
    if (viewMode === 'features') {
      loadFeatureView()
    }
  }, [viewMode, loadFeatureView])

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h2>Skill Browser</h2>
          <p>Browse and manage your skill library</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-secondary btn-sm" onClick={() => setShowFeatureSync(true)}>
            <RefreshCw size={13} /> Sync Features
          </button>
          <label className="btn btn-secondary btn-sm" style={{ cursor: importing ? 'not-allowed' : 'pointer' }}>
            <Upload size={13} /> {importing ? 'Importing...' : 'Import .md'}
            <input type="file" accept=".md" style={{ display: 'none' }} onChange={handleImport} />
          </label>
          <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>
            <Plus size={13} /> New Skill
          </button>
        </div>
      </div>

      {/* View Mode Toggle */}
      <div className="flex gap-2 mb-4">
        <button 
          className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-secondary'}`} 
          onClick={() => setViewMode('list')}
        >
          List View
        </button>
        <button 
          className={`btn btn-sm ${viewMode === 'grid' ? 'btn-primary' : 'btn-secondary'}`} 
          onClick={() => setViewMode('grid')}
        >
          Grid View
        </button>
        <button 
          className={`btn btn-sm ${viewMode === 'tree' ? 'btn-primary' : 'btn-secondary'}`} 
          onClick={() => setViewMode('tree')}
        >
          Hierarchy View
        </button>
        <button
          className={`btn btn-sm ${viewMode === 'features' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setViewMode('features')}
        >
          Feature View
        </button>
      </div>

      {/* Search + Filters */}
      <div className="flex gap-3 mb-6" style={{ flexWrap: 'wrap' }}>
        <div className="search-bar" style={{ flex: '1 1 300px' }}>
          <Search size={14} className="search-icon" />
          <input
            placeholder="Search skills by name, description, tags..."
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <select className="form-input form-select" style={{ width: 160 }}
          value={filterLevel} onChange={e => { setFilterLevel(e.target.value); setSearchQ('') }}>
          <option value="">All Levels</option>
          <option value="atomic">Atomic</option>
          <option value="composite">Composite</option>
        </select>
        <select className="form-input form-select" style={{ width: 200 }}
          value={filterCategory} onChange={e => { setFilterCategory(e.target.value); setSearchQ('') }}>
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="btn btn-secondary btn-sm" onClick={() => { setSearchQ(''); setFilterLevel(''); setFilterCategory(''); load() }}>
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Content */}
      {loading || searching ? (
        <div className="loading-center"><div className="spinner" /></div>
      ) : filteredSkills.length === 0 ? (
        <div className="empty-state">
          <h3>No skills found</h3>
          <p>Import a SKILL.md file or create a new skill to get started.</p>
        </div>
      ) : viewMode === 'features' ? (
        <FeatureDistributionView
          features={featureDefinitions}
          rows={featureRows}
          loading={loadingFeatureView}
          error={featureViewError}
          onRefresh={loadFeatureView}
        />
      ) : viewMode === 'list' ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: '20%' }}>Name</th>
                <th style={{ width: '12%' }}>Level</th>
                <th>Description</th>
                <th style={{ width: '15%' }}>Category</th>
                <th style={{ width: '20%' }}>Tags</th>
                <th style={{ width: '8%', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {paginatedSkills.map(skill => (
                <tr key={skill.id} onClick={() => navigate(`/skills/${skill.id}`)} style={{ cursor: 'pointer' }}>
                  <td>
                    <div className="flex flex-col">
                      <span className="font-mono font-bold text-accent" style={{ fontSize: '13.5px' }}>{skill.name}</span>
                      <span className="text-xs text-muted mt-1">v{skill.version}</span>
                    </div>
                  </td>
                  <td>
                    <span className={`badge badge-${skill.level}`}>{skill.level}</span>
                  </td>
                  <td>
                    <span className="text-sm text-secondary" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: 1.4 }}>
                      {skill.description}
                    </span>
                  </td>
                  <td>
                    <span className="text-sm text-secondary font-mono" style={{ fontSize: '12px' }}>{skill.category}</span>
                  </td>
                  <td>
                    <div className="flex gap-1 flex-wrap">
                      {skill.tags.slice(0, 3).map(t => (
                        <span key={t} className="badge badge-tag">{t}</span>
                      ))}
                      {skill.tags.length > 3 && <span className="badge badge-tag">+{skill.tags.length - 3}</span>}
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div className="flex gap-2 justify-end" onClick={e => e.stopPropagation()}>
                      <button className="btn btn-ghost btn-sm text-red" style={{ padding: '4px 8px' }}
                        onClick={e => handleDelete(skill.id, skill.name, e)}>
                        <X size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="skill-grid">
          {paginatedSkills.map(skill => (
            <div key={skill.id} className="skill-card" onClick={() => navigate(`/skills/${skill.id}`)}>
              <div className="skill-card-header">
                <span className="skill-card-name">{skill.name}</span>
                <span className={`badge badge-${skill.level}`}>{skill.level}</span>
              </div>
              <p className="skill-card-desc">{skill.description}</p>
              <div className="skill-card-meta">
                {skill.tags.slice(0, 4).map(t => (
                  <span key={t} className="badge badge-tag">{t}</span>
                ))}
                {skill.tags.length > 4 && <span className="badge badge-tag">+{skill.tags.length - 4}</span>}
              </div>
              <div className="skill-card-footer">
                <span className="skill-card-category">{skill.category}</span>
                <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                  <span className="text-xs text-muted">v{skill.version}</span>
                  <button className="btn btn-ghost btn-sm text-red" style={{ padding: '2px 6px' }}
                    onClick={e => handleDelete(skill.id, skill.name, e)}>
                    <X size={12} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <TreeView skills={filteredSkills} navigate={navigate} />
      )}

      {/* Pagination Controls */}
      {viewMode !== 'tree' && viewMode !== 'features' && totalPages > 1 && (
        <div className="flex justify-between items-center mt-6 p-4 card" style={{ background: 'var(--bg-secondary)', padding: '12px 24px' }}>
          <span className="text-xs text-secondary">
            Showing <strong className="text-primary">{startIndex + 1}</strong> to <strong className="text-primary">{Math.min(startIndex + pageSize, filteredSkills.length)}</strong> of <strong className="text-primary">{filteredSkills.length}</strong> skills
          </span>
          <div className="flex gap-2 items-center">
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
              disabled={currentPage === 1}
            >
              Previous
            </button>
            
            {getPaginationGroup().map((page, index) => {
              if (page === '...') {
                return <span key={`ellipsis-${index}`} className="text-muted px-1" style={{ display: 'flex', alignItems: 'center' }}>...</span>
              }
              return (
                <button
                  key={page}
                  className={`btn btn-sm ${currentPage === page ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ minWidth: 32, padding: '4px 8px', justifyContent: 'center' }}
                  onClick={() => setCurrentPage(page as number)}
                >
                  {page}
                </button>
              )
            })}
            
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
              disabled={currentPage === totalPages}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {showCreate && <CreateSkillModal onClose={() => setShowCreate(false)} onCreated={() => { load(); setShowCreate(false); showToast('✅ Skill created!') }} />}
      {showFeatureSync && <FeatureSyncModal onClose={() => setShowFeatureSync(false)} />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}

function FeatureSyncModal({ onClose }: { onClose: () => void }) {
  const [items, setItems] = useState<BatchSyncItem[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    skillsApi.list()
      .then((res) => {
        if (cancelled) return
        setItems(res.items.map((skill) => ({ skill, status: 'pending' })))
      })
      .catch((err: any) => {
        if (!cancelled) setError(apiErrorMessage(err, 'Could not load skills'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const updateItem = (skillId: string, patch: Partial<BatchSyncItem>) => {
    setItems(prev => prev.map(item => item.skill.id === skillId ? { ...item, ...patch } : item))
  }

  const startSync = async () => {
    if (running) return
    setRunning(true)
    setError('')
    for (const item of items) {
      updateItem(item.skill.id, { status: 'checking_cache', message: 'Checking cache...' })
      try {
        const detail = await skillsApi.get(item.skill.id)
        const cached = await evaluationApi.getCachedFeatures(detail.raw_content, 'default')
        if (cached.cache_complete) {
          updateItem(item.skill.id, { status: 'cache_hit', message: 'Cache hit' })
          continue
        }
        updateItem(item.skill.id, { status: 'llm_calling', message: 'LLM calling...' })
        await evaluationApi.syncFeatures(detail.raw_content, 'default')
        updateItem(item.skill.id, { status: 'success', message: 'Success' })
      } catch (err: any) {
        updateItem(item.skill.id, { status: 'fail', message: apiErrorMessage(err, 'Sync failed') })
      }
    }
    setRunning(false)
  }

  const counts = items.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1
    return acc
  }, {} as Record<BatchSyncStatus, number>)
  const done = (counts.cache_hit || 0) + (counts.success || 0) + (counts.fail || 0)

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
      <div className="card" style={{ width: '100%', maxWidth: 780, maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold">Sync Features</h3>
            <p className="text-sm text-muted mt-1">Runs sequentially across the full skill library. Cache hits do not call the LLM.</p>
          </div>
          <button className="btn btn-ghost" onClick={onClose} disabled={running}><X size={16} /></button>
        </div>

        <div className="flex justify-between items-center mb-4">
          <div className="flex gap-2 flex-wrap">
            <span className="badge badge-tag">{items.length} skills</span>
            <span className="badge badge-tag">{done} done</span>
            <span className="badge badge-pass">{counts.cache_hit || 0} cache hit</span>
            <span className="badge badge-pass">{counts.success || 0} success</span>
            <span className="badge badge-fail">{counts.fail || 0} fail</span>
          </div>
          <button className="btn btn-primary btn-sm" onClick={startSync} disabled={loading || running || items.length === 0}>
            {running ? <RefreshCw size={13} /> : <Play size={13} />} {running ? 'Syncing...' : 'Start Sync'}
          </button>
        </div>

        {error && (
          <div className="card mb-4" style={{ borderColor: 'var(--red)', background: 'rgba(248,113,113,0.05)' }}>
            <p className="text-sm text-red">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="loading-center" style={{ minHeight: 240 }}><div className="spinner" /></div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Skill</th>
                  <th style={{ width: 180 }}>Status</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.skill.id}>
                    <td><span className="font-mono font-bold text-accent">{item.skill.name}</span></td>
                    <td><BatchSyncBadge status={item.status} /></td>
                    <td className="text-sm text-muted">{item.message || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function BatchSyncBadge({ status }: { status: BatchSyncStatus }) {
  const label: Record<BatchSyncStatus, string> = {
    pending: 'Pending',
    checking_cache: 'Checking cache',
    cache_hit: 'Cache hit',
    llm_calling: 'LLM calling',
    success: 'Success',
    fail: 'Fail',
  }
  const className = status === 'fail'
    ? 'badge badge-fail'
    : status === 'success' || status === 'cache_hit'
      ? 'badge badge-pass'
      : 'badge badge-tag'
  return (
    <span className={className}>
      {status === 'success' || status === 'cache_hit' ? <CheckCircle size={12} /> : null}
      {label[status]}
    </span>
  )
}

function FeatureDistributionView({
  features,
  rows,
  loading,
  error,
  onRefresh,
}: {
  features: FeatureDefinition[]
  rows: FeatureViewItem[]
  loading: boolean
  error: string
  onRefresh: () => void
}) {
  const cachedCount = rows.filter(row => row.cacheComplete).length
  const failedCount = rows.filter(row => row.error).length
  const missingCount = Math.max(0, rows.length - cachedCount - failedCount)

  if (loading && rows.length === 0) {
    return <div className="loading-center"><div className="spinner" /></div>
  }

  return (
    <div className="flex" style={{ flexDirection: 'column', gap: 16 }}>
      <div className="card">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="font-bold text-sm">Feature Distribution</h3>
            <p className="text-sm text-muted mt-1">Visualizes cached content features across the skill library. This view does not call the LLM.</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={13} /> {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
        <div className="flex gap-2 flex-wrap mt-4">
          <span className="badge badge-tag">{rows.length} skills</span>
          <span className="badge badge-pass">{cachedCount} cached</span>
          <span className="badge badge-tag">{missingCount} missing cache</span>
          <span className="badge badge-fail">{failedCount} failed</span>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--red)', background: 'rgba(248,113,113,0.05)' }}>
          <p className="text-sm text-red">{error}</p>
        </div>
      )}

      {features.length === 0 ? (
        <div className="empty-state">No feature definitions found.</div>
      ) : (
        <div className="feature-distribution-grid">
          {features.map(feature => (
            <FeatureDistributionCard key={feature.id} feature={feature} rows={rows} />
          ))}
        </div>
      )}
    </div>
  )
}

function FeatureDistributionCard({ feature, rows }: { feature: FeatureDefinition; rows: FeatureViewItem[] }) {
  const values = rows
    .filter(row => row.cacheComplete && row.features && Object.prototype.hasOwnProperty.call(row.features, feature.id))
    .map(row => row.features?.[feature.id])
  const missing = Math.max(0, rows.length - values.length)

  if (feature.type === 'boolean') {
    const trueCount = values.filter(Boolean).length
    const falseCount = values.length - trueCount
    const total = Math.max(1, rows.length)
    return (
      <div className="card feature-distribution-card">
        <div className="flex justify-between items-start gap-3 mb-3">
          <div>
            <h4 className="font-mono text-accent" style={{ fontSize: 14 }}>{feature.id}</h4>
            <div className="text-xs text-muted mt-1">boolean</div>
          </div>
          <span className="badge badge-tag">{values.length}/{rows.length}</span>
        </div>
        <StackedBar
          segments={[
            { label: 'true', value: trueCount, color: 'var(--green)' },
            { label: 'false', value: falseCount, color: 'var(--red)' },
            { label: 'missing', value: missing, color: 'var(--text-muted)' },
          ]}
          total={total}
        />
        <div className="feature-stat-row"><span>true</span><strong>{trueCount}</strong></div>
        <div className="feature-stat-row"><span>false</span><strong>{falseCount}</strong></div>
        <div className="feature-stat-row"><span>missing cache</span><strong>{missing}</strong></div>
      </div>
    )
  }

  const numericValues = values.map(value => Number(value)).filter(value => Number.isFinite(value))
  const min = numericValues.length ? Math.min(...numericValues) : 0
  const max = numericValues.length ? Math.max(...numericValues) : 0
  const avg = numericValues.length ? numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length : 0
  const buckets = buildIntegerBuckets(numericValues)

  return (
    <div className="card feature-distribution-card">
      <div className="flex justify-between items-start gap-3 mb-3">
        <div>
          <h4 className="font-mono text-accent" style={{ fontSize: 14 }}>{feature.id}</h4>
          <div className="text-xs text-muted mt-1">integer</div>
        </div>
        <span className="badge badge-tag">{numericValues.length}/{rows.length}</span>
      </div>
      <div className="feature-stat-grid">
        <div><span>min</span><strong>{formatNumber(min)}</strong></div>
        <div><span>avg</span><strong>{formatNumber(avg)}</strong></div>
        <div><span>max</span><strong>{formatNumber(max)}</strong></div>
      </div>
      <div className="mini-histogram">
        {buckets.map(bucket => (
          <div key={bucket.label} className="mini-histogram-row">
            <span>{bucket.label}</span>
            <div className="mini-histogram-track">
              <div style={{ width: `${bucket.percent}%` }} />
            </div>
            <strong>{bucket.count}</strong>
          </div>
        ))}
      </div>
      {missing > 0 && <div className="feature-stat-row mt-2"><span>missing cache</span><strong>{missing}</strong></div>}
    </div>
  )
}

function StackedBar({
  segments,
  total,
}: {
  segments: { label: string; value: number; color: string }[]
  total: number
}) {
  return (
    <div className="stacked-bar" title={segments.map(segment => `${segment.label}: ${segment.value}`).join(', ')}>
      {segments.filter(segment => segment.value > 0).map(segment => (
        <div
          key={segment.label}
          style={{ width: `${(segment.value / total) * 100}%`, background: segment.color }}
        />
      ))}
    </div>
  )
}

function buildIntegerBuckets(values: number[]) {
  if (!values.length) return [{ label: 'no data', count: 0, percent: 0 }]
  const counts = new Map<number, number>()
  values.forEach(value => counts.set(value, (counts.get(value) || 0) + 1))
  const sorted = [...counts.entries()].sort((a, b) => a[0] - b[0])
  const maxCount = Math.max(...sorted.map(([, count]) => count), 1)
  const compact = sorted.length > 8
    ? sorted.slice(0, 7).concat([[Number.NaN, sorted.slice(7).reduce((sum, [, count]) => sum + count, 0)]])
    : sorted
  return compact.map(([value, count]) => ({
    label: Number.isNaN(value) ? 'other' : String(value),
    count,
    percent: (count / maxCount) * 100,
  }))
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function TreeView({ skills, navigate }: { skills: SkillSummary[], navigate: any }) {
  const tree = buildTree(skills)
  
  return (
    <div className="card" style={{ background: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(12px)' }}>
      <h3 className="font-bold text-sm mb-4 border-b border-[rgba(255,255,255,0.08)] pb-2">Skill Hierarchy</h3>
      <div className="pl-2">
        {Object.values(tree.children).map(node => (
          <TreeNodeView key={node.name} node={node} level={0} navigate={navigate} />
        ))}
      </div>
    </div>
  )
}

function TreeNodeView({ node, level, navigate }: { node: TreeNode, level: number, navigate: any }) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = Object.keys(node.children).length > 0 || node.skills.length > 0
  
  return (
    <div style={{ marginLeft: level > 0 ? 20 : 0 }}>
      <div 
        className="flex items-center gap-2 py-2 cursor-pointer hover:text-accent transition-colors"
        onClick={() => setExpanded(!expanded)}
        style={{ fontSize: 15 }}
      >
        <span className="text-muted" style={{ width: 16, display: 'inline-block' }}>
          {hasChildren ? (expanded ? '▼' : '▶') : ' '}
        </span>
        {hasChildren ? (
          expanded ? <FolderOpen size={16} className="text-yellow-400" /> : <Folder size={16} className="text-yellow-400" />
        ) : (
          <Folder size={16} className="text-yellow-400" />
        )}
        <span className="font-semibold text-slate-200">{node.name}</span>
      </div>
      
      {expanded && (
        <div className="border-l border-[rgba(255,255,255,0.05)] ml-2">
          {Object.values(node.children).map(child => (
            <TreeNodeView key={child.name} node={child} level={level + 1} navigate={navigate} />
          ))}
          {node.skills.map(skill => (
            <div 
              key={skill.id} 
              className="flex items-center gap-2 py-2 cursor-pointer hover:bg-[rgba(255,255,255,0.02)] pl-6 transition-colors"
              onClick={() => navigate(`/skills/${skill.id}`)}
              style={{ fontSize: 14 }}
            >
              <FileText size={14} className="text-cyan-400" />
              <span className="text-slate-300">{skill.name}</span>
              <span className={`badge badge-${skill.level} text-xs`} style={{ transform: 'scale(0.8)' }}>{skill.level}</span>
              <span className="text-xs text-muted ml-auto">{(skill.description || '').slice(0, 60)}...</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CreateSkillModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    name: '', description: '', version: '1.0.0', level: 'atomic',
    category: '', goal: '', tags: '', instruction: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    setLoading(true); setError('')
    try {
      await skillsApi.create({
        metadata: {
          name: form.name, description: form.description, version: form.version,
          level: form.level as 'atomic' | 'composite', category: form.category,
          goal: form.goal || undefined,
          tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
          sub_skills: [],
        },
        instruction: form.instruction,
      })
      onCreated()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create skill')
    } finally { setLoading(false) }
  }

  const f = (k: string) => (e: React.ChangeEvent<any>) => setForm(p => ({ ...p, [k]: e.target.value }))

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
      <div className="card" style={{ width: '100%', maxWidth: 560, maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold">Create New Skill</h3>
          <button className="btn btn-ghost" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">Name *</label>
            <input className="form-input" placeholder="e.g. debug-python-error" value={form.name} onChange={f('name')} />
          </div>
          <div className="form-group">
            <label className="form-label">Version</label>
            <input className="form-input" value={form.version} onChange={f('version')} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Description *</label>
          <input className="form-input" placeholder="Brief description of what this skill does" value={form.description} onChange={f('description')} />
        </div>
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">Category *</label>
            <input className="form-input" placeholder="e.g. python/debugging" value={form.category} onChange={f('category')} />
          </div>
          <div className="form-group">
            <label className="form-label">Level</label>
            <select className="form-input form-select" value={form.level} onChange={f('level')}>
              <option value="atomic">Atomic</option>
              <option value="composite">Composite</option>
            </select>
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Goal</label>
          <input className="form-input" placeholder="Specific goal of this skill" value={form.goal} onChange={f('goal')} />
        </div>
        <div className="form-group">
          <label className="form-label">Tags (comma separated)</label>
          <input className="form-input" placeholder="python, debug, error" value={form.tags} onChange={f('tags')} />
        </div>
        <div className="form-group">
          <label className="form-label">Instructions *</label>
          <textarea className="form-input form-textarea" placeholder="Step-by-step instructions for the AI agent..." value={form.instruction} onChange={f('instruction')} style={{ minHeight: 140 }} />
        </div>
        {error && <p style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{error}</p>}
        <div className="flex gap-2">
          <button className="btn btn-secondary flex-1" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary flex-1" onClick={submit} disabled={loading || !form.name || !form.description || !form.category || !form.instruction}>
            {loading ? 'Creating...' : 'Create Skill'}
          </button>
        </div>
      </div>
    </div>
  )
}
