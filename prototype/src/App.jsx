import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  LayoutDashboard, FileText, Settings, Shield, Search, Plus, ChevronDown, ChevronRight,
  AlertTriangle, CheckCircle, XCircle, Zap, TrendingUp, DollarSign, Clock, Filter,
  Edit, Trash2, Play, Save, X, Info, BarChart3, PieChart, Activity
} from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, PieChart as RechartsPie, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { claims as initialClaims } from './data/syntheticClaims'
import { defaultRules } from './data/defaultRules'
import { validateClaims, testRule } from './engine/validationEngine'
import { generateAiFix } from './engine/aiFix'

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6']

// ==================== SIDEBAR ====================
function Sidebar({ activeView, setActiveView }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'claims', label: 'Claims Workbench', icon: FileText },
    { id: 'rules', label: 'Rule Manager', icon: Settings },
    { id: 'jab', label: 'JAB Audit', icon: Shield },
  ]

  return (
    <div className="w-64 min-h-screen flex flex-col" style={{ background: '#1e1b2e' }}>
      <div className="p-5 flex items-center gap-3 border-b border-white/10">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center font-bold text-white text-lg" style={{ background: '#dc2626' }}>
          C
        </div>
        <div>
          <div className="text-white font-bold text-sm tracking-wide">ClaustraRCM</div>
          <div className="text-gray-400 text-xs">AI Claim Validation</div>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(item => {
          const Icon = item.icon
          const isActive = activeView === item.id
          return (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-white/15 text-white'
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
              }`}
            >
              <Icon size={18} />
              {item.label}
            </button>
          )
        })}
      </nav>
      <div className="p-4 border-t border-white/10">
        <div className="text-gray-500 text-xs">Prototype v1.0</div>
        <div className="text-gray-600 text-xs">Oct 2026</div>
      </div>
    </div>
  )
}

// ==================== KPI CARD ====================
function KpiCard({ title, value, subtitle, icon: Icon, color, tooltip }) {
  const [showTooltip, setShowTooltip] = useState(false)
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm relative">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-gray-500 font-medium uppercase tracking-wider flex items-center gap-1">
            {title}
            {tooltip && (
              <span
                className="cursor-help relative"
                onMouseEnter={() => setShowTooltip(true)}
                onMouseLeave={() => setShowTooltip(false)}
              >
                <Info size={12} className="text-gray-400" />
                {showTooltip && (
                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 bg-gray-900 text-white text-xs p-2 rounded-lg shadow-lg z-50">
                    {tooltip}
                  </span>
                )}
              </span>
            )}
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{value}</div>
          {subtitle && <div className="mt-1 text-xs text-gray-500">{subtitle}</div>}
        </div>
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={20} className="text-white" />
        </div>
      </div>
    </div>
  )
}

// ==================== DASHBOARD VIEW ====================
function DashboardView({ claims, validationResults }) {
  const stats = useMemo(() => {
    const total = claims.length
    const cleanClaims = claims.filter(c => c.isCleanClaim).length
    const deniedClaims = claims.filter(c => c.denial).length
    const totalCharged = claims.reduce((s, c) => s + c.totalCharge, 0)
    const totalPaid = claims.reduce((s, c) => s + c.totalPaid, 0)
    const revenueAtRisk = claims.filter(c => c.denial).reduce((s, c) => s + c.totalCharge, 0)
    const passCount = validationResults.filter(r => r.status === 'pass').length
    const warnCount = validationResults.filter(r => r.status === 'warning').length
    const errorCount = validationResults.filter(r => r.status === 'error').length
    const aifixCount = validationResults.filter(r => r.status === 'aifix').length

    return {
      total, cleanClaims, deniedClaims, totalCharged, totalPaid, revenueAtRisk,
      cleanRate: total > 0 ? ((cleanClaims / total) * 100).toFixed(1) : 0,
      denialRate: total > 0 ? ((deniedClaims / total) * 100).toFixed(1) : 0,
      passCount, warnCount, errorCount, aifixCount,
    }
  }, [claims, validationResults])

  const statusData = [
    { name: 'Pass', value: stats.passCount, color: '#22c55e' },
    { name: 'Warning', value: stats.warnCount, color: '#eab308' },
    { name: 'Error', value: stats.errorCount, color: '#ef4444' },
    { name: 'AI Fix', value: stats.aifixCount, color: '#8b5cf6' },
  ].filter(d => d.value > 0)

  const arData = useMemo(() => {
    const buckets = { '0-30': 0, '31-60': 0, '61-90': 0, '90+': 0 }
    claims.forEach(c => {
      if (c.daysInAr <= 30) buckets['0-30']++
      else if (c.daysInAr <= 60) buckets['31-60']++
      else if (c.daysInAr <= 90) buckets['61-90']++
      else buckets['90+']++
    })
    return Object.entries(buckets).map(([name, value]) => ({ name, value }))
  }, [claims])

  const arColors = ['#22c55e', '#eab308', '#f97316', '#ef4444']

  const denialReasons = useMemo(() => {
    const counts = {}
    claims.forEach(c => {
      if (c.denial) {
        const cat = c.denial.rootCauseCategory
        counts[cat] = (counts[cat] || 0) + 1
      }
    })
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
  }, [claims])

  const monthlyData = useMemo(() => {
    const months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']
    return months.map((m, i) => ({
      name: m,
      collections: Math.round(180000 + Math.random() * 120000 + i * 15000),
      charges: Math.round(250000 + Math.random() * 150000 + i * 20000),
    }))
  }, [])

  const revenueTrend = useMemo(() => {
    const months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']
    return months.map((m, i) => ({
      name: m,
      revenue: Math.round(220000 + i * 18000 + Math.random() * 30000),
      target: Math.round(250000 + i * 15000),
    }))
  }, [])

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Executive Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Real-time revenue cycle intelligence</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <KpiCard
          title="Total Claims" value={stats.total} subtitle="Active claims in system"
          icon={FileText} color="bg-blue-500"
          tooltip="Count of all claims currently loaded in the validation system"
        />
        <KpiCard
          title="Clean Claim Rate" value={`${stats.cleanRate}%`} subtitle={`${stats.cleanClaims} clean claims`}
          icon={CheckCircle} color="bg-green-500"
          tooltip="Percentage of claims that pass all pre-submission checks without errors"
        />
        <KpiCard
          title="Denial Rate" value={`${stats.denialRate}%`} subtitle={`${stats.deniedClaims} denied claims`}
          icon={XCircle} color="bg-red-500"
          tooltip="Percentage of claims with a denial on record"
        />
        <KpiCard
          title="Revenue at Risk" value={`$${(stats.revenueAtRisk / 1000).toFixed(0)}K`}
          subtitle="From denied claims"
          icon={DollarSign} color="bg-purple-500"
          tooltip="Total billed amount of all denied claims — represents potential revenue loss"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <TrendingUp size={16} className="text-blue-500" /> Revenue Trends
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={revenueTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
              <Tooltip formatter={v => [`$${v.toLocaleString()}`, '']} />
              <Legend />
              <Line type="monotone" dataKey="revenue" stroke="#6366f1" strokeWidth={2} dot={{ r: 4 }} name="Revenue" />
              <Line type="monotone" dataKey="target" stroke="#94a3b8" strokeWidth={2} strokeDasharray="5 5" dot={false} name="Target" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <PieChart size={16} className="text-green-500" /> Claim Validation Status
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <RechartsPie>
              <Pie data={statusData} cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {statusData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip />
            </RechartsPie>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Clock size={16} className="text-orange-500" /> AR Aging Breakdown
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <RechartsPie>
              <Pie data={arData} cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}d: ${value}`}>
                {arData.map((entry, i) => <Cell key={i} fill={arColors[i]} />)}
              </Pie>
              <Tooltip />
            </RechartsPie>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-500" /> Top Denial Reasons
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={denialReasons} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={100} />
              <Tooltip />
              <Bar dataKey="count" fill="#ef4444" radius={[0, 4, 4, 0]} name="Denials" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <BarChart3 size={16} className="text-indigo-500" /> Monthly Collections vs Charges
        </h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={monthlyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
            <Tooltip formatter={v => [`$${v.toLocaleString()}`, '']} />
            <Legend />
            <Bar dataKey="charges" fill="#c7d2fe" radius={[4, 4, 0, 0]} name="Charges" />
            <Bar dataKey="collections" fill="#6366f1" radius={[4, 4, 0, 0]} name="Collections" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ==================== STATUS BADGE ====================
function StatusBadge({ status }) {
  const config = {
    pass: { className: 'status-pass', icon: CheckCircle, label: 'Pass' },
    warning: { className: 'status-warning', icon: AlertTriangle, label: 'Warning' },
    error: { className: 'status-error', icon: XCircle, label: 'Error' },
    aifix: { className: 'status-aifix', icon: Zap, label: 'AI Fix' },
  }
  const c = config[status] || config.pass
  const Icon = c.icon
  return (
    <span className={c.className}>
      <Icon size={12} />
      {c.label}
    </span>
  )
}

// ==================== EXPANDED CLAIM ROW ====================
function ExpandedClaimRow({ claim, result, onApplyAiFix }) {
  const [aiFixes, setAiFixes] = useState([])

  useEffect(() => {
    if (result && result.failures.length > 0) {
      const fixes = result.failures.map(f => {
        const fix = generateAiFix(claim, f)
        return { failure: f, fix, applied: false }
      }).filter(f => f.fix !== null)
      setAiFixes(fixes)
    }
  }, [claim, result])

  return (
    <div className="animate-fade-in bg-gray-50 border-t border-gray-100 px-6 py-4">
      <div className="grid grid-cols-3 gap-6">
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Claim Details</h4>
          <div className="space-y-1.5 text-sm">
            <div><span className="text-gray-500">Patient:</span> <span className="font-medium">{claim.patientId}</span></div>
            <div><span className="text-gray-500">Provider:</span> <span className="font-medium">{claim.providerName}</span></div>
            <div><span className="text-gray-500">Specialty:</span> <span className="font-medium">{claim.specialty}</span></div>
            <div><span className="text-gray-500">Service Date:</span> <span className="font-medium">{claim.serviceDate}</span></div>
            <div><span className="text-gray-500">Claim Type:</span> <span className="font-medium">{claim.claimType}</span></div>
          </div>
        </div>
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Diagnosis & Billing</h4>
          <div className="space-y-1.5 text-sm">
            <div><span className="text-gray-500">ICD-10:</span> <span className="font-medium">{claim.primaryIcd10 || '(missing)'}</span></div>
            <div><span className="text-gray-500">Description:</span> <span className="font-medium">{claim.diagnosisDescription || '(missing)'}</span></div>
            <div><span className="text-gray-500">Charged:</span> <span className="font-medium">${claim.totalCharge.toLocaleString()}</span></div>
            <div><span className="text-gray-500">Allowed:</span> <span className="font-medium">${claim.totalAllowed.toLocaleString()}</span></div>
            <div><span className="text-gray-500">Paid:</span> <span className="font-medium">${claim.totalPaid.toLocaleString()}</span></div>
          </div>
        </div>
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Authorization & Status</h4>
          <div className="space-y-1.5 text-sm">
            <div><span className="text-gray-500">PA Required:</span> <span className="font-medium">{claim.paRequired ? 'Yes' : 'No'}</span></div>
            <div><span className="text-gray-500">PA Obtained:</span> <span className="font-medium">{claim.paObtained ? 'Yes' : 'No'}</span></div>
            <div><span className="text-gray-500">PA Number:</span> <span className="font-medium">{claim.paNumber || 'N/A'}</span></div>
            <div><span className="text-gray-500">Days in AR:</span> <span className="font-medium">{claim.daysInAr}</span></div>
            <div><span className="text-gray-500">Clean Claim:</span> <span className="font-medium">{claim.isCleanClaim ? 'Yes' : 'No'}</span></div>
          </div>
        </div>
      </div>

      {result && result.failures.length > 0 && (
        <div className="mt-4 space-y-2">
          <h4 className="text-xs font-semibold text-gray-500 uppercase">Validation Failures</h4>
          {result.failures.map((f, i) => (
            <div key={i} className={`rounded-lg p-3 text-sm ${f.severity === 'error' ? 'bg-red-50 border border-red-200' : 'bg-yellow-50 border border-yellow-200'}`}>
              <div className="flex items-center gap-2 font-medium">
                {f.severity === 'error' ? <XCircle size={14} className="text-red-500" /> : <AlertTriangle size={14} className="text-yellow-600" />}
                <span>{f.ruleName}</span>
                <span className="text-xs text-gray-400">({f.ruleId})</span>
              </div>
              <div className="mt-1 text-gray-600">{f.message}</div>
              <div className="mt-1 text-gray-500 italic">Action: {f.recommendedAction}</div>
            </div>
          ))}
        </div>
      )}

      {aiFixes.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">AI Fix Suggestions</h4>
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500">Description</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500">Confidence</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500">Linked Rule</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500">Status</th>
                  <th className="text-right px-4 py-2 text-xs font-semibold text-gray-500">Action</th>
                </tr>
              </thead>
              <tbody>
                {aiFixes.map((af, i) => (
                  <tr key={i} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-gray-800">{af.fix.description}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{af.fix.reasoning}</div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-200 rounded-full h-1.5">
                          <div className="h-1.5 rounded-full bg-purple-500" style={{ width: `${af.fix.confidence * 100}%` }} />
                        </div>
                        <span className="text-xs font-medium">{(af.fix.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-500">{af.failure.ruleId}</td>
                    <td className="px-4 py-2.5">
                      {af.applied ? (
                        <span className="status-pass"><CheckCircle size={12} />Applied</span>
                      ) : (
                        <span className="text-xs text-gray-500">Pending</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {!af.applied && af.fix.suggestedValue !== null && (
                        <button
                          onClick={() => {
                            onApplyAiFix(claim.claimId, af.fix.field, af.fix.suggestedValue)
                            setAiFixes(prev => prev.map((f, idx) => idx === i ? { ...f, applied: true } : f))
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1 bg-purple-600 text-white text-xs font-medium rounded-lg hover:bg-purple-700 transition-colors"
                        >
                          <Zap size={12} /> Apply Fix
                        </button>
                      )}
                      {!af.applied && af.fix.suggestedValue === null && (
                        <span className="text-xs text-gray-400 italic">Manual review</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {claim.denial && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3">
          <h4 className="text-xs font-semibold text-red-700 uppercase mb-1">Denial Information</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="text-red-500">Reason:</span> <span className="text-red-800">{claim.denial.denialReasonText}</span></div>
            <div><span className="text-red-500">CARC:</span> <span className="text-red-800">{claim.denial.carcCode} - {claim.denial.carcDescription}</span></div>
            <div><span className="text-red-500">Amount:</span> <span className="text-red-800">${claim.denial.denialAmount.toLocaleString()}</span></div>
            <div><span className="text-red-500">Preventable:</span> <span className="text-red-800">{claim.denial.isPreventable ? 'Yes' : 'No'}</span></div>
          </div>
        </div>
      )}
    </div>
  )
}

// ==================== CLAIMS WORKBENCH VIEW ====================
function ClaimsWorkbenchView({ claims, validationResults, onApplyAiFix }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [payerFilter, setPayerFilter] = useState('all')
  const [expandedRow, setExpandedRow] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const perPage = 15
  const [sortField, setSortField] = useState('claimId')
  const [sortDir, setSortDir] = useState('asc')

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const resultMap = useMemo(() => {
    const map = {}
    validationResults.forEach(r => { map[r.claimId] = r })
    return map
  }, [validationResults])

  const payers = useMemo(() => [...new Set(claims.map(c => c.payerName))].sort(), [claims])

  const filtered = useMemo(() => {
    return claims.filter(c => {
      const r = resultMap[c.claimId]
      if (searchTerm) {
        const term = searchTerm.toLowerCase()
        const matches = c.claimId.toLowerCase().includes(term) ||
          c.payerName.toLowerCase().includes(term) ||
          c.providerName.toLowerCase().includes(term)
        if (!matches) return false
      }
      if (statusFilter !== 'all' && r && r.status !== statusFilter) return false
      if (payerFilter !== 'all' && c.payerName !== payerFilter) return false
      return true
    })
  }, [claims, resultMap, searchTerm, statusFilter, payerFilter])

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const r1 = resultMap[a.claimId]
      const r2 = resultMap[b.claimId]
      let v1, v2
      switch (sortField) {
        case 'claimId': v1 = a.claimId; v2 = b.claimId; break
        case 'billedAmount': v1 = a.billedAmount; v2 = b.billedAmount; break
        case 'riskScore': v1 = r1?.riskScore ?? 0; v2 = r2?.riskScore ?? 0; break
        case 'status': v1 = r1?.status ?? ''; v2 = r2?.status ?? ''; break
        case 'payerName': v1 = a.payerName; v2 = b.payerName; break
        default: v1 = a[sortField]; v2 = b[sortField]; break
      }
      if (typeof v1 === 'number' && typeof v2 === 'number') return sortDir === 'asc' ? v1 - v2 : v2 - v1
      return sortDir === 'asc' ? String(v1).localeCompare(String(v2)) : String(v2).localeCompare(String(v1))
    })
  }, [filtered, sortField, sortDir, resultMap])

  const totalPages = Math.ceil(sorted.length / perPage)
  const paginated = sorted.slice((currentPage - 1) * perPage, currentPage * perPage)

  useEffect(() => { setCurrentPage(1) }, [searchTerm, statusFilter, payerFilter])

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Claims Workbench</h1>
        <div className="text-sm text-gray-500">{filtered.length} claims</div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search claims, payers, providers..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-gray-400" />
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All Status</option>
            <option value="pass">Pass</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="aifix">AI Fix</option>
          </select>
          <select
            value={payerFilter}
            onChange={e => setPayerFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All Payers</option>
            {payers.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase w-8"></th>
              <th onClick={() => handleSort('claimId')} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-indigo-600 select-none">Claim Code {sortField === 'claimId' && (sortDir === 'asc' ? '↑' : '↓')}</th>
              <th onClick={() => handleSort('status')} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-indigo-600 select-none">Status {sortField === 'status' && (sortDir === 'asc' ? '↑' : '↓')}</th>
              <th onClick={() => handleSort('payerName')} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-indigo-600 select-none">Payer {sortField === 'payerName' && (sortDir === 'asc' ? '↑' : '↓')}</th>
              <th onClick={() => handleSort('billedAmount')} className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-indigo-600 select-none">Billed Amount {sortField === 'billedAmount' && (sortDir === 'asc' ? '↑' : '↓')}</th>
              <th onClick={() => handleSort('riskScore')} className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-indigo-600 select-none">AI Risk % {sortField === 'riskScore' && (sortDir === 'asc' ? '↑' : '↓')}</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {paginated.map(claim => {
              const r = resultMap[claim.claimId]
              const isExpanded = expandedRow === claim.claimId
              return (
                <React.Fragment key={claim.claimId}>
                  <tr
                    onClick={() => setExpandedRow(isExpanded ? null : claim.claimId)}
                    className={`border-b border-gray-50 cursor-pointer transition-colors ${isExpanded ? 'bg-indigo-50/50' : 'hover:bg-gray-50'}`}
                  >
                    <td className="px-4 py-3">
                      {isExpanded ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm font-medium text-gray-900">{claim.claimId}</span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r ? r.status : 'pass'} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded bg-indigo-100 flex items-center justify-center text-xs font-bold text-indigo-600">
                          {claim.payerName.charAt(0)}
                        </div>
                        <span className="text-sm text-gray-700">{claim.payerName}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-medium text-gray-900">${claim.totalCharge.toLocaleString()}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {r && (
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 bg-gray-200 rounded-full h-1.5">
                            <div
                              className={`h-1.5 rounded-full ${r.riskScore >= 60 ? 'bg-red-500' : r.riskScore >= 30 ? 'bg-yellow-500' : 'bg-green-500'}`}
                              style={{ width: `${r.riskScore}%` }}
                            />
                          </div>
                          <span className={`text-xs font-semibold ${r.riskScore >= 60 ? 'text-red-600' : r.riskScore >= 30 ? 'text-yellow-600' : 'text-green-600'}`}>
                            {r.riskScore}%
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-500">{claim.submissionDate}</span>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={7}>
                        <ExpandedClaimRow claim={claim} result={r} onApplyAiFix={onApplyAiFix} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-500">
            Showing {(currentPage - 1) * perPage + 1}-{Math.min(currentPage * perPage, sorted.length)} of {sorted.length}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).slice(
              Math.max(0, currentPage - 3), Math.min(totalPages, currentPage + 2)
            ).map(page => (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                className={`px-3 py-1.5 text-sm rounded-lg ${currentPage === page ? 'bg-indigo-600 text-white' : 'border border-gray-200 hover:bg-gray-50'}`}
              >
                {page}
              </button>
            ))}
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ==================== CONDITION BUILDER ====================
const CLAIM_FIELDS = [
  { value: 'primaryIcd10', label: 'Primary ICD-10' },
  { value: 'paRequired', label: 'PA Required' },
  { value: 'paObtained', label: 'PA Obtained' },
  { value: 'paNumber', label: 'PA Number' },
  { value: 'totalCharge', label: 'Total Charge' },
  { value: 'totalAllowed', label: 'Total Allowed' },
  { value: 'payerName', label: 'Payer Name' },
  { value: 'claimType', label: 'Claim Type' },
  { value: 'daysInAr', label: 'Days in AR' },
  { value: 'isCleanClaim', label: 'Is Clean Claim' },
  { value: 'departmentName', label: 'Department' },
  { value: 'status', label: 'Claim Status' },
  { value: 'diagnosisDescription', label: 'Diagnosis Description' },
]

const OPERATORS = [
  { value: 'isEmpty', label: 'Is Empty' },
  { value: 'isNotEmpty', label: 'Is Not Empty' },
  { value: 'equals', label: 'Equals' },
  { value: 'notEquals', label: 'Not Equals' },
  { value: 'greaterThan', label: 'Greater Than' },
  { value: 'lessThan', label: 'Less Than' },
  { value: 'contains', label: 'Contains' },
]

const CATEGORIES = ['Coding', 'Eligibility', 'Authorization', 'Demographics', 'Billing', 'Required Fields', 'Payer-Specific']

function RuleBuilderPanel({ isOpen, onClose, onSave, editingRule, claims }) {
  const [form, setForm] = useState({
    id: '', name: '', description: '', category: 'Coding', severity: 'error',
    status: 'active', recommendedAction: '',
    scopeType: 'all', scopeValue: '',
    conditions: [{ field: 'primaryIcd10', operator: 'isEmpty', value: '' }],
    conditionLogic: 'AND',
  })
  const [testResults, setTestResults] = useState(null)

  useEffect(() => {
    if (editingRule) {
      setForm({
        id: editingRule.id,
        name: editingRule.name,
        description: editingRule.description,
        category: editingRule.category,
        severity: editingRule.severity,
        status: editingRule.status,
        recommendedAction: editingRule.recommendedAction,
        scopeType: editingRule.scope.type,
        scopeValue: editingRule.scope.value || '',
        conditions: editingRule.conditions.length > 0 ? editingRule.conditions : [{ field: 'primaryIcd10', operator: 'isEmpty', value: '' }],
        conditionLogic: editingRule.conditionLogic || 'AND',
      })
    } else {
      const nextId = `RULE-${String(Date.now()).slice(-3)}`
      setForm({
        id: nextId, name: '', description: '', category: 'Coding', severity: 'error',
        status: 'active', recommendedAction: '',
        scopeType: 'all', scopeValue: '',
        conditions: [{ field: 'primaryIcd10', operator: 'isEmpty', value: '' }],
        conditionLogic: 'AND',
      })
    }
    setTestResults(null)
  }, [editingRule, isOpen])

  const updateCondition = (index, key, val) => {
    setForm(prev => ({
      ...prev,
      conditions: prev.conditions.map((c, i) => i === index ? { ...c, [key]: val } : c)
    }))
  }

  const addCondition = () => {
    setForm(prev => ({
      ...prev,
      conditions: [...prev.conditions, { field: 'primaryIcd10', operator: 'isEmpty', value: '' }]
    }))
  }

  const removeCondition = (index) => {
    if (form.conditions.length <= 1) return
    setForm(prev => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index)
    }))
  }

  const handleTest = () => {
    const rule = {
      ...form,
      scope: { type: form.scopeType, value: form.scopeValue || undefined },
    }
    const result = testRule(claims, rule)
    setTestResults(result)
  }

  const handleSave = () => {
    if (!form.name.trim()) return
    const now = new Date().toISOString().split('T')[0]
    const rule = {
      id: form.id,
      name: form.name,
      description: form.description,
      category: form.category,
      severity: form.severity,
      status: form.status,
      recommendedAction: form.recommendedAction,
      scope: { type: form.scopeType, value: form.scopeValue || undefined },
      conditions: form.conditions,
      conditionLogic: form.conditionLogic,
      createdAt: editingRule ? editingRule.createdAt : now,
      updatedAt: now,
    }
    onSave(rule)
    onClose()
  }

  if (!isOpen) return null

  const payers = [...new Set(claims.map(c => c.payerName))].sort()

  return (
    <div className="fixed inset-y-0 right-0 w-[520px] bg-white shadow-2xl border-l border-gray-200 z-50 flex flex-col animate-slide-in">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h2 className="text-lg font-bold text-gray-900">{editingRule ? 'Edit Rule' : 'Add New Custom Rule'}</h2>
        <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded-lg transition-colors">
          <X size={20} className="text-gray-500" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Rule Definition */}
        <div>
          <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
            <Settings size={14} /> Rule Definition
          </h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Rule ID</label>
                <input value={form.id} disabled className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-gray-50 text-gray-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Category</label>
                <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Rule Name</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g., Missing Primary Diagnosis Code" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2} placeholder="Describe what this rule checks..." className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Severity</label>
                <select value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))} className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option value="error">Error</option>
                  <option value="warning">Warning</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
                <div className="flex items-center gap-2 mt-1">
                  <button
                    onClick={() => setForm(f => ({ ...f, status: f.status === 'active' ? 'inactive' : 'active' }))}
                    className={`relative w-10 h-5 rounded-full transition-colors ${form.status === 'active' ? 'bg-green-500' : 'bg-gray-300'}`}
                  >
                    <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.status === 'active' ? 'translate-x-5' : 'translate-x-0.5'}`} />
                  </button>
                  <span className="text-sm text-gray-600">{form.status === 'active' ? 'Active' : 'Inactive'}</span>
                </div>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Recommended Action</label>
              <textarea value={form.recommendedAction} onChange={e => setForm(f => ({ ...f, recommendedAction: e.target.value }))} rows={2} placeholder="What should the user do when this rule triggers..." className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
            </div>
          </div>
        </div>

        {/* Scope Definition */}
        <div>
          <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
            <Filter size={14} /> Scope Definition
          </h3>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name="scope" checked={form.scopeType === 'all'} onChange={() => setForm(f => ({ ...f, scopeType: 'all', scopeValue: '' }))} className="text-indigo-600" />
              All Claims
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name="scope" checked={form.scopeType === 'payer'} onChange={() => setForm(f => ({ ...f, scopeType: 'payer' }))} className="text-indigo-600" />
              Specific Payer
            </label>
            {form.scopeType === 'payer' && (
              <select value={form.scopeValue} onChange={e => setForm(f => ({ ...f, scopeValue: e.target.value }))} className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 ml-6">
                <option value="">Select payer...</option>
                {payers.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name="scope" checked={form.scopeType === 'claimType'} onChange={() => setForm(f => ({ ...f, scopeType: 'claimType' }))} className="text-indigo-600" />
              Claim Type
            </label>
            {form.scopeType === 'claimType' && (
              <select value={form.scopeValue} onChange={e => setForm(f => ({ ...f, scopeValue: e.target.value }))} className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 ml-6">
                <option value="">Select type...</option>
                <option value="Professional">Professional</option>
                <option value="Institutional">Institutional</option>
              </select>
            )}
          </div>
        </div>

        {/* Condition Builder */}
        <div>
          <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
            <Activity size={14} /> Condition Builder
          </h3>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs text-gray-500">Logic:</span>
            <button
              onClick={() => setForm(f => ({ ...f, conditionLogic: 'AND' }))}
              className={`px-3 py-1 text-xs font-medium rounded-lg transition-colors ${form.conditionLogic === 'AND' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600'}`}
            >AND</button>
            <button
              onClick={() => setForm(f => ({ ...f, conditionLogic: 'OR' }))}
              className={`px-3 py-1 text-xs font-medium rounded-lg transition-colors ${form.conditionLogic === 'OR' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600'}`}
            >OR</button>
          </div>
          <div className="space-y-2">
            {form.conditions.map((cond, i) => (
              <div key={i} className="flex items-center gap-2 bg-gray-50 p-2 rounded-lg border border-gray-200">
                <select value={cond.field} onChange={e => updateCondition(i, 'field', e.target.value)} className="flex-1 px-2 py-1.5 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500">
                  {CLAIM_FIELDS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                </select>
                <select value={cond.operator} onChange={e => updateCondition(i, 'operator', e.target.value)} className="w-28 px-2 py-1.5 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500">
                  {OPERATORS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                {!['isEmpty', 'isNotEmpty'].includes(cond.operator) && (
                  <input
                    value={cond.value}
                    onChange={e => updateCondition(i, 'value', e.target.value)}
                    placeholder="Value"
                    className="w-28 px-2 py-1.5 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                )}
                <button onClick={() => removeCondition(i)} className="p-1 text-gray-400 hover:text-red-500 transition-colors" title="Remove condition">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
          <button onClick={addCondition} className="mt-2 flex items-center gap-1 text-xs text-indigo-600 font-medium hover:text-indigo-700">
            <Plus size={14} /> Add Condition
          </button>
        </div>

        {/* Test Rule */}
        <div>
          <button
            onClick={handleTest}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 text-white text-sm font-medium rounded-lg hover:bg-gray-700 transition-colors"
          >
            <Play size={14} /> Test Rule
          </button>
          {testResults && (
            <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-3 animate-fade-in">
              <div className="text-sm font-medium text-blue-800">Test Results</div>
              <div className="mt-1 text-sm text-blue-700">
                <span className="font-semibold">{testResults.matched.length}</span> claims matched,{' '}
                <span className="font-semibold">{testResults.unaffected.length}</span> unaffected out of {testResults.total} total
              </div>
              {testResults.matched.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {testResults.matched.slice(0, 10).map(id => (
                    <span key={id} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">{id}</span>
                  ))}
                  {testResults.matched.length > 10 && <span className="text-xs text-blue-500">+{testResults.matched.length - 10} more</span>}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex items-center justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors">
          Cancel
        </button>
        <button onClick={handleSave} className="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2">
          <Save size={14} /> {editingRule ? 'Update Rule' : 'Add Rule'}
        </button>
      </div>
    </div>
  )
}

// ==================== RULE MANAGER VIEW ====================
function RuleManagerView({ rules, claims, onAddRule, onUpdateRule, onDeleteRule }) {
  const [panelOpen, setPanelOpen] = useState(false)
  const [editingRule, setEditingRule] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  const handleEdit = (rule) => {
    setEditingRule(rule)
    setPanelOpen(true)
  }

  const handleAdd = () => {
    setEditingRule(null)
    setPanelOpen(true)
  }

  const handleSave = (rule) => {
    if (editingRule) {
      onUpdateRule(rule)
    } else {
      onAddRule(rule)
    }
  }

  const handleDelete = (ruleId) => {
    onDeleteRule(ruleId)
    setDeleteConfirm(null)
  }

  const handleToggleStatus = (rule) => {
    onUpdateRule({ ...rule, status: rule.status === 'active' ? 'inactive' : 'active' })
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Rule Manager</h1>
        <button
          onClick={handleAdd}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors"
        >
          <Plus size={16} /> Add Rule
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Rule ID</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Name</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Category</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Severity</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Scope</th>
              <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rules.map(rule => (
              <tr key={rule.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 text-sm font-mono text-gray-600">{rule.id}</td>
                <td className="px-4 py-3">
                  <div className="text-sm font-medium text-gray-900">{rule.name}</div>
                  <div className="text-xs text-gray-500 mt-0.5 line-clamp-1">{rule.description}</div>
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs font-medium rounded-full">{rule.category}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${rule.severity === 'error' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                    {rule.severity}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {rule.scope.type === 'all' ? 'All Claims' : `${rule.scope.type}: ${rule.scope.value}`}
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => handleToggleStatus(rule)}
                    className={`relative w-10 h-5 rounded-full transition-colors ${rule.status === 'active' ? 'bg-green-500' : 'bg-gray-300'}`}
                  >
                    <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${rule.status === 'active' ? 'translate-x-5' : 'translate-x-0.5'}`} />
                  </button>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => handleEdit(rule)} className="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors" title="Edit">
                      <Edit size={14} />
                    </button>
                    {deleteConfirm === rule.id ? (
                      <div className="flex items-center gap-1">
                        <button onClick={() => handleDelete(rule.id)} className="px-2 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700">Yes</button>
                        <button onClick={() => setDeleteConfirm(null)} className="px-2 py-1 bg-gray-200 text-gray-700 text-xs rounded hover:bg-gray-300">No</button>
                      </div>
                    ) : (
                      <button onClick={() => setDeleteConfirm(rule.id)} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="Delete">
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <RuleBuilderPanel
        isOpen={panelOpen}
        onClose={() => { setPanelOpen(false); setEditingRule(null) }}
        onSave={handleSave}
        editingRule={editingRule}
        claims={claims}
      />
    </div>
  )
}

// ==================== JAB AUDIT VIEW ====================
function JABAuditView() {
  const steps = [
    {
      id: 1, title: 'Pre-Submission Validation', icon: CheckCircle, color: 'bg-green-500',
      description: 'AI-powered rule engine validates every claim against payer-specific requirements, coding standards, and authorization rules before submission.',
      features: ['Real-time validation against 100+ rules', 'AI-suggested corrections for common errors', 'Risk scoring to prioritize review', 'Clean claim rate optimization'],
    },
    {
      id: 2, title: 'Claim Submission', icon: FileText, color: 'bg-blue-500',
      description: 'Clean, validated claims are submitted to payers electronically with all required documentation attached.',
      features: ['EDI 837 compliant formatting', 'Automated attachment of supporting documents', 'Real-time submission tracking', 'Batch processing capabilities'],
    },
    {
      id: 3, title: 'Payer Adjudication', icon: Clock, color: 'bg-orange-500',
      description: 'Monitor claim status through the adjudication process with automated follow-up on aging claims.',
      features: ['ERA/835 processing and reconciliation', 'Automated status inquiries (276/277)', 'Denial tracking and categorization', 'AR aging management'],
    },
    {
      id: 4, title: 'Underpayment Recovery (JAB Audit)', icon: DollarSign, color: 'bg-purple-500',
      description: 'Systematic identification of underpaid claims by comparing actual payments against contracted rates and fee schedules.',
      features: ['Contract term comparison engine', 'Fee schedule variance detection', 'Automated appeal letter generation', 'Recovery tracking dashboard'],
    },
  ]

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">JAB Audit Integration</h1>
        <p className="text-sm text-gray-500 mt-1">Conceptual workflow for end-to-end revenue cycle optimization</p>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-start gap-3">
        <AlertTriangle size={20} className="text-yellow-600 flex-shrink-0 mt-0.5" />
        <div>
          <div className="text-sm font-semibold text-yellow-800">Conceptual Integration -- Not a Live Connection</div>
          <div className="text-sm text-yellow-700 mt-0.5">This view illustrates the proposed integration between ClaustraRCM validation and JAB Audit underpayment recovery. Actual system connections require additional implementation.</div>
        </div>
      </div>

      {/* Workflow diagram */}
      <div className="flex items-center justify-between gap-2">
        {steps.map((step, i) => (
          <React.Fragment key={step.id}>
            <div className="flex-1 bg-white rounded-xl border border-gray-100 shadow-sm p-4 relative">
              <div className={`w-10 h-10 ${step.color} rounded-lg flex items-center justify-center mb-3`}>
                <step.icon size={20} className="text-white" />
              </div>
              <div className="text-xs text-gray-400 font-semibold uppercase">Step {step.id}</div>
              <h3 className="text-sm font-bold text-gray-900 mt-1">{step.title}</h3>
            </div>
            {i < steps.length - 1 && (
              <div className="flex-shrink-0">
                <ChevronRight size={20} className="text-gray-300" />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Detailed cards */}
      <div className="grid grid-cols-2 gap-4">
        {steps.map(step => (
          <div key={step.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className={`w-10 h-10 ${step.color} rounded-lg flex items-center justify-center`}>
                <step.icon size={20} className="text-white" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-gray-900">{step.title}</h3>
                <div className="text-xs text-gray-400">Phase {step.id}</div>
              </div>
            </div>
            <p className="text-sm text-gray-600 mb-3">{step.description}</p>
            <ul className="space-y-1.5">
              {step.features.map((f, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-gray-700">
                  <CheckCircle size={12} className="text-green-500 flex-shrink-0" />
                  {f}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Combined value proposition */}
      <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl border border-indigo-100 p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-2">Combined Value Proposition</h3>
        <p className="text-sm text-gray-700 mb-4">
          By integrating pre-submission AI validation with post-payment underpayment recovery, organizations can capture revenue from both ends of the revenue cycle:
        </p>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white/70 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-green-600">15-25%</div>
            <div className="text-xs text-gray-600 mt-1">Reduction in denials through pre-submission validation</div>
          </div>
          <div className="bg-white/70 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">3-5%</div>
            <div className="text-xs text-gray-600 mt-1">Revenue recovery from underpaid claims</div>
          </div>
          <div className="bg-white/70 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-purple-600">40%</div>
            <div className="text-xs text-gray-600 mt-1">Faster resolution with AI-assisted workflows</div>
          </div>
        </div>
      </div>

      {/* Future Integration Requirements */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
          <Settings size={14} /> Future Integration Requirements
        </h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            'Clearinghouse EDI connectivity (837/835)',
            'Real-time eligibility verification API (270/271)',
            'Payer portal API integrations',
            'EHR/PM system bidirectional interface',
            'Contract management database',
            'Fee schedule repository',
            'Automated appeal workflow engine',
            'Payment variance detection algorithms',
          ].map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-gray-600">
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ==================== MAIN APP COMPONENT ====================
export default function App() {
  const [activeView, setActiveView] = useState('dashboard')
  const [claims, setClaims] = useState(initialClaims)
  const [rules, setRules] = useState(defaultRules)
  const [validationResults, setValidationResults] = useState([])

  // Run validation whenever claims or rules change
  useEffect(() => {
    const results = validateClaims(claims, rules)
    setValidationResults(results)
  }, [claims, rules])

  const handleApplyAiFix = useCallback((claimId, field, value) => {
    setClaims(prev => prev.map(c => {
      if (c.claimId === claimId) {
        return { ...c, [field]: value }
      }
      return c
    }))
  }, [])

  const handleAddRule = useCallback((rule) => {
    setRules(prev => [...prev, rule])
  }, [])

  const handleUpdateRule = useCallback((updatedRule) => {
    setRules(prev => prev.map(r => r.id === updatedRule.id ? updatedRule : r))
  }, [])

  const handleDeleteRule = useCallback((ruleId) => {
    setRules(prev => prev.filter(r => r.id !== ruleId))
  }, [])

  // Tab bar for Claims/Rules views
  const TabBar = () => (
    <div className="bg-white border-b border-gray-200 px-6">
      <div className="flex gap-0">
        <button
          onClick={() => setActiveView('claims')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeView === 'claims'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Claims Workbench
        </button>
        <button
          onClick={() => setActiveView('rules')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeView === 'rules'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Rule Manager
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      <main className="flex-1 overflow-auto">
        {(activeView === 'claims' || activeView === 'rules') && <TabBar />}
        {activeView === 'dashboard' && (
          <DashboardView claims={claims} validationResults={validationResults} />
        )}
        {activeView === 'claims' && (
          <ClaimsWorkbenchView
            claims={claims}
            validationResults={validationResults}
            onApplyAiFix={handleApplyAiFix}
          />
        )}
        {activeView === 'rules' && (
          <RuleManagerView
            rules={rules}
            claims={claims}
            onAddRule={handleAddRule}
            onUpdateRule={handleUpdateRule}
            onDeleteRule={handleDeleteRule}
          />
        )}
        {activeView === 'jab' && <JABAuditView />}
      </main>
    </div>
  )
}
