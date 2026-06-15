import React, {useState, useRef, useEffect} from 'react'

const statusColors = {
  offDuty: '#e2e8f0',
  onDuty: '#fde68a',
  driving: '#34d399',
  sleeper: '#c7d2fe',
}

const rows = [
  {key: 'offDuty', label: 'Off Duty'},
  {key: 'sleeper', label: 'Sleeper Berth'},
  {key: 'driving', label: 'Driving'},
  {key: 'onDuty', label: 'On Duty (not driving)'},
]

const statusRow = {
  offDuty: 'offDuty',
  onDuty: 'onDuty',
  driving: 'driving',
  sleeper: 'sleeper',
}

const parseMinutes = (time) => {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}

const statusLabels = {
  offDuty: 'Off Duty',
  sleeper: 'Sleeper Berth',
  driving: 'Driving',
  onDuty: 'On Duty',
}

const formatDuration = (minutes) => {
  const hours = minutes / 60
  return `${hours % 1 === 0 ? hours : hours.toFixed(1)} hour${hours === 1 ? '' : 's'}`
}

export default function ELDSheet({days}){
  const [selectedEvent, setSelectedEvent] = useState(null)
  const sheetRef = useRef(null)

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (!selectedEvent) return
      const target = event.target
      if (target.closest('.eld-event-tooltip') || target.closest('.eld-segment')) {
        return
      }
      setSelectedEvent(null)
    }

    document.addEventListener('click', handleOutsideClick)
    return () => document.removeEventListener('click', handleOutsideClick)
  }, [selectedEvent])

  const summaryTotals = rows.map((row) => {
    const minutes = days.reduce((sum, day) => {
      return sum + day.events.filter((e) => statusRow[e.status] === row.key).reduce((s, e) => s + e.minutes, 0)
    }, 0)
    return { key: row.key, label: row.label, value: (minutes / 60).toFixed(2), unit: 'h' }
  })

  return (
    <div className="eld-sheet" ref={sheetRef}>
      <div className="timeline-summary-grid">
        <div className="summary-stat-card">
          <div className="summary-stat-label">Days</div>
          <div className="summary-stat-value">{days.length}</div>
          <div className="summary-stat-unit">days</div>
        </div>
        {summaryTotals.map((line) => (
          <div className="summary-stat-card" key={line.key}>
            <div className="summary-stat-label">{line.label}</div>
            <div className="summary-stat-value">{line.value}</div>
            <div className="summary-stat-unit">{line.unit}</div>
          </div>
        ))}
      </div>
      <div className="eld-day-list">
        {days.map((day)=>(
          <div className="eld-day" key={day.day}>
            <div className="eld-day-header">
              <h4>Day {day.day}</h4>
              <div className="eld-day-detail">Total cycle</div>
            </div>
            <div className="eld-grid three-col">
              <div className="eld-hour-labels" style={{gridColumn: '2 / 3'}}>
                {Array.from({length:13}, (_, idx)=>(
                  <div key={idx} className="eld-hour-label">{idx * 2}</div>
                ))}
              </div>

              {rows.map((row)=>(
                <React.Fragment key={row.key}>
                  <div className="eld-row-title cell-title">{row.label}</div>
                  <div className="eld-track">
                    {day.events.filter((event)=>statusRow[event.status] === row.key).map((event,index)=>{
                      const left = parseMinutes(event.start) / 1440 * 100
                      const width = event.minutes / 1440 * 100
                      const eventKey = `${day.day}-${row.key}-${index}`
                      const isSelected = selectedEvent?.key === eventKey
                      return (
                        <React.Fragment key={eventKey}>
                          <div
                            className="eld-segment"
                            onClick={() => setSelectedEvent(isSelected ? null : {
                              key: eventKey,
                              day: day.day,
                              status: event.status,
                              note: event.note,
                              start: event.start,
                              end: event.end,
                              left,
                              width,
                            })}
                            style={{left:`${left}%`, width:`${width}%`, background: statusColors[event.status]}}
                          />
                          {isSelected && (
                            <div className="eld-event-tooltip" style={{left: `${left + width / 2}%`}}>
                              <div className="eld-event-tooltip-title">
                                {statusLabels[event.status]} ({formatDuration(event.minutes)})
                              </div>
                              <div className="eld-event-tooltip-time">{event.start} - {event.end}</div>
                            </div>
                          )}
                        </React.Fragment>
                      )
                    })}
                  </div>
                  <div className="eld-totals-cell" style={{display:'flex', alignItems:'center', justifyContent:'flex-end', padding:'6px 0', borderBottom:'1px solid #f1f5f9'}}>
                    <div style={{fontWeight:700}}>{(day.events.filter(e=>statusRow[e.status]===row.key).reduce((s,e)=>s+e.minutes,0)/60).toFixed(2)}</div>
                  </div>
                </React.Fragment>
              ))}

              <div className="eld-row-title cell-title">Total</div>
              <div />
              <div className="eld-totals-cell" style={{fontWeight:800}}>{(day.events.reduce((s,e)=>s+e.minutes,0)/60).toFixed(2)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
