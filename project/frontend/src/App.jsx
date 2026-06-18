import React, {useState, useRef} from 'react'
import axios from 'axios'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import ELDSheet from './ELDSheet'
import './App.css'

// Empty string -> relative '/api/...' calls, handled by the Vite dev proxy locally.
// Set via .env.production / .env.development, see those files for the actual values.
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const cityOptions = [
  'New York, NY',
  'Los Angeles, CA',
  'Chicago, IL',
  'Houston, TX',
  'Phoenix, AZ',
  'Philadelphia, PA',
  'San Antonio, TX',
  'San Diego, CA',
  'Dallas, TX',
  'San Jose, CA',
  'Austin, TX',
  'Jacksonville, FL',
  'San Francisco, CA',
  'Columbus, OH',
  'Fort Worth, TX',
  'Charlotte, NC',
  'Seattle, WA',
  'Denver, CO',
  'Washington, DC',
  'Boston, MA',
]

delete L.Icon.Default.prototype._getIconUrl

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})
// Custom emoji icons
const currentIcon = L.divIcon({
  html: '🚛',
  className: 'custom-emoji-icon',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const pickupIcon = L.divIcon({
  html: '📦',
  className: 'custom-emoji-icon',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const dropoffIcon = L.divIcon({
  html: '🏁',
  className: 'custom-emoji-icon',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const fuelStopIcon = L.divIcon({
  html: '⛽',
  className: 'custom-emoji-icon',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const sleeperIcon = L.divIcon({
  html: '🛏️',
  className: 'custom-emoji-icon',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});
const createEmojiIcon = (emoji) => L.divIcon({
  html: emoji,
  className: 'custom-emoji-icon',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});
export default function App() {
  const [suggestions, setSuggestions] = useState([])
  const [activeSuggestField, setActiveSuggestField] = useState(null)
  const [route, setRoute] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [currentCity, setCurrentCity] = useState('New York, NY')
  const [pickupCity, setPickupCity] = useState('Chicago, IL')
  const [dropoffCity, setDropoffCity] = useState('Los Angeles, CA')
  const [currentLat, setCurrentLat] = useState('40.7128')
  const [currentLng, setCurrentLng] = useState('-74.0060')
  const [pickupLat, setPickupLat] = useState('41.8781')
  const [pickupLng, setPickupLng] = useState('-87.6298')
  const [dropLat, setDropLat] = useState('34.0522')
  const [dropLng, setDropLng] = useState('-118.2437')
  const [currentCycleUsed, setCurrentCycleUsed] = useState('0')
  const mapRef = useRef(null)
  const polylineRef = useRef(null)
  const markerRefs = useRef([])

  const geocodeCity = async (query) => {
    if (!query) throw new Error('Please enter a city')
    const res = await axios.get('https://nominatim.openstreetmap.org/search', {
      params: { q: query, format: 'json', limit: 1, countrycodes: 'us' },
    })
    if (!res.data || res.data.length === 0) {
      throw new Error(`Unable to geocode: ${query}`)
    }
    const r = res.data[0]
    return { lat: parseFloat(r.lat), lng: parseFloat(r.lon) }
  }

  const initMap = (center) => {
    if (mapRef.current) return mapRef.current
    const map = L.map('map').setView(center, 6)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map)
    mapRef.current = map
    return map
  }

  const clearMapMarkers = () => {
    markerRefs.current.forEach((marker) => mapRef.current?.removeLayer(marker))
    markerRefs.current = []
  }

  const addMapMarker = (map, coords, label, description, icon = null) => {
    const marker = L.marker(coords, { icon: icon || L.Icon.Default }).addTo(map);
    marker.bindPopup(`<strong>${label}</strong><br/>${description}`);
    markerRefs.current.push(marker);
  };

  const handleCityChange = (value, setter) => {
    setter(value)
    // update suggestions as user types
    const list = cityOptions.filter((c) => c.toLowerCase().includes(value.toLowerCase())).slice(0, 8)
    setSuggestions(list)
  }

  const handleCityBlur = async (value, setLat, setLng) => {
    if (!value) return
    try {
      const coords = await geocodeCity(value)
      setLat(coords.lat.toFixed(6))
      setLng(coords.lng.toFixed(6))
    } catch (err) {
      // ignore until submit
    }
    // hide suggestions after blur
    setTimeout(() => setActiveSuggestField(null), 150)
  }

  const handleSuggestSelect = async (city, setter, setLat, setLng) => {
    setter(city)
    setActiveSuggestField(null)
    try {
      const coords = await geocodeCity(city)
      setLat(coords.lat.toFixed(6))
      setLng(coords.lng.toFixed(6))
    } catch (err) {
      // ignore
    }
  }

const handleSubmit = async (e) => {
  e.preventDefault();
  setError('');
  setLoading(true);
  try {
    const current = { lat: parseFloat(currentLat), lng: parseFloat(currentLng) };
    const pickup = { lat: parseFloat(pickupLat), lng: parseFloat(pickupLng) };
    const dropoff = { lat: parseFloat(dropLat), lng: parseFloat(dropLng) };

    const res = await axios.post(`${API_BASE}/api/eld/`, {
      current,
      pickup,
      dropoff,
      currentCycleUsed: parseFloat(currentCycleUsed || '0'),
      includeGeometry: true,
    });
    const routeData = res.data;
    setRoute(routeData);

    // Initialize map
    const map = initMap([current.lat, current.lng]);
    clearMapMarkers();

    if (polylineRef.current) {
      map.removeLayer(polylineRef.current);
    }

    // Draw route polyline
    const coords = routeData.route_geometry.map((c) => [c[1], c[0]]);
    polylineRef.current = L.polyline(coords, { color: '#2a9d8f', weight: 5 }).addTo(map);

    // Add current, pickup, dropoff markers with emoji icons
    addMapMarker(map, [current.lat, current.lng], 'Current', currentCity, createEmojiIcon('🚛'));
    addMapMarker(map, [pickup.lat, pickup.lng], 'Pickup', pickupCity, createEmojiIcon('📦'));
    addMapMarker(map, [dropoff.lat, dropoff.lng], 'Dropoff', dropoffCity, createEmojiIcon('🏁'));

    // Add fuel stops
    if (routeData.fuel_stops > 0) {
      for (let i = 1; i <= routeData.fuel_stops; i++) {
        const segmentIndex = Math.floor((i / (routeData.fuel_stops + 1)) * coords.length);
        const fuelStopCoord = coords[segmentIndex];
        addMapMarker(
          map,
          fuelStopCoord,
          `Fuel Stop ${i}`,
          `Fuel stop ${i}/${routeData.fuel_stops}`,
          createEmojiIcon('⛽')
        );
      }
    }

    // Add sleeper berths
// ✅ NEW (CORRECT) - Uses cumulative DRIVING time only
let cumulativeDriveMinutes = 0;
routeData.trip_schedule.days.forEach((day) => {
  day.events.forEach((event) => {
    if (event.status === 'driving') {
      cumulativeDriveMinutes += event.minutes;
    }
    else if (event.status === 'sleeper') {
      // Place sleeper berth at the END of the previous driving segment
      const ratio = Math.min(cumulativeDriveMinutes / (routeData.duration_hours * 60), 0.99);
      const sleeperCoord = coords[Math.floor(ratio * coords.length)];
      addMapMarker(map, sleeperCoord, 'Sleeper Berth', `Day ${day.day}: ${event.note}`, createEmojiIcon('🛏️'));
    }
  });
});

    map.fitBounds(polylineRef.current.getBounds(), { padding: [40, 40] });
  } catch (err) {
    setError(err.response?.data?.error || err.message || 'Unable to compute route');
  } finally {
    setLoading(false);
  }
};





  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-inner">
          <div className="hero-badge">Spotter ELD</div>
          <h1>Spotter ELD Route Planner</h1>
          <p className="hero-sub">Enter current, pickup, and dropoff locations to generate route details and HOS logs.</p>
        </div>
      </header>
      <form className="trip-form" onSubmit={handleSubmit}>
        <div className="field-block">
          <label>Current location (USA city)</label>
          <div className="input-with-suggestions">
            <input
              list="city-list"
              value={currentCity}
              onChange={(e) => handleCityChange(e.target.value, setCurrentCity)}
              onFocus={() => { setActiveSuggestField('current'); setSuggestions(cityOptions.slice(0,8)) }}
              onBlur={() => handleCityBlur(currentCity, setCurrentLat, setCurrentLng)}
              placeholder="Choose a city"
            />
            {activeSuggestField === 'current' && suggestions.length > 0 && (
              <ul className="suggestions-list">
                {suggestions.map((c) => (
                  <li key={c} className="suggestion-item" onMouseDown={(e)=>e.preventDefault()} onClick={() => handleSuggestSelect(c, setCurrentCity, setCurrentLat, setCurrentLng)}>{c}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="coord-row">
            <input value={currentLat} onChange={(e) => setCurrentLat(e.target.value)} placeholder="Lat" />
            <input value={currentLng} onChange={(e) => setCurrentLng(e.target.value)} placeholder="Lng" />
          </div>
        </div>

        <div className="field-block">
          <label>Pickup location (USA city)</label>
          <div className="input-with-suggestions">
            <input
              list="city-list"
              value={pickupCity}
              onChange={(e) => handleCityChange(e.target.value, setPickupCity)}
              onFocus={() => { setActiveSuggestField('pickup'); setSuggestions(cityOptions.slice(0,8)) }}
              onBlur={() => handleCityBlur(pickupCity, setPickupLat, setPickupLng)}
              placeholder="Choose a city"
            />
            {activeSuggestField === 'pickup' && suggestions.length > 0 && (
              <ul className="suggestions-list">
                {suggestions.map((c) => (
                  <li key={c} className="suggestion-item" onMouseDown={(e)=>e.preventDefault()} onClick={() => handleSuggestSelect(c, setPickupCity, setPickupLat, setPickupLng)}>{c}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="coord-row">
            <input value={pickupLat} onChange={(e) => setPickupLat(e.target.value)} placeholder="Lat" />
            <input value={pickupLng} onChange={(e) => setPickupLng(e.target.value)} placeholder="Lng" />
          </div>
        </div>

        <div className="field-block">
          <label>Dropoff location (USA city)</label>
          <div className="input-with-suggestions">
            <input
              list="city-list"
              value={dropoffCity}
              onChange={(e) => handleCityChange(e.target.value, setDropoffCity)}
              onFocus={() => { setActiveSuggestField('dropoff'); setSuggestions(cityOptions.slice(0,8)) }}
              onBlur={() => handleCityBlur(dropoffCity, setDropLat, setDropLng)}
              placeholder="Choose a city"
            />
            {activeSuggestField === 'dropoff' && suggestions.length > 0 && (
              <ul className="suggestions-list">
                {suggestions.map((c) => (
                  <li key={c} className="suggestion-item" onMouseDown={(e)=>e.preventDefault()} onClick={() => handleSuggestSelect(c, setDropoffCity, setDropLat, setDropLng)}>{c}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="coord-row">
            <input value={dropLat} onChange={(e) => setDropLat(e.target.value)} placeholder="Lat" />
            <input value={dropLng} onChange={(e) => setDropLng(e.target.value)} placeholder="Lng" />
          </div>
        </div>

        <div className="field-block small">
          <label>Current cycle used (hrs)</label>
          <input value={currentCycleUsed} onChange={(e) => setCurrentCycleUsed(e.target.value)} />
        </div>
        <button type="submit" disabled={loading}>{loading ? 'Calculating...' : 'Generate Route'}</button>
        {error && <div className="error-box">{error}</div>}
        <datalist id="city-list">
          {cityOptions.map((city) => <option key={city} value={city} />)}
        </datalist>
      </form>

      <div className="content-grid">
        <section className="map-panel">
          <div id="map" className="map-container"></div>
          {route && (
            <div className="map-legend">
              <div><strong>Map markers</strong></div>
              <div>Current location, pickup, and dropoff are shown with markers.</div>
            </div>
          )}
        </section>
        <section className="summary-panel">
          {route ? (
            <div className="summary-card">
              <div className="summary-header">
                <h2>Route Summary</h2>
                {route.trip_schedule?.warnings?.length > 0 && (
                  <div className="summary-warnings">
                    {route.trip_schedule.warnings.map((w, i) => (
                      <span key={i} className="restart-badge">{w}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="route-summary-grid">
                <div className="route-metric">
                  <div className="route-metric-label">Distance</div>
                  <div className="route-metric-value">{route.distance_miles}</div>
                  <div className="route-metric-unit">mi</div>
                </div>
                <div className="route-metric">
                  <div className="route-metric-label">Driving Time</div>
                  <div className="route-metric-value">{route.duration_hours}</div>
                  <div className="route-metric-unit">h</div>
                </div>
                <div className="route-metric">
                  <div className="route-metric-label">Fuel Stops</div>
                  <div className="route-metric-value">{route.fuel_stops}</div>
                  <div className="route-metric-unit"></div>
                </div>
              </div>
             
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
      <footer className="app-footer">
        Developed by <a href="https://takinsoft.ir" target="_blank" rel="noreferrer">Milad</a> as an assessment for <a href="https://spotter.ai" target="_blank" rel="noreferrer">Spotter AI</a>
      </footer>
    </div>
  )
}

