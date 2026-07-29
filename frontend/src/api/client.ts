import axios from 'axios'

const BASE = {
  management: '/api/management',
  evaluation: '/api/evaluation',
  testing: '/api/testing',
  reporting: '/api/reporting',
}

const mgmt = axios.create({ baseURL: BASE.management })
const eval_ = axios.create({ baseURL: BASE.evaluation, timeout: 180000 })
const test_ = axios.create({ baseURL: BASE.testing })
const report = axios.create({ baseURL: BASE.reporting })

// ── Types ─────────────────────────────────────────────────────────────────

export interface SkillMetadata {
  name: string
  version: string
  level: string
  category: string
  tags: string[]
  description?: string
  goal?: string
  sub_skills?: string[]
  [key: string]: any
}

export interface SkillSummary extends SkillMetadata {
  id: string
  metadata: Record<string, any>
  updated_at: string
}

export interface SkillRead extends SkillSummary {
  raw_content: string
  full_markdown: string
}

export interface SkillList {
  items: SkillSummary[]
  total: number
}

export interface SkillSearchResult {
  skill: SkillSummary
  score: number
}

export interface FormatCriterion {
  criterion: string
  label?: string
  score: number
  max_score: number
  explanation: string
  applied_steps: Record<string, any>[]
}

export interface FormatReview {
  score: number
  max_score: number
  passed: boolean
  frontmatter_valid: boolean
  errors: string[]
  criteria: FormatCriterion[]
  features: Record<string, any>
  feature_evidence: Record<string, FeatureEvidence>
}

export interface ContentCriterion {
  criterion: string
  label?: string
  score: number
  max_score: number
  explanation: string
  applied_steps: Record<string, any>[]
}

export interface ContentReview {
  model: string
  profile_id?: string
  profile_hash?: string
  total_score: number
  max_score: number
  criteria: ContentCriterion[]
  features: Record<string, any>
  feature_evidence: Record<string, FeatureEvidence>
  calibration: Record<string, Record<string, number>>
}

export interface SkillMarkdownEvaluation {
  format_review: FormatReview
  content_review: ContentReview
}

export type FeatureType = 'boolean' | 'integer'
export type ConditionOperator = 'exists' | 'missing' | 'eq' | 'neq' | 'lt' | 'lte' | 'gt' | 'gte'
export type RuleAction = 'force_score' | 'set_score_from_bucket' | 'add' | 'subtract' | 'cap_max' | 'set_baseline'

export interface FeatureEvidence {
  evidence?: string
  confidence?: number
  source?: string
}

export interface FeatureDefinition {
  id: string
  type: FeatureType
  extraction_guidance: string
}

export interface Condition {
  all?: Condition[]
  any?: Condition[]
  not?: Condition
  feature?: string
  operator?: ConditionOperator
  value?: any
}

export interface RuleStep {
  id: string
  description: string
  condition?: Condition
  action: RuleAction
  value?: any
  feature?: string
  source?: 'percentile_bonus'
  scores?: Record<string, number>
  mode?: string
}

export interface CriterionDefinition {
  id: string
  label: string
  max_score: number
  steps: RuleStep[]
}

export interface LlmConfig {
  provider: string
  base_url: string
  model: string
  api_key: string
}

export interface EvaluationProfile {
  schema_version: number
  id: string
  name: string
  description: string
  llm?: LlmConfig
  bucket_scheme: Record<'p25' | 'p50' | 'p75' | 'p90' | 'above', number>
  features: FeatureDefinition[]
  criteria: CriterionDefinition[]
  format_features?: FeatureDefinition[]
  format_criteria?: CriterionDefinition[]
}

export interface SkillFeatureExtraction {
  model: string
  profile_id: string
  profile_hash: string
  content_features: Record<string, any>
  content_feature_evidence: Record<string, FeatureEvidence>
  format_features: Record<string, any>
  format_feature_evidence: Record<string, FeatureEvidence>
  calibration: Record<string, Record<string, number>>
  metadata_fields: string[]
  frontmatter_parse_error?: string | null
  sync_log?: Record<string, any>[]
  cache_complete?: boolean
}

export interface DashboardData {
  skills: { total: number }
  evaluations: { total: number }
  test_runs: { total: number; passed: number; pass_rate: number }
  doc_reviews: { total: number; passed: number; pass_rate: number }
  by_category: Record<string, number>
  by_level: Record<string, number>
  registry_loaded: number
}

// ── Management API ────────────────────────────────────────────────────────

export const skillsApi = {
  list: (params?: { category?: string; level?: string; tag?: string }) =>
    mgmt.get<SkillList>('/skills', { params }).then(r => r.data),

  search: (q: string, top_k = 5) =>
    mgmt.get<{ query: string; results: SkillSearchResult[] }>('/skills/search', { params: { q, top_k } }).then(r => r.data),

  get: (id: string) =>
    mgmt.get<SkillRead>(`/skills/${id}`).then(r => r.data),

  create: (payload: { metadata: SkillMetadata; instruction: string }) =>
    mgmt.post<SkillRead>('/skills', payload).then(r => r.data),

  update: (id: string, payload: { metadata?: Record<string, any>; instruction?: string; full_markdown?: string; raw_content?: string }) =>
    mgmt.put<SkillRead>(`/skills/${id}`, payload).then(r => r.data),

  delete: (id: string, removeFile = false) =>
    mgmt.delete(`/skills/${id}`, { params: { remove_file: removeFile } }).then(r => r.data),

  importFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return mgmt.post<SkillRead>('/skills/import', form).then(r => r.data)
  },

  exportUrl: (id: string) => `${BASE.management}/skills/${id}/export`,

  registryStatus: () =>
    mgmt.get('/registry/status').then(r => r.data),

  registryReload: () =>
    mgmt.post('/registry/reload').then(r => r.data),
}

// ── Evaluation API ────────────────────────────────────────────────────────

export const evaluationApi = {
  evaluateMarkdown: (markdown: string, profileId = 'default') =>
    eval_.post<SkillMarkdownEvaluation>('/evaluate/markdown', { markdown, profile_id: profileId }).then(r => r.data),

  extractFeatures: (markdown: string, profileId = 'default') =>
    eval_.post<SkillFeatureExtraction>('/evaluate/features', { markdown, profile_id: profileId }).then(r => r.data),

  syncFeatures: (markdown: string, profileId = 'default') =>
    eval_.post<SkillFeatureExtraction>('/evaluate/features/sync', { markdown, profile_id: profileId }).then(r => r.data),

  getCachedFeatures: (markdown: string, profileId = 'default') =>
    eval_.post<SkillFeatureExtraction>('/evaluate/features/cache', { markdown, profile_id: profileId }).then(r => r.data),

  scoreFeatures: (payload: {
    markdown: string
    profile_id?: string
    content_features: Record<string, any>
    content_feature_evidence: Record<string, FeatureEvidence>
    format_features: Record<string, any>
    format_feature_evidence: Record<string, FeatureEvidence>
    calibration: Record<string, Record<string, number>>
  }) =>
    eval_.post<SkillMarkdownEvaluation>('/evaluate/score-features', payload).then(r => r.data),

  exportHtml: (evaluation: SkillMarkdownEvaluation) =>
    eval_.post('/evaluate/export-html', { evaluation }, { responseType: 'blob' }).then(r => r.data as Blob),

  getDefaultProfile: () =>
    eval_.get<EvaluationProfile>('/evaluation/profiles/default').then(r => r.data),

  saveDefaultProfile: (profile: EvaluationProfile) =>
    eval_.put<EvaluationProfile>('/evaluation/profiles/default', profile).then(r => r.data),
}

export function apiErrorMessage(err: any, fallback = 'Request failed') {
  if (err?.code === 'ECONNABORTED') {
    return `${fallback}: request timed out. Check backend logs for the last sync/evaluation step.`
  }
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item?.msg || JSON.stringify(item)).join('; ')
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return err?.message || fallback
}

// ── Testing API ───────────────────────────────────────────────────────────

export const testingApi = {
  runSkillTests: (skillId: string, mockMode = true) =>
    test_.post(`/tests/run/${skillId}`, { mock_mode: mockMode }).then(r => r.data),

  getResults: (skillId: string) =>
    test_.get(`/tests/${skillId}/results`).then(r => r.data),

  chat: (messages: {role: string, content: string}[], model: string, apiKey: string) =>
    test_.post(`/tests/chat`, { messages, model, api_key: apiKey }).then(r => r.data),

  orchestrate: (task: string) =>
    test_.post(`/orchestrate`, { task }).then(r => r.data),
}

// ── Reporting API ─────────────────────────────────────────────────────────

export const reportingApi = {
  dashboard: () =>
    report.get<DashboardData>('/reports/dashboard').then(r => r.data),

  skillsSummary: () =>
    report.get('/reports/skills/summary').then(r => r.data),

  testsSummary: () =>
    report.get('/reports/tests/summary').then(r => r.data),

  evaluationsSummary: () =>
    report.get('/reports/evaluations/summary').then(r => r.data),

  docReviewsSummary: () =>
    report.get('/reports/doc-reviews/summary').then(r => r.data),

  registryStatus: () =>
    report.get('/reports/registry/status').then(r => r.data),

  skillHistory: (skillId: string) =>
    report.get(`/reports/skills/${skillId}/history`).then(r => r.data),
}
