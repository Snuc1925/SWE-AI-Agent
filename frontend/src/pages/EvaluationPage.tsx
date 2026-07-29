import { ChangeEvent, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { CheckCircle, Download, FileUp, Plus, Play, Save, Sparkles, Trash2, UploadCloud, XCircle, Pencil, Check, X, ChevronDown, ChevronRight } from 'lucide-react'

import {
  Condition,
  ConditionOperator,
  CriterionDefinition,
  EvaluationProfile,
  FeatureDefinition,
  FeatureType,
  LlmConfig,
  RuleAction,
  RuleStep,
  evaluationApi,
  FeatureEvidence,
  SkillFeatureExtraction,
  SkillMarkdownEvaluation,
  apiErrorMessage,
  skillsApi,
} from '../api/client'

type InputMode = 'upload' | 'paste'
type ProfileTab = 'features' | 'bucket' | 'criteria' | 'model'

const FEATURE_TYPES: FeatureType[] = ['boolean', 'integer']
const OPERATORS: ConditionOperator[] = ['exists', 'missing', 'eq', 'neq', 'lt', 'lte', 'gt', 'gte']
const ACTIONS: RuleAction[] = ['force_score', 'set_score_from_bucket', 'add', 'subtract', 'cap_max', 'set_baseline']

const defaultLlmConfig = (): LlmConfig => ({
  provider: 'openai-compatible',
  base_url: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat',
  api_key: '',
})

const emptyFeature = (): FeatureDefinition => ({
  id: 'new_feature',
  type: 'boolean',
  extraction_guidance: '',
})

const emptyCondition = (featureId = ''): Condition => ({
  feature: featureId,
  operator: 'eq',
  value: false,
})

const emptyStep = (featureId = ''): RuleStep => ({
  id: 'new_rule_step',
  description: '',
  condition: emptyCondition(featureId),
  action: 'add',
  value: 1,
})

const emptyCriterion = (): CriterionDefinition => ({
  id: 'new_criterion',
  label: 'New Criterion',
  max_score: 10,
  steps: [],
})

const cloneProfile = (profile: EvaluationProfile): EvaluationProfile => JSON.parse(JSON.stringify(profile))

function parseValue(value: string, featureType?: FeatureType) {
  if (featureType === 'boolean') return value === 'true'
  if (featureType === 'integer') return Number.parseInt(value || '0', 10)
  return Number.parseInt(value || '0', 10)
}

function valueToInput(value: any) {
  if (value && typeof value === 'object') {
    return JSON.stringify(value)
  }
  return value === undefined ? '' : String(value)
}

export default function EvaluationPage() {
  const location = useLocation()
  const initialSkillId = location.state?.skillId || ''

  const [mode, setMode] = useState<InputMode>('upload')
  const [pageTab, setPageTab] = useState<'evaluation' | 'config'>('evaluation')
  const [profileTab, setProfileTab] = useState<ProfileTab>('features')
  const [editingFeature, setEditingFeature] = useState<{ index: number; feature: FeatureDefinition } | null>(null)
  const [markdown, setMarkdown] = useState('')
  const [fileName, setFileName] = useState('')
  const [profile, setProfile] = useState<EvaluationProfile | null>(null)
  const [savedProfile, setSavedProfile] = useState<EvaluationProfile | null>(null)
  const [extraction, setExtraction] = useState<SkillFeatureExtraction | null>(null)
  const [result, setResult] = useState<SkillMarkdownEvaluation | null>(null)
  const [loading, setLoading] = useState(false)
  const [profileLoading, setProfileLoading] = useState(false)
  const [prefillLoading, setPrefillLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    setProfileLoading(true)
    evaluationApi.getDefaultProfile()
      .then((loaded) => {
        setProfile(loaded)
        setSavedProfile(cloneProfile(loaded))
      })
      .catch((err) => setError(err.response?.data?.detail || err.message || 'Failed to load evaluation profile'))
      .finally(() => setProfileLoading(false))
  }, [])

  useEffect(() => {
    if (!initialSkillId) return
    setPrefillLoading(true)
    skillsApi.get(initialSkillId)
      .then((skill) => {
        setMarkdown(skill.raw_content)
        setMode('paste')
      })
      .catch((err) => {
        setError(err.response?.data?.detail || err.message || 'Failed to prefill skill markdown')
      })
      .finally(() => setPrefillLoading(false))
  }, [initialSkillId])

  const updateProfile = (updater: (draft: EvaluationProfile) => void) => {
    setProfile((current) => {
      if (!current) return current
      const draft = cloneProfile(current)
      updater(draft)
      return draft
    })
  }

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.name.endsWith('.md')) {
      setError('Please choose a .md file')
      return
    }

    setError('')
    setFileName(file.name)
    setMode('upload')
    const text = await file.text()
    setMarkdown(text)
  }

  const handleSaveProfile = async () => {
    if (!profile) return
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const saved = await evaluationApi.saveDefaultProfile(profile)
      setProfile(saved)
      setSavedProfile(cloneProfile(saved))
      setNotice('Evaluation profile saved')
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Saving profile failed')
    } finally {
      setLoading(false)
    }
  }

  const handleEvaluate = async () => {
    if (!markdown.trim()) {
      setError('Please upload a .md file or paste SKILL.md content before evaluating')
      return
    }
    setLoading(true)
    setError('')
    setNotice('')
    setResult(null)
    try {
      const res = await evaluationApi.evaluateMarkdown(markdown, profile?.id || 'default')
      setResult(res)
    } catch (err: any) {
      setError(apiErrorMessage(err, 'Evaluation failed'))
    } finally {
      setLoading(false)
    }
  }

  const handleExtractFeatures = async () => {
    if (!markdown.trim()) {
      setError('Please upload a .md file or paste SKILL.md content before extracting features')
      return
    }
    setLoading(true)
    setError('')
    setNotice('')
    setResult(null)
    try {
      const res = await evaluationApi.extractFeatures(markdown, profile?.id || 'default')
      setExtraction(res)
      setNotice('Features extracted. Review and adjust values before scoring.')
    } catch (err: any) {
      setError(apiErrorMessage(err, 'Feature extraction failed'))
    } finally {
      setLoading(false)
    }
  }

  const handleScoreFeatures = async () => {
    if (!extraction) return
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const res = await evaluationApi.scoreFeatures({
        markdown,
        profile_id: profile?.id || 'default',
        content_features: extraction.content_features,
        content_feature_evidence: extraction.content_feature_evidence,
        format_features: extraction.format_features,
        format_feature_evidence: extraction.format_feature_evidence,
        calibration: extraction.calibration,
      })
      setResult(res)
      setNotice('Scored using reviewed feature values.')
    } catch (err: any) {
      setError(apiErrorMessage(err, 'Feature scoring failed'))
    } finally {
      setLoading(false)
    }
  }

  const handleExportHtml = async () => {
    if (!result) return
    try {
      const blob = await evaluationApi.exportHtml(result)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'skill-evaluation-report.html'
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      setError(apiErrorMessage(err, 'HTML export failed'))
    }
  }

  const featureOptions = profile?.features.map((feature) => feature.id) || []
  const featureTypeById = Object.fromEntries(profile?.features.map((feature) => [feature.id, feature.type]) || [])
  const isDirty = profile && savedProfile ? JSON.stringify(profile) !== JSON.stringify(savedProfile) : false

  return (
    <div>
      <div className="tabs mb-6">
        <button className={`tab ${pageTab === 'evaluation' ? 'active' : ''}`} onClick={() => setPageTab('evaluation')}>
          Evaluation
        </button>
        <button className={`tab ${pageTab === 'config' ? 'active' : ''}`} onClick={() => setPageTab('config')}>
          Config
        </button>
      </div>

      {pageTab === 'evaluation' ? (
        <>
          <div className="tabs">
            <button className={`tab ${mode === 'upload' ? 'active' : ''}`} onClick={() => setMode('upload')}>
              <UploadCloud size={14} /> Upload .md
            </button>
            <button className={`tab ${mode === 'paste' ? 'active' : ''}`} onClick={() => setMode('paste')}>
              <FileUp size={14} /> Paste Markdown
            </button>
          </div>

          <div className="card mb-6">
            {mode === 'upload' ? (
              <div className="form-group mb-0">
                <label className="form-label">Choose a SKILL.md file</label>
                <input className="form-input" type="file" accept=".md,text/markdown" onChange={handleFileChange} />
                <div className="text-xs text-muted mt-4">
                  {fileName ? `Loaded file: ${fileName}` : 'The file content will be read locally and sent as markdown text.'}
                </div>
              </div>
            ) : (
              <div className="form-group mb-0">
                <label className="form-label">Paste SKILL.md content</label>
                <textarea
                  className="form-input form-textarea"
                  style={{ minHeight: 260 }}
                  value={markdown}
                  onChange={(e) => setMarkdown(e.target.value)}
                  placeholder="Paste the full SKILL.md content here..."
                />
              </div>
            )}

            {mode === 'upload' && markdown && (
              <div className="form-group mt-4 mb-0">
                <label className="form-label">Preview / Edit loaded markdown</label>
                <textarea
                  className="form-input form-textarea"
                  style={{ minHeight: 180 }}
                  value={markdown}
                  onChange={(e) => setMarkdown(e.target.value)}
                />
              </div>
            )}

            <div className="mt-4 flex gap-3 items-center">
              <button className="btn btn-primary" onClick={handleEvaluate} disabled={loading || prefillLoading || profileLoading}>
                {loading || prefillLoading ? <div className="spinner" style={{ width: 16, height: 16 }} /> : <Play size={16} />}
                Evaluate Directly
              </button>
              <button className="btn btn-secondary" onClick={handleExtractFeatures} disabled={loading || prefillLoading || profileLoading}>
                <Sparkles size={16} />
                Extract Features
              </button>
              <button className="btn btn-secondary" onClick={handleScoreFeatures} disabled={loading || !extraction}>
                <CheckCircle size={16} />
                Score Reviewed Features
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setMarkdown('')
                  setFileName('')
                  setExtraction(null)
                  setResult(null)
                  setError('')
                  setNotice('')
                }}
                disabled={loading || prefillLoading}
              >
                Clear
              </button>
            </div>
          </div>

          {extraction && profile && (
            <FeatureCorrectionPanel
              extraction={extraction}
              contentFeatureTypes={Object.fromEntries(profile.features.map((feature) => [feature.id, feature.type]))}
              formatFeatureTypes={Object.fromEntries((profile.format_features || []).map((feature) => [feature.id, feature.type]))}
              onChange={setExtraction}
            />
          )}

          {notice && (
            <div className="card mb-6" style={{ borderColor: 'var(--green)', background: 'rgba(34,211,238,0.05)' }}>
              <p className="text-sm text-green">{notice}</p>
            </div>
          )}

          {error && (
            <div className="card mb-6" style={{ borderColor: 'var(--red)', background: 'rgba(248,113,113,0.05)' }}>
              <h3 className="text-red font-bold flex items-center gap-2"><XCircle size={18} /> Error</h3>
              <p className="mt-2 text-sm">{error}</p>
            </div>
          )}

          {result && (
            <>
              <div className="flex justify-end mb-4">
                <button className="btn btn-secondary btn-sm" onClick={handleExportHtml}>
                  <Download size={14} /> Export HTML
                </button>
              </div>
              <EvaluationResult result={result} />
            </>
          )}
        </>
      ) : (
        <>
          {profile && (
            <div className="card mb-6">
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h3 className="font-bold text-sm">Evaluation Profile</h3>
                  <div className="text-xs text-muted mt-1">{profile.name}</div>
                </div>
                <div className="flex gap-2">
                  <button className="btn btn-secondary btn-sm" onClick={() => savedProfile && setProfile(cloneProfile(savedProfile))} disabled={!savedProfile || loading || !isDirty}>
                    Reset to Default
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={handleSaveProfile} disabled={loading || !isDirty}>
                    <Save size={14} /> Save Profile
                  </button>
                </div>
              </div>

              <div className="tabs mb-4">
                <button className={`tab ${profileTab === 'features' ? 'active' : ''}`} onClick={() => setProfileTab('features')}>Features</button>
                <button className={`tab ${profileTab === 'bucket' ? 'active' : ''}`} onClick={() => setProfileTab('bucket')}>Bucket Scoring</button>
                <button className={`tab ${profileTab === 'criteria' ? 'active' : ''}`} onClick={() => setProfileTab('criteria')}>Criteria</button>
                <button className={`tab ${profileTab === 'model' ? 'active' : ''}`} onClick={() => setProfileTab('model')}>Model & Key</button>
              </div>

              {profileTab === 'features' && (
                <FeatureEditor
                  features={profile.features}
                  onChange={(features) => updateProfile((draft) => { draft.features = features })}
                  onEditFeature={(index, feature) => setEditingFeature({ index, feature })}
                  onAddFeature={() => setEditingFeature({ index: profile.features.length, feature: emptyFeature() })}
                />
              )}

              {profileTab === 'bucket' && (
                <div className="rule-grid">
                  {(['p25', 'p50', 'p75', 'p90', 'above'] as const).map((key) => (
                    <label key={key} className="form-group mb-0">
                      <span className="form-label">{key}</span>
                      <input
                        className="form-input"
                        type="number"
                        value={profile.bucket_scheme[key]}
                        onChange={(e) => updateProfile((draft) => { draft.bucket_scheme[key] = Number(e.target.value) })}
                      />
                    </label>
                  ))}
                </div>
              )}

              {profileTab === 'criteria' && (
                <CriteriaEditor
                  criteria={profile.criteria}
                  featureOptions={featureOptions}
                  featureTypeById={featureTypeById}
                  onChange={(criteria) => updateProfile((draft) => { draft.criteria = criteria })}
                />
              )}

              {profileTab === 'model' && (
                <ModelConfigEditor
                  llm={profile.llm || defaultLlmConfig()}
                  onChange={(llm) => updateProfile((draft) => { draft.llm = llm })}
                />
              )}
            </div>
          )}

          {notice && (
            <div className="card mb-6" style={{ borderColor: 'var(--green)', background: 'rgba(34,211,238,0.05)' }}>
              <p className="text-sm text-green">{notice}</p>
            </div>
          )}

          {error && (
            <div className="card mb-6" style={{ borderColor: 'var(--red)', background: 'rgba(248,113,113,0.05)' }}>
              <h3 className="text-red font-bold flex items-center gap-2"><XCircle size={18} /> Error</h3>
              <p className="mt-2 text-sm">{error}</p>
            </div>
          )}
        </>
      )}

      {editingFeature && (
        <EditFeatureModal
          feature={editingFeature.feature}
          onClose={() => setEditingFeature(null)}
          onSave={(saved) => {
            const { index } = editingFeature
            updateProfile((draft) => {
              if (index === draft.features.length) {
                draft.features.push(saved)
              } else {
                draft.features[index] = saved
              }
            })
            setEditingFeature(null)
          }}
        />
      )}
    </div>
  )
}

function ModelConfigEditor({
  llm,
  onChange,
}: {
  llm: LlmConfig
  onChange: (llm: LlmConfig) => void
}) {
  const update = (patch: Partial<LlmConfig>) => onChange({ ...llm, ...patch })

  return (
    <div>
      <div className="card mb-4" style={{ background: 'rgba(99,102,241,0.06)', borderColor: 'rgba(99,102,241,0.18)' }}>
        <h4 className="font-bold text-sm mb-2">LLM extraction config</h4>
        <p className="text-sm text-muted">
          The LLM only extracts configured boolean/integer features. Scoring remains deterministic from the rule profile.
        </p>
        <p className="text-xs text-muted mt-2">
          When you click Save Profile, these values are saved to the active default profile JSON in <code>/database/evaluation_profiles/default_distribution.json</code>.
        </p>
      </div>

      <div className="rule-grid">
        <label className="form-group mb-0">
          <span className="form-label">Provider</span>
          <select
            className="form-input form-select"
            value={llm.provider || 'openai-compatible'}
            onChange={(e) => update({ provider: e.target.value })}
          >
            <option value="openai-compatible">openai-compatible</option>
          </select>
        </label>

        <label className="form-group mb-0">
          <span className="form-label">Base URL</span>
          <input
            className="form-input"
            placeholder="https://api.deepseek.com/v1"
            value={llm.base_url || ''}
            onChange={(e) => update({ base_url: e.target.value })}
          />
        </label>

        <label className="form-group mb-0">
          <span className="form-label">Model</span>
          <input
            className="form-input"
            placeholder="deepseek-chat"
            value={llm.model || ''}
            onChange={(e) => update({ model: e.target.value })}
          />
        </label>

        <label className="form-group mb-0">
          <span className="form-label">API Key</span>
          <input
            className="form-input"
            type="password"
            placeholder="sk-..."
            value={llm.api_key || ''}
            onChange={(e) => update({ api_key: e.target.value })}
          />
        </label>
      </div>

      <div className="mt-4 text-xs text-muted">
        Keep this local/private: the key is stored as plain text because this dev setup uses JSON files instead of a secret manager.
      </div>
    </div>
  )
}

function EditFeatureModal({
  feature,
  onClose,
  onSave,
}: {
  feature: FeatureDefinition
  onClose: () => void
  onSave: (feature: FeatureDefinition) => void
}) {
  const [form, setForm] = useState<FeatureDefinition>({ ...feature })

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
      <div className="card" style={{ width: '100%', maxWidth: 500, maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold">{feature.id === 'new_feature' ? 'Add Feature' : 'Edit Feature'}</h3>
          <button className="btn btn-ghost" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="form-group">
          <label className="form-label">Feature ID</label>
          <input
            className="form-input font-mono"
            placeholder="e.g. has_description"
            value={form.id}
            onChange={(e) => setForm(prev => ({ ...prev, id: e.target.value }))}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Type</label>
          <select
            className="form-input form-select"
            value={form.type}
            onChange={(e) => setForm(prev => ({ ...prev, type: e.target.value as FeatureType }))}
          >
            {FEATURE_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">LLM Extraction Guidance</label>
          <textarea
            className="form-input form-textarea"
            placeholder="Step-by-step instructions for extraction..."
            value={form.extraction_guidance}
            onChange={(e) => setForm(prev => ({ ...prev, extraction_guidance: e.target.value }))}
            style={{ minHeight: 120 }}
          />
        </div>

        <div className="flex gap-2 mt-6">
          <button className="btn btn-secondary flex-1" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary flex-1"
            onClick={() => onSave(form)}
            disabled={!form.id.trim()}
          >
            Save Feature
          </button>
        </div>
      </div>
    </div>
  )
}

function FeatureEditor({
  features,
  onChange,
  onEditFeature,
  onAddFeature,
}: {
  features: FeatureDefinition[]
  onChange: (features: FeatureDefinition[]) => void
  onEditFeature: (index: number, feature: FeatureDefinition) => void
  onAddFeature: () => void
}) {
  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          className="btn btn-secondary btn-sm"
          onClick={onAddFeature}
        >
          <Plus size={14} /> Add Feature
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: '25%' }}>Feature ID</th>
              <th style={{ width: '15%' }}>Type</th>
              <th>LLM Extraction Guidance</th>
              <th style={{ width: '10%', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {features.map((feature, index) => (
              <tr key={`${feature.id}-${index}`}>
                <td style={{ verticalAlign: 'middle', padding: '12px 16px' }}>
                  <code className="font-mono text-accent" style={{ fontSize: '13.5px', fontWeight: 600 }}>{feature.id}</code>
                </td>
                <td style={{ verticalAlign: 'middle', padding: '12px 16px' }}>
                  <span className="badge badge-tag">{feature.type}</span>
                </td>
                <td style={{ verticalAlign: 'middle', padding: '12px 16px' }}>
                  <span className="text-secondary text-sm" style={{ display: 'block', whiteSpace: 'pre-wrap', lineHeight: 1.4 }}>
                    {feature.extraction_guidance || <em className="text-muted">No extraction guidance</em>}
                  </span>
                </td>
                <td style={{ verticalAlign: 'middle', textAlign: 'right', padding: '12px 16px' }}>
                  <div className="flex gap-1 justify-end">
                    <button
                      className="btn btn-ghost btn-sm text-accent"
                      onClick={() => onEditFeature(index, feature)}
                      style={{ padding: '8px' }}
                      title="Edit Feature"
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="btn btn-ghost btn-sm text-red"
                      onClick={() => onChange(features.filter((_, idx) => idx !== index))}
                      style={{ padding: '8px' }}
                      title="Remove Feature"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function FeatureCorrectionPanel({
  extraction,
  contentFeatureTypes,
  formatFeatureTypes,
  onChange,
}: {
  extraction: SkillFeatureExtraction
  contentFeatureTypes: Record<string, FeatureType>
  formatFeatureTypes: Record<string, FeatureType>
  onChange: (next: SkillFeatureExtraction) => void
}) {
  const updateFeature = (scope: 'content' | 'format', key: string, value: any) => {
    const featureKey = scope === 'content' ? 'content_features' : 'format_features'
    onChange({
      ...extraction,
      [featureKey]: {
        ...extraction[featureKey],
        [key]: value,
      },
    })
  }

  return (
    <div className="card mb-6">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="font-bold text-sm">Review Extracted Features</h3>
          <div className="text-xs text-muted mt-1">Adjust values here before scoring. Evidence and confidence are informational.</div>
        </div>
        <span className="badge badge-pass">Model: {extraction.model}</span>
      </div>

      <h4 className="font-bold text-sm mb-3">Format Features</h4>
      <FeatureCorrectionTable
        features={extraction.format_features}
        evidence={extraction.format_feature_evidence}
        featureTypes={formatFeatureTypes}
        onChange={(key, value) => updateFeature('format', key, value)}
      />

      <h4 className="font-bold text-sm mt-6 mb-3">Content Features</h4>
      <FeatureCorrectionTable
        features={extraction.content_features}
        evidence={extraction.content_feature_evidence}
        featureTypes={contentFeatureTypes}
        onChange={(key, value) => updateFeature('content', key, value)}
      />
    </div>
  )
}

function FeatureCorrectionTable({
  features,
  evidence,
  featureTypes,
  onChange,
}: {
  features: Record<string, any>
  evidence: Record<string, FeatureEvidence>
  featureTypes: Record<string, FeatureType>
  onChange: (key: string, value: any) => void
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Feature</th>
            <th>Value</th>
            <th>Evidence</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(features).map(([key, value]) => {
            const type = featureTypes[key] || inferFeatureType(value)
            const itemEvidence = evidence[key] || {}
            return (
              <tr key={key}>
                <td className="font-mono text-xs">{key}</td>
                <td>
                  <FeatureValueInput
                    type={type}
                    value={value}
                    onChange={(next) => onChange(key, next)}
                  />
                </td>
                <td className="text-xs">{itemEvidence.evidence || 'No evidence returned'}</td>
                <td className="font-mono text-xs">{itemEvidence.confidence ?? ''}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function FeatureValueInput({
  type,
  value,
  onChange,
}: {
  type: FeatureType
  value: any
  onChange: (value: any) => void
}) {
  if (type === 'boolean') {
    return (
      <select className="form-input compact-select" value={String(Boolean(value))} onChange={(e) => onChange(e.target.value === 'true')}>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    )
  }
  if (type === 'integer') {
    return (
      <input
        className="form-input compact-input"
        type="number"
        step={1}
        value={value ?? 0}
        onChange={(e) => onChange(Number.parseInt(e.target.value || '0', 10))}
      />
    )
  }
  return null
}

function inferFeatureType(value: any): FeatureType {
  if (typeof value === 'boolean') return 'boolean'
  return 'integer'
}

function CriteriaEditor({
  criteria,
  featureOptions,
  featureTypeById,
  onChange,
}: {
  criteria: CriterionDefinition[]
  featureOptions: string[]
  featureTypeById: Record<string, FeatureType>
  onChange: (criteria: CriterionDefinition[]) => void
}) {
  const [expandedIndices, setExpandedIndices] = useState<Record<number, boolean>>({})

  const toggleExpand = (index: number) => {
    setExpandedIndices(prev => ({
      ...prev,
      [index]: !prev[index]
    }))
  }

  const updateCriterion = (index: number, patch: Partial<CriterionDefinition>) => {
    onChange(criteria.map((criterion, idx) => idx === index ? { ...criterion, ...patch } : criterion))
  }

  const updateSteps = (criterionIndex: number, steps: RuleStep[]) => {
    updateCriterion(criterionIndex, { steps })
  }

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button className="btn btn-secondary btn-sm" onClick={() => onChange([...criteria, emptyCriterion()])}>
          <Plus size={14} /> Add Criterion
        </button>
      </div>
      <div className="stack-list">
        {criteria.map((criterion, criterionIndex) => {
          const isExpanded = expandedIndices[criterionIndex]
          return (
            <div key={`${criterion.id}-${criterionIndex}`} className="rule-block" style={{ padding: 0, overflow: 'hidden', marginBottom: '16px' }}>
              <div
                className="flex justify-between items-center p-4 cursor-pointer hover:bg-card-hover transition-colors"
                onClick={() => toggleExpand(criterionIndex)}
                style={{ borderBottom: isExpanded ? '1px solid var(--border)' : 'none' }}
              >
                <div className="flex items-center gap-3">
                  <span className="text-secondary flex items-center">
                    {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm font-mono text-accent">{criterion.id || 'new_criterion'}</span>
                    {criterion.label && <span className="text-xs text-muted">({criterion.label})</span>}
                  </div>
                  <span className="badge badge-tag" style={{ fontSize: '10px' }}>
                    {criterion.steps.length} {criterion.steps.length === 1 ? 'step' : 'steps'}
                  </span>
                  <span className="badge badge-tag" style={{ fontSize: '10px' }}>
                    Max: {criterion.max_score} pts
                  </span>
                </div>

                <div onClick={(e) => e.stopPropagation()}>
                  <button
                    className="btn btn-ghost btn-sm text-red"
                    onClick={() => onChange(criteria.filter((_, idx) => idx !== criterionIndex))}
                    style={{ padding: '4px 8px' }}
                    title="Remove Criterion"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {isExpanded && (
                <div className="p-5" style={{ background: 'rgba(255, 255, 255, 0.01)' }}>
                  <div className="rule-grid">
                    <label className="form-group mb-0">
                      <span className="form-label">Criterion ID</span>
                      <input className="form-input" value={criterion.id} onChange={(e) => updateCriterion(criterionIndex, { id: e.target.value })} />
                    </label>
                    <label className="form-group mb-0">
                      <span className="form-label">Label</span>
                      <input className="form-input" value={criterion.label} onChange={(e) => updateCriterion(criterionIndex, { label: e.target.value })} />
                    </label>
                    <label className="form-group mb-0">
                      <span className="form-label">Max Score</span>
                      <input className="form-input" type="number" value={criterion.max_score} onChange={(e) => updateCriterion(criterionIndex, { max_score: Number(e.target.value) })} />
                    </label>
                  </div>

                  <div className="mt-4 flex justify-between items-center">
                    <div className="text-xs text-muted">Rule steps run from top to bottom.</div>
                    <button className="btn btn-secondary btn-sm" onClick={() => updateSteps(criterionIndex, [...criterion.steps, emptyStep(featureOptions[0] || '')])}>
                      <Plus size={14} /> Add Step
                    </button>
                  </div>

                  <div className="stack-list mt-3">
                    {criterion.steps.map((step, stepIndex) => (
                      <RuleStepEditor
                        key={`${step.id}-${stepIndex}`}
                        step={step}
                        featureOptions={featureOptions}
                        featureTypeById={featureTypeById}
                        onChange={(nextStep) => updateSteps(
                          criterionIndex,
                          criterion.steps.map((item, idx) => idx === stepIndex ? nextStep : item),
                        )}
                        onRemove={() => updateSteps(criterionIndex, criterion.steps.filter((_, idx) => idx !== stepIndex))}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function RuleStepEditor({
  step,
  featureOptions,
  featureTypeById,
  onChange,
  onRemove,
}: {
  step: RuleStep
  featureOptions: string[]
  featureTypeById: Record<string, FeatureType>
  onChange: (step: RuleStep) => void
  onRemove: () => void
}) {
  const [isExpanded, setIsExpanded] = useState(false)

  const showValue = ['force_score', 'add', 'subtract', 'cap_max', 'set_baseline'].includes(step.action) && step.source !== 'percentile_bonus'
  const showFeature = step.action === 'set_score_from_bucket' || step.source === 'percentile_bonus'

  let actionLabel: string = step.action
  if (step.source === 'percentile_bonus') {
    actionLabel = `percentile_bonus (${step.scores?.p50 ?? 2} / ${step.scores?.p90 ?? 4})`
  } else if (showValue) {
    actionLabel = `${step.action} (${step.value})`
  } else if (showFeature) {
    actionLabel = `${step.action} (${step.feature})`
  }

  return (
    <div className="rule-step" style={{ padding: 0, overflow: 'hidden', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', marginBottom: '8px', background: 'var(--bg-card)' }}>
      <div
        className="flex justify-between items-center p-3 cursor-pointer hover:bg-card-hover transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
        style={{ borderBottom: isExpanded ? '1px solid var(--border)' : 'none' }}
      >
        <div className="flex items-center gap-3">
          <span className="text-secondary flex items-center">
            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </span>
          <div className="flex items-center gap-2">
            <span className="font-bold text-xs font-mono text-accent">{step.id || 'new_step'}</span>
            <span className="badge badge-tag" style={{ fontSize: '10.5px' }}>{actionLabel}</span>
            {step.condition ? (
              <span className="badge badge-tag" style={{ fontSize: '10.5px', background: 'rgba(99,102,241,0.1)', color: 'var(--accent)' }}>Conditional</span>
            ) : (
              <span className="badge badge-tag" style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>Always Apply</span>
            )}
          </div>
          {step.description && (
            <span className="text-xs text-muted truncate max-w-md hidden md:inline" style={{ marginLeft: '8px' }}>
              — {step.description}
            </span>
          )}
        </div>

        <div onClick={(e) => e.stopPropagation()}>
          <button
            className="btn btn-ghost btn-sm text-red"
            onClick={onRemove}
            style={{ padding: '4px 8px' }}
            title="Remove Step"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="p-4" style={{ background: 'rgba(255,255,255,0.01)' }}>
          <div className="rule-grid">
            <label className="form-group mb-0">
              <span className="form-label">Step ID</span>
              <input className="form-input" value={step.id} onChange={(e) => onChange({ ...step, id: e.target.value })} />
            </label>
            <label className="form-group mb-0">
              <span className="form-label">Action</span>
              <select className="form-input" value={step.action} onChange={(e) => onChange({ ...step, action: e.target.value as RuleAction })}>
                {ACTIONS.map((action) => <option key={action} value={action}>{action}</option>)}
              </select>
            </label>
            {showFeature && (
              <label className="form-group mb-0">
                <span className="form-label">Feature</span>
                <select className="form-input" value={step.feature || ''} onChange={(e) => onChange({ ...step, feature: e.target.value })}>
                  {featureOptions.map((feature) => <option key={feature} value={feature}>{feature}</option>)}
                </select>
              </label>
            )}
            {showValue && (
              <label className="form-group mb-0">
                <span className="form-label">Value</span>
                <input className="form-input" value={valueToInput(step.value)} onChange={(e) => onChange({ ...step, value: Number(e.target.value) })} />
              </label>
            )}
          </div>

          <label className="form-group mt-3 mb-0">
            <span className="form-label">Description</span>
            <input className="form-input" value={step.description} onChange={(e) => onChange({ ...step, description: e.target.value })} />
          </label>

          <div className="mt-3 flex gap-3 items-center">
            <label className="flex gap-2 items-center text-sm">
              <input
                type="checkbox"
                checked={step.source === 'percentile_bonus'}
                onChange={(e) => onChange(e.target.checked ? { ...step, source: 'percentile_bonus', action: 'add', scores: step.scores || { p50: 2, p90: 4 } } : { ...step, source: undefined })}
              />
              Percentile bonus source
            </label>
            {step.source === 'percentile_bonus' && (
              <>
                <input className="form-input compact-input" type="number" value={step.scores?.p50 ?? 2} onChange={(e) => onChange({ ...step, scores: { ...(step.scores || {}), p50: Number(e.target.value) } })} />
                <span className="text-xs text-muted">at p50</span>
                <input className="form-input compact-input" type="number" value={step.scores?.p90 ?? 4} onChange={(e) => onChange({ ...step, scores: { ...(step.scores || {}), p90: Number(e.target.value) } })} />
                <span className="text-xs text-muted">at p90</span>
              </>
            )}
          </div>

          <div className="rule-condition mt-3">
            <div className="flex justify-between items-center mb-2">
              <span className="form-label mb-0">Condition</span>
              <button className="btn btn-ghost btn-sm" onClick={() => onChange({ ...step, condition: step.condition ? undefined : emptyCondition(featureOptions[0] || '') })}>
                {step.condition ? 'Always Apply' : 'Add Condition'}
              </button>
            </div>
            {step.condition && (
              <ConditionEditor
                condition={step.condition}
                featureOptions={featureOptions}
                featureTypeById={featureTypeById}
                onChange={(condition) => onChange({ ...step, condition })}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ConditionEditor({
  condition,
  featureOptions,
  featureTypeById,
  onChange,
}: {
  condition: Condition
  featureOptions: string[]
  featureTypeById: Record<string, FeatureType>
  onChange: (condition: Condition) => void
}) {
  if (condition.all || condition.any) {
    const groupKey = condition.all ? 'all' : 'any'
    const items = condition[groupKey] || []
    return (
      <div className="condition-group">
        <div className="flex gap-2 items-center mb-2">
          <select
            className="form-input compact-select"
            value={groupKey}
            onChange={(e) => onChange({ [e.target.value]: items } as Condition)}
          >
            <option value="all">all</option>
            <option value="any">any</option>
          </select>
          <button className="btn btn-secondary btn-sm" onClick={() => onChange({ ...condition, [groupKey]: [...items, emptyCondition(featureOptions[0] || '')] })}>
            <Plus size={14} /> Add Rule
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => onChange({ ...condition, [groupKey]: [...items, { any: [emptyCondition(featureOptions[0] || '')] }] })}>
            <Plus size={14} /> Add Group
          </button>
        </div>
        <div className="stack-list">
          {items.map((item, index) => (
            <div key={index} className="condition-line">
              <ConditionEditor
                condition={item}
                featureOptions={featureOptions}
                featureTypeById={featureTypeById}
                onChange={(next) => onChange({ ...condition, [groupKey]: items.map((candidate, idx) => idx === index ? next : candidate) })}
              />
              <button className="btn btn-ghost btn-sm" onClick={() => onChange({ ...condition, [groupKey]: items.filter((_, idx) => idx !== index) })}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (condition.not) {
    return (
      <div className="condition-group">
        <div className="text-xs text-muted mb-2">NOT</div>
        <ConditionEditor
          condition={condition.not}
          featureOptions={featureOptions}
          featureTypeById={featureTypeById}
          onChange={(next) => onChange({ not: next })}
        />
      </div>
    )
  }

  const featureType = featureTypeById[condition.feature || '']
  const operator = condition.operator || 'eq'
  const needsValue = !['exists', 'missing'].includes(operator)

  return (
    <div className="condition-leaf">
      <select className="form-input" value={condition.feature || ''} onChange={(e) => onChange({ ...condition, feature: e.target.value })}>
        {featureOptions.map((feature) => <option key={feature} value={feature}>{feature}</option>)}
      </select>
      <select className="form-input compact-select" value={operator} onChange={(e) => onChange({ ...condition, operator: e.target.value as ConditionOperator })}>
        {OPERATORS.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
      {needsValue && condition.value && typeof condition.value === 'object' && condition.value.percentile ? (
        <>
          <select
            className="form-input"
            value={condition.value.feature || condition.feature || ''}
            onChange={(e) => onChange({ ...condition, value: { ...condition.value, feature: e.target.value } })}
          >
            {featureOptions.map((feature) => <option key={feature} value={feature}>{feature}</option>)}
          </select>
          <select
            className="form-input compact-select"
            value={condition.value.percentile || 'p75'}
            onChange={(e) => onChange({ ...condition, value: { ...condition.value, percentile: e.target.value } })}
          >
            <option value="p25">p25</option>
            <option value="p50">p50</option>
            <option value="p75">p75</option>
            <option value="p90">p90</option>
          </select>
        </>
      ) : needsValue && featureType === 'boolean' ? (
        <select className="form-input compact-select" value={String(condition.value ?? false)} onChange={(e) => onChange({ ...condition, value: e.target.value === 'true' })}>
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      ) : needsValue ? (
        <input
          className="form-input"
          value={valueToInput(condition.value)}
          onChange={(e) => onChange({ ...condition, value: parseValue(e.target.value, featureType) })}
          placeholder="value"
        />
      ) : null}
    </div>
  )
}

function EvaluationResult({ result }: { result: SkillMarkdownEvaluation }) {
  return (
    <div>
      <div className="card">
        <h3 className="font-bold text-sm mb-4">Configurable Content Review</h3>
        <div className="score-circle pass">
          <div className="score-num">{result.content_review.total_score}</div>
          <div className="score-denom">/ {result.content_review.max_score}</div>
        </div>
        <div className="text-center mb-6">
          <span className="badge badge-pass">LLM Features</span>
          <div className="text-xs text-muted mt-2">Model: {result.content_review.model}</div>
        </div>

        <div className="mt-4 border-t border-[rgba(255,255,255,0.08)] pt-4">
          {result.content_review.criteria.map((c) => (
            <div key={c.criterion} className="criterion-row expanded">
              <div className="criterion-icon">
                <CheckCircle size={14} className="text-green" />
              </div>
              <div className="criterion-desc">
                <div className="font-bold text-sm">{c.label || c.criterion}</div>
                <div className="criterion-note">{c.explanation}</div>
                {c.applied_steps.length > 0 && (
                  <div className="applied-steps">
                    {c.applied_steps.map((step, index) => (
                      <div key={`${step.id}-${index}`} className="text-xs text-muted">
                        {step.id || step.action}: {step.before} {'->'} {step.after}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="criterion-pts pts-pass">
                {c.score}/{c.max_score}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6">
          <h4 className="font-bold text-sm mb-3">Extracted Features</h4>
          <div className="feature-result-grid">
            {Object.entries(result.content_review.features).map(([key, value]) => (
              <div key={key} className="feature-pill">
                <span>{key}</span>
                <strong>{String(value)}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6">
          <h4 className="font-bold text-sm mb-3">Calibration</h4>
          <div className="feature-result-grid">
            {Object.entries(result.content_review.calibration).map(([feature, thresholds]) => (
              <div key={feature} className="feature-pill wide">
                <span>{feature}</span>
                <strong>
                  p25 {thresholds.p25} / p50 {thresholds.p50} / p75 {thresholds.p75} / p90 {thresholds.p90}
                </strong>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
