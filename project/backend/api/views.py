import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


def minutes_to_time(minutes):
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{int(hours):02d}:{int(mins):02d}"


def add_segment(events, status, start, end, note=None):
    if end <= start:
        return
    events.append({
        'status': status,
        'start': minutes_to_time(start),
        'end': minutes_to_time(end),
        'minutes': end - start,
        'note': note or status,
    })


@csrf_exempt
def eld_route(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    data = json.loads(request.body.decode('utf-8'))
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

    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=geojson&steps=true"
    r = requests.get(osrm_url, timeout=10)
    if r.status_code != 200:
        return JsonResponse({'error': 'routing failed'}, status=500)
    route = r.json()
    summary = route.get('routes', [])[0]
    drive_hours = summary.get('duration', 0) / 3600.0
    distance = summary.get('distance', 0) / 1609.34
    instructions = []
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

    for leg_index, leg in enumerate(summary.get('legs', []), start=1):
        for step in leg.get('steps', []):
            instructions.append({
                'distance_miles': round(step.get('distance', 0) / 1609.34, 2),
                'duration_minutes': round(step.get('duration', 0) / 60, 2),
                'instruction': build_instruction(step),
            })

    remaining_drive = round(drive_hours, 2)
    remaining_pickup = 1.0
    remaining_dropoff = 1.0
    days = []
    day = 1
    cycle_hours = cycle_used
    warnings = []

    while remaining_drive > 0 or remaining_pickup > 0 or remaining_dropoff > 0:
        if day > 8:
            warnings.append('Exceeded 8-day HOS cycle')
            break

        if cycle_hours >= 70:
            # Apply 34-hour restart day if the 70/8-day limit is reached.
            days.append({
                'day': day,
                'events': [
                    {
                        'status': 'sleeper',
                        'start': '00:00',
                        'end': '24:00',
                        'minutes': 1440,
                        'note': '34-hour restart',
                    }
                ],
                'cycle_hours': round(cycle_hours, 2),
            })
            day += 1
            cycle_hours = 0.0
            warnings.append('34-hour restart applied')
            continue

        events = []
        current_minute = 0
        add_segment(events, 'offDuty', 0, 8 * 60, 'Off Duty')
        current_minute = 8 * 60

        if remaining_pickup > 0:
            add_segment(events, 'onDuty', current_minute, current_minute + 60, 'Pickup')
            current_minute += 60
            cycle_hours += 1
            remaining_pickup = 0.0

        if remaining_drive > 0:
            drive_today = min(remaining_drive, 11.0)
            first_leg = min(drive_today, 8.0)
            add_segment(events, 'driving', current_minute, current_minute + int(first_leg * 60), 'Driving')
            current_minute += int(first_leg * 60)
            cycle_hours += first_leg
            remaining_drive -= first_leg

            if drive_today > 8.0 and remaining_drive > 0:
                add_segment(events, 'offDuty', current_minute, current_minute + 30, '30-minute break')
                current_minute += 30
                second_leg = min(drive_today - 8.0, remaining_drive)
                add_segment(events, 'driving', current_minute, current_minute + int(second_leg * 60), 'Driving')
                current_minute += int(second_leg * 60)
                cycle_hours += second_leg
                remaining_drive -= second_leg

        if remaining_drive <= 0 and remaining_dropoff > 0:
            add_segment(events, 'onDuty', current_minute, current_minute + 60, 'Dropoff')
            current_minute += 60
            cycle_hours += 1
            remaining_dropoff = 0.0

        if current_minute < 24 * 60:
            if remaining_drive > 0:
                add_segment(events, 'sleeper', current_minute, 24 * 60, 'Sleeper Berth')
            else:
                add_segment(events, 'offDuty', current_minute, 24 * 60, 'Off Duty')

        days.append({
            'day': day,
            'events': events,
            'cycle_hours': round(cycle_hours, 2),
        })
        day += 1

        if cycle_hours >= 70 and (remaining_drive > 0 or remaining_pickup > 0 or remaining_dropoff > 0):
            warnings.append('70-hour cycle reached before trip completion')
            continue

    fuel_stops = max(0, int(distance // 1000))
    response = {
        'distance_miles': round(distance, 2),
        'duration_hours': round(drive_hours, 2),
        'fuel_stops': fuel_stops,
        'trip_schedule': {
            'days': days,
            'warnings': warnings,
        },
    }
    if include_geometry:
        response['route_geometry'] = summary.get('geometry', {}).get('coordinates', [])
    return JsonResponse(response)
