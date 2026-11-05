/** Small SVG charts used by the Analyse and Backtest screens. Colours come from the theme tokens. */
const W = 860

export function LineChart({ series, height = 230, label }: { series: { points: { x: number; y: number }[]; dashed?: boolean; color?: string }[]; height?: number; label: string }) {
  const all = series.flatMap(s => s.points)
  if (!all.length) return <div className="muted small pad">Nothing to chart yet.</div>
  const xs = all.map(p => p.x), ys = [0, ...all.map(p => p.y)]
  const x0 = Math.min(...xs), x1 = Math.max(...xs) || 1, y0 = Math.min(...ys), y1 = Math.max(...ys)
  const sx = (x: number) => 50 + ((x - x0) / (x1 - x0 || 1)) * (W - 70), sy = (y: number) => height - 30 - ((y - y0) / (y1 - y0 || 1)) * (height - 60)
  const ticks = [y0, (y0 + y1) / 2, y1]
  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" role="img" aria-label={label} style={{ display: 'block' }}>
      {ticks.map((t, i) => <g key={i}><line x1={50} x2={W - 20} y1={sy(t)} y2={sy(t)} stroke="var(--border)" /><text x={4} y={sy(t) + 4} fontSize="8" fill="var(--text-muted)">£{t.toFixed(0)}</text></g>)}
      <line x1={50} x2={W - 20} y1={sy(0)} y2={sy(0)} stroke="var(--border-strong)" />
      {series.map((s, i) => <path key={i} d={s.points.map((p, j) => `${j ? 'L' : 'M'}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(' ')} fill="none" stroke={s.color ?? 'var(--brand)'} strokeWidth={s.dashed ? 2 : 2.5} strokeDasharray={s.dashed ? '5 4' : undefined} />)}
    </svg>)
}

/** Equity curve with drawdown bars under the zero line and a shaded out-of-sample region. */
export function EquityChart({ curve, drawdown, oosFrom }: { curve: number[]; drawdown: number[]; oosFrom: number | null }) {
  if (!curve.length) return <div className="muted small pad">No trades to chart.</div>
  const H = 250, n = curve.length, hi = Math.max(0, ...curve), lo = Math.min(0, ...curve), dmax = Math.max(1, ...drawdown)
  const sx = (i: number) => 50 + (n === 1 ? 0 : (i / (n - 1)) * (W - 70)), zero = 20 + (hi / (hi - lo || 1)) * (H - 90), sy = (v: number) => zero - (v / (hi - lo || 1)) * (H - 90)
  const bw = Math.max(3, (W - 70) / n - 3)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Backtest equity curve with drawdown bars and a shaded out-of-sample period" style={{ display: 'block' }}>
      {oosFrom != null && <><rect x={sx(oosFrom) - bw / 2} y={10} width={W - 20 - (sx(oosFrom) - bw / 2)} height={H - 50} fill="var(--surface-raised)" opacity=".7" /><text x={sx(oosFrom) + 4} y={26} fontSize="8" fill="var(--text-muted)">Out-of-sample: not used to tune the script</text></>}
      <line x1={50} x2={W - 20} y1={zero} y2={zero} stroke="var(--border-strong)" />
      {drawdown.map((d, i) => <rect key={i} x={sx(i) - bw / 2} y={zero} width={bw} height={(d / dmax) * 40} fill="var(--loss)" opacity=".5" />)}
      <path d={curve.map((v, i) => `${i ? 'L' : 'M'}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join(' ')} fill="none" stroke="var(--brand)" strokeWidth="2.5" />
      <text x={4} y={zero + 4} fontSize="8" fill="var(--text-muted)">£0</text><text x={4} y={sy(hi) + 4} fontSize="8" fill="var(--text-muted)">£{hi.toFixed(0)}</text>
    </svg>)
}

export function Bars({ values, labels, label, height = 115 }: { values: number[]; labels: string[]; label: string; height?: number }) {
  if (!values.length) return <div className="muted small pad">Nothing to chart yet.</div>
  const mx = Math.max(1, ...values.map(Math.abs)), base = height / 2 - 10, bw = Math.min(30, 340 / values.length - 6)
  return (
    <svg viewBox={`0 0 380 ${height}`} width="100%" role="img" aria-label={label} style={{ display: 'block' }}>
      <line x1={0} x2={380} y1={base} y2={base} stroke="var(--border-strong)" />
      {values.map((v, i) => { const h = (Math.abs(v) / mx) * (base - 6), x = 10 + i * (bw + 6); return <g key={i}><rect x={x} y={v >= 0 ? base - h : base} width={bw} height={Math.max(h, 1)} fill={v >= 0 ? 'var(--profit)' : 'var(--loss)'} /><text x={x} y={height - 6} fontSize="8" fill="var(--text-muted)">{labels[i]}</text></g> })}
    </svg>)
}

export function Histogram({ lo, hi, counts }: { lo: number; hi: number; counts: number[] }) {
  const mx = Math.max(1, ...counts), bw = 380 / counts.length - 4
  return (
    <svg viewBox="0 0 380 120" width="100%" role="img" aria-label="Distribution of profit and loss per trade" style={{ display: 'block' }}>
      <line x1={0} x2={380} y1={100} y2={100} stroke="var(--border-strong)" />
      {counts.map((c, i) => { const mid = lo + ((i + 0.5) / counts.length) * (hi - lo); return <rect key={i} x={2 + i * (bw + 4)} y={100 - (c / mx) * 90} width={bw} height={(c / mx) * 90} fill={mid >= 0 ? 'var(--profit)' : 'var(--loss)'} opacity=".85" /> })}
      <text x={2} y={116} fontSize="8" fill="var(--text-muted)">{lo < 0 ? '−' : ''}£{Math.abs(lo).toFixed(0)}</text><text x={330} y={116} fontSize="8" fill="var(--text-muted)">{hi < 0 ? '−' : '+'}£{Math.abs(hi).toFixed(0)}</text>
    </svg>)
}
