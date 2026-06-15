# Spotter ELD Assessment

This is a minimal scaffold for the Full Stack Developer assessment: a Django REST backend with a React frontend (Vite) demonstrating routing and ELD log rendering.

Run backend:
```bash
python3 -m pip install -r project/backend/requirements.txt
python3 project/backend/manage.py runserver 8000
```

Run frontend:
```bash
cd project/frontend
npm install
npm run dev
```

The frontend uses Vite with a proxy to `http://localhost:8000/api` and Nominatim geocoding for address input.

The frontend posts to `POST /api/eld/` with `{current,pickup,dropoff}` coordinates and renders the route and simple ELD canvas.
