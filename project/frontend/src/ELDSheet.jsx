import React from 'react'

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

export default function ELDSheet({days}){
  return (
    <div className="eld-sheet">
      <h3>ELD Timeline</h3>
      <div className="eld-day-list">
        {days.map((day)=>(
          <div className="eld-day" key={day.day}>
            <div className="eld-day-header">
              <h4>Day {day.day}</h4>
              <div className="eld-day-detail">Total cycle: {day.cycle_hours} h</div>
            </div>
            <div className="eld-grid">
              <div className="eld-hour-labels">
                {Array.from({length:13}, (_, idx)=>(
                  <div key={idx} className="eld-hour-label">{idx * 2}</div>
                ))}
              </div>
              {rows.map((row)=>(
                <div key={row.key} className="eld-row">
                  <div className="eld-row-title">{row.label}</div>
                  <div className="eld-track">
                    {day.events.filter((event)=>statusRow[event.status] === row.key).map((event,index)=>{
                      const left = parseMinutes(event.start) / 1440 * 100
                      const width = event.minutes / 1440 * 100
                      return (
                        <div key={index} className="eld-segment" title={`${event.note} ${event.start}-${event.end}`} style={{left:`${left}%`, width:`${width}%`, background: statusColors[event.status]}} />
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
            <div className="eld-events">
              {day.events.map((event,index)=>(
                <div key={index} className="eld-event-row">
                  <span>{event.start}-{event.end}</span>
                  <span>{event.note}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
