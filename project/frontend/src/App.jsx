import React, {useState, useRef} from 'react'
import axios from 'axios'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import ELDSheet from './ELDSheet'
import './App.css'

export default function App(){
  const [route, setRoute] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const mapRef = useRef(null)
  const polylineRef = useRef(null)

  const geocode = async (addr, lat, lng)=>{
    if(!addr) return {lat: parseFloat(lat), lng: parseFloat(lng)}
    const res = await axios.get('https://nominatim.openstreetmap.org/search', {params:{q:addr, format:'json', limit:1}})
    if (!res.data || res.data.length === 0) {
      throw new Error(`Unable to geocode: ${addr}`)
    }
    const r = res.data[0]
    return {lat: parseFloat(r.lat), lng: parseFloat(r.lon)}
  }

  const initMap = (center) => {
    if (mapRef.current) return mapRef.current
    const map = L.map('map').setView(center, 6)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map)
    mapRef.current = map
    return map
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const form = new FormData(e.target)
    try {
      const current = await geocode(form.get('curAddr'), form.get('curLat'), form.get('curLng'))
      const pickup = await geocode(form.get('pickupAddr'), form.get('pickupLat'), form.get('pickupLng'))
      const dropoff = await geocode(form.get('dropAddr'), form.get('dropLat'), form.get('dropLng'))
      const currentCycleUsed = parseFloat(form.get('currentCycleUsed') || '0')
      const res = await axios.post('/api/eld/', {current, pickup, dropoff, currentCycleUsed})
      setRoute(res.data)
      const map = initMap([current.lat, current.lng])
      const coords = res.data.route.geometry.coordinates.map(c=>[c[1], c[0]])
      if (polylineRef.current) {
        map.removeLayer(polylineRef.current)
      }
      polylineRef.current = L.polyline(coords, {color: '#2a9d8f', weight: 5}).addTo(map)
      map.fitBounds(polylineRef.current.getBounds(), {padding:[40,40]})
    } catch (err) {
      setError(err.message || 'Unable to compute route')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header>
        <h1>Spotter ELD Route Planner</h1>
        <p>Enter current, pickup, and dropoff locations to generate route details and HOS logs.</p>
      </header>
      <form className="trip-form" onSubmit={handleSubmit}>
        <div className="field-block">
          <label>Current location (address preferred)</label>
          <input name="curAddr" placeholder="e.g. New York, NY" />
          <div className="coord-row">
            <input name="curLat" defaultValue="40.7128" placeholder="Lat" />
            <input name="curLng" defaultValue="-74.0060" placeholder="Lng" />
          </div>
        </div>

        <div className="field-block">
          <label>Pickup location (address preferred)</label>
          <input name="pickupAddr" placeholder="e.g. Chicago, IL" />
          <div className="coord-row">
            <input name="pickupLat" defaultValue="41.8781" placeholder="Lat" />
            <input name="pickupLng" defaultValue="-87.6298" placeholder="Lng" />
          </div>
        </div>

        <div className="field-block">
          <label>Dropoff location (address preferred)</label>
          <input name="dropAddr" placeholder="e.g. Los Angeles, CA" />
          <div className="coord-row">
            <input name="dropLat" defaultValue="34.0522" placeholder="Lat" />
            <input name="dropLng" defaultValue="-118.2437" placeholder="Lng" />
          </div>
        </div>

        <div className="field-block small">
          <label>Current cycle used (hrs)</label>
          <input name="currentCycleUsed" defaultValue="0" />
        </div>
        <button type="submit" disabled={loading}>{loading ? 'Calculating...' : 'Generate Route'}</button>
        {error && <div className="error-box">{error}</div>}
      </form>
      <div className="content-grid">
        <section className="map-panel">
          <div id="map" className="map-container"></div>
        </section>
        <section className="summary-panel">
          {route ? (
            <div className="summary-card">
              <h2>Route Summary</h2>
              <div>Distance: <strong>{route.distance_miles} mi</strong></div>
              <div>Driving Time: <strong>{route.duration_hours} h</strong></div>
              <div>Fuel Stops: <strong>{route.fuel_stops}</strong></div>
              {route.instructions && route.instructions.length > 0 && (
                <div>
                  <h3>Route Instructions</h3>
                  <ul>
                    {route.instructions.slice(0, 6).map((step, idx) => (
                      <li key={idx}>{step.instruction} ({step.distance_miles} mi, {step.duration_minutes} min)</li>
                    ))}
                  </ul>
                </div>
              )}
              {route.trip_schedule.warnings.length > 0 && (
                <div className="warning-box">{route.trip_schedule.warnings.join('. ')}</div>
              )}
              <ELDSheet days={route.trip_schedule.days} />
            </div>
          ) : (
            <div className="summary-card">
              <h2>Trip Output</h2>
              <p>Submit the form to generate driving schedule and ELD timelines.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
