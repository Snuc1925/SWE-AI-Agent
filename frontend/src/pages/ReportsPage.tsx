import { useEffect, useState } from 'react'
import { reportingApi } from '../api/client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const COLORS = ['#6366f1', '#22d3ee', '#a78bfa', '#fbbf24', '#f87171', '#34d399']

export default function ReportsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    reportingApi.dashboard()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading-center"><div className="spinner" /></div>
  if (!data) return <div className="empty-state">Unable to load reports</div>

  const categoryChart = Object.entries(data.by_category).map(([name, count]) => ({ name: name.split('/').pop(), full: name, count }))

  return (
    <div>
      <div className="page-header">
        <h2>Reports</h2>
        <p>Detailed breakdown of platform activity</p>
      </div>

      <div className="grid-2 mb-6">
        <div className="card">
          <h3 className="font-bold text-sm mb-4">Skills by Category</h3>
          <ResponsiveContainer width="100%" height={250}>
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
        </div>

        <div className="card">
          <h3 className="font-bold text-sm mb-4">Registry Status</h3>
          <div className="flex flex-col gap-4">
            <div className="flex justify-between items-center pb-4 border-b border-[rgba(255,255,255,0.08)]">
              <span className="text-secondary">Skills Loaded</span>
              <span className="font-bold text-xl">{data.registry_loaded}</span>
            </div>
            <div className="flex justify-between items-center pb-4 border-b border-[rgba(255,255,255,0.08)]">
              <span className="text-secondary">Atomic Skills</span>
              <span className="font-bold text-accent">{data.by_level['atomic'] || 0}</span>
            </div>
            <div className="flex justify-between items-center pb-4 border-b border-[rgba(255,255,255,0.08)]">
              <span className="text-secondary">Composite Skills</span>
              <span className="font-bold text-purple">{data.by_level['composite'] || 0}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h3 className="font-bold text-sm mb-4">Test Runner Performance</h3>
          <div className="flex justify-around items-center h-[200px]">
            <div className="text-center">
              <div className="text-4xl font-bold text-green mb-2">{data.test_runs.pass_rate}%</div>
              <div className="text-xs text-muted uppercase tracking-wider">Pass Rate</div>
            </div>
            <div className="w-[1px] h-[100px] bg-[rgba(255,255,255,0.08)]" />
            <div className="flex flex-col gap-3">
              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-1">Total Runs</div>
                <div className="text-xl font-bold">{data.test_runs.total}</div>
              </div>
              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-1">Passed</div>
                <div className="text-xl font-bold text-green">{data.test_runs.passed}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 className="font-bold text-sm mb-4">Documentation Reviews</h3>
          <div className="flex justify-around items-center h-[200px]">
            <div className="text-center">
              <div className="text-4xl font-bold text-purple mb-2">{data.doc_reviews.pass_rate}%</div>
              <div className="text-xs text-muted uppercase tracking-wider">Pass Rate</div>
            </div>
            <div className="w-[1px] h-[100px] bg-[rgba(255,255,255,0.08)]" />
            <div className="flex flex-col gap-3">
              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-1">Total Reviews</div>
                <div className="text-xl font-bold">{data.doc_reviews.total}</div>
              </div>
              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-1">Passed</div>
                <div className="text-xl font-bold text-purple">{data.doc_reviews.passed}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
