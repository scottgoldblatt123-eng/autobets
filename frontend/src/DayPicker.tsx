/** Pick which day's markets to list: "Next up" (soonest to start) or a UK calendar day, today onward, by chip or calendar. */
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

export default function DayPicker({ value, onChange }: { value: string; onChange: (day: string) => void }) {
  const today = new Date(), days = Array.from({ length: 6 }, (_, i) => { const d = new Date(today); d.setDate(d.getDate() + i); return d })
  const label = (d: Date, i: number) => (i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : d.toLocaleDateString([], { weekday: 'short', day: 'numeric' }))
  const inStrip = days.some(d => iso(d) === value)
  return <div className="daypick">
    <div className="chips">
      <button className={'chip' + (value === '' ? ' on' : '')} onClick={() => onChange('')} title="The next markets to start">Next up</button>
      {days.map((d, i) => <button key={iso(d)} className={'chip' + (value === iso(d) ? ' on' : '')} onClick={() => onChange(iso(d))}>{label(d, i)}</button>)}
      <input type="date" className={'chip dateinp' + (value && !inStrip ? ' on' : '')} min={iso(today)} value={value} aria-label="Pick a date"
        onChange={e => onChange(e.target.value && e.target.value >= iso(today) ? e.target.value : '')} />
    </div>
  </div>
}
