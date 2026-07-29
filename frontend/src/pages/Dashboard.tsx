import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { BookOpen, FlaskConical, RefreshCw } from 'lucide-react'

import { SkillList, skillsApi } from '../api/client'

const COLORS = ['#6366f1', '#22d3ee', '#a78bfa', '#fbbf24', '#f87171', '#34d399']

export default function Dashboard() {
  const [skills, setSkills] = useState<SkillList | null>(null)
  const [registryCount, setRegistryCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    Promise.all([
      skillsApi.list(),
      skillsApi.registryStatus().catch(() => ({ loaded_skills: 0 })),
    ])
      .then(([skillList, registry]) => {
        setSkills(skillList)
        setRegistryCount(registry.loaded_skills || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const byCategory = new Map<string, number>()
  const byLevel = new Map<string, number>()
  for (const skill of skills?.items || []) {
    byCategory.set(skill.category, (byCategory.get(skill.category) || 0) + 1)
    byLevel.set(skill.level, (byLevel.get(skill.level) || 0) + 1)
  }

  const categoryChart = Array.from(byCategory.entries())
    .map(([name, count]) => ({ name: name.split('/').pop(), full: name, count }))

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h2>Dashboard</h2>
          <p>Simple overview from the JSON-backed skill library</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="loading-center"><div className="spinner" /></div>
      ) : !skills ? (
        <div className="empty-state"><h3>Unable to connect to skill management</h3></div>
      ) : (
        <>
          <div className="stat-grid">
            <div className="stat-card" onClick={() => navigate('/skills')} style={{ cursor: 'pointer' }}>
              <div className="stat-label">Total Skills</div>
              <div className="stat-value accent">{skills.total}</div>
              <div className="stat-sub">{registryCount} in registry</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Categories</div>
              <div className="stat-value" style={{ color: 'var(--green)' }}>{byCategory.size}</div>
              <div className="stat-sub">from skill metadata</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Levels</div>
              <div className="stat-value" style={{ color: 'var(--purple)' }}>{byLevel.size}</div>
              <div className="stat-sub">atomic / composite</div>
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-sm">Skills by Category</h3>
              </div>
              {categoryChart.length === 0 ? (
                <div className="empty-state" style={{ padding: '30px' }}>No categories yet</div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={categoryChart} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: '#0f1420', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, color: '#f1f5f9' }}
                      formatter={(v, _, p) => [v, p.payload.full]}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {categoryChart.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="card">
              <h3 className="font-bold text-sm mb-4">Skills by Level</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {Array.from(byLevel.entries()).map(([level, count]) => (
                  <div key={level}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`badge badge-${level}`}>{level}</span>
                      <span className="text-sm font-bold">{count}</span>
                    </div>
                    <div style={{ background: 'var(--border)', borderRadius: 4, height: 6 }}>
                      <div style={{
                        width: `${skills.total ? (count / skills.total * 100) : 0}%`,
                        height: '100%',
                        borderRadius: 4,
                        background: level === 'atomic' ? 'var(--accent)' : 'var(--purple)',
                        transition: 'width 0.8s ease',
                      }} />
                    </div>
                  </div>
                ))}
              </div>

              <hr className="divider" />
              <h3 className="font-bold text-sm mb-3">Quick Actions</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button className="btn btn-secondary w-full" onClick={() => navigate('/skills')}>
                  <BookOpen size={14} /> Browse Skills
                </button>
                <button className="btn btn-secondary w-full" onClick={() => navigate('/evaluation')}>
                  <FlaskConical size={14} /> Run Evaluation
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
