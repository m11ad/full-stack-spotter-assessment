import React, {useRef, useEffect} from 'react'

export default function ELDCanvas({logs}){
  const ref = useRef(null)
  useEffect(()=>{
    const c = ref.current
    if(!c) return
    const ctx = c.getContext('2d')
    ctx.clearRect(0,0,c.width,c.height)
    ctx.fillStyle = '#fff'
    ctx.fillRect(0,0,c.width,c.height)
    ctx.fillStyle = '#000'
    ctx.font = '14px Arial'
    ctx.fillText('ELD Log Sheets', 10, 20)
    logs.forEach((l,i)=>{
      const y = 40 + i*60
      ctx.strokeRect(10, y, 500, 50)
      ctx.fillText(`Day ${l.day} - Drive: ${l.drive_hours}h Rest: ${l.rest_hours}h`, 20, y+30)
    })
  },[logs])

  return <canvas ref={ref} width={540} height={180} style={{border:'1px solid #ddd', marginTop:12}} />
}
