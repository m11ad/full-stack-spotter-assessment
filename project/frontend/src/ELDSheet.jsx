import React from 'react'

const statusColors = {
  offDuty: '#f8f9fa',
  onDuty: '#f4a261',
  driving: '#2a9d8f',
}

export default function ELDSheet({days}){
  const totalWidth = 720
  const dayWidth = 240
  return (
    <div style={{marginTop:20}}>
      <h3>ELD Timeline</h3>
      <div style={{display:'flex', gap:16}}>
        {days.map((day)=>(
          <div key={day.day} style={{width:dayWidth, border:'1px solid #ddd', padding:12, borderRadius:10, background:'#fff'}}>
            <h4>Day {day.day}</h4>
            <div style={{position:'relative', height:80, background:'#f1f5f9', borderRadius:8}}>
              {day.events.map((event,index)=>{
                const left = (event.start.split(':')[0]*60 + parseInt(event.start.split(':')[1])) / 1440 * 100
                const width = event.minutes / 1440 * 100
                return (
                  <div key={index} title={`${event.note} ${event.start}-${event.end}`} style={{position:'absolute', left:`${left}%`, width:`${width}%`, height:'100%', background:statusColors[event.status] || '#ccc', opacity:0.9, borderRight:'1px solid #fff'}} />
                )
              })}
            </div>
            <div style={{marginTop:8}}>
              {day.events.map((event,index)=>(
                <div key={index} style={{fontSize:12, marginBottom:4}}>
                  <strong>{event.start}-{event.end}</strong> {event.note}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
