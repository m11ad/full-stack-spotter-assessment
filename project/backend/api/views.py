import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .hos_engine import simulate_hos, FUEL_EVERY_MILES



def build_instruction(step):
    man = step.get('maneuver', {}) or {}
    mtype = man.get('type', '')
    mod = man.get('modifier', '')
    name = step.get('name') or ''
    ref = step.get('ref') or ''
    parts = []
    if mtype:
        parts.append(mtype.replace('_', ' ').capitalize())
    if mod:
        parts.append(mod.capitalize())
    if name:
        parts.append(f"onto {name}")
    elif ref:
        parts.append(f"towards {ref}")
    if not parts:
        return 'Continue'
    return ' '.join(parts)


@csrf_exempt
def eld_route(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    cur = data.get('current')
    pickup = data.get('pickup')
    dropoff = data.get('dropoff')
    cycle_used = float(data.get('currentCycleUsed', 0))
    include_geometry = data.get('includeGeometry', False)

    coords = [cur, pickup, dropoff]
    try:
        coord_str = ';'.join(f"{c['lng']},{c['lat']}" for c in coords)
    except Exception:
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)

    osrm_url = (
        f"http://router.project-osrm.org/route/v1/driving/{coord_str}"
        f"?overview=full&geometries=geojson&steps=true"
    )
    try:
        r = requests.get(osrm_url, timeout=10)
    except requests.RequestException:
        return JsonResponse({'error': 'routing service unreachable'}, status=502)

    if r.status_code != 200:
        return JsonResponse({'error': 'routing failed'}, status=500)

    route = r.json()
    routes = route.get('routes', [])
    if not routes:
        return JsonResponse({'error': 'no route found between the given points'}, status=422)

    summary = routes[0]
    drive_hours = summary.get('duration', 0) / 3600.0
    distance_miles = summary.get('distance', 0) / 1609.34

    instructions = []
    for leg in summary.get('legs', []):
        for step in leg.get('steps', []):
            instructions.append({
                'distance_miles': round(step.get('distance', 0) / 1609.34, 2),
                'duration_minutes': round(step.get('duration', 0) / 60, 2),
                'instruction': build_instruction(step),
            })

    # --- this is the part that's new: continuous-time HOS state machine,
    # replacing the old "reset to 8:00 every loop iteration" day builder ---
    days, warnings = simulate_hos(
        drive_total_hours=drive_hours,
        cycle_used_hours=cycle_used,
        distance_miles=distance_miles,
    )

    fuel_stops = max(0, int(distance_miles // FUEL_EVERY_MILES))

    response = {
        'distance_miles': round(distance_miles, 2),
        'duration_hours': round(drive_hours, 2),
        'fuel_stops': fuel_stops,
        'instructions': instructions,
        'trip_schedule': {
            'days': days,
            'warnings': warnings,
        },
    }
    if include_geometry:
        response['route_geometry'] = summary.get('geometry', {}).get('coordinates', [])

    return JsonResponse(response)