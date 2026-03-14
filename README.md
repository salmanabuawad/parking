# Final Masterpiece Package

## Running locally (no Docker)

Use **local Postgres**, **local backend/frontend**, and **nginx** as reverse proxy.

1. **PostgreSQL** – Run Postgres locally (e.g. default `postgres:5432`). Backend uses `backend/.env`; default:
   ```bash
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
   ```

2. **Backend** (port 8000):
   ```bash
   cd backend
   pip install -r requirements.txt
   python run_backend.py
   ```

3. **Frontend** (port 5173):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Nginx** – Point nginx at this config and run it (e.g. port 80). It proxies:
   - `/api/` → `http://127.0.0.1:8000/api/`
   - `/` → `http://127.0.0.1:5173/` (Vite dev server)

   Example (Windows, nginx in `C:\nginx`):
   ```bash
   nginx -c c:\parking_app\parking\nginx\nginx.conf
   ```
   Or copy `nginx/nginx.conf` into your nginx `conf.d` and ensure the path to it is correct (paths like `/var/log/nginx` are Linux; on Windows use a valid path or adjust the config).

5. **Optional – upload worker** (same process as backend, different entrypoint):
   ```bash
   cd backend
   python run_upload_worker.py
   ```

Open **http://localhost** (or the port nginx listens on). The frontend uses relative `/api`, so no `VITE_API_URL` is needed when using nginx.

---

This bundle combines:
- the current backend patch set
- the final architecture
- curb / parking logic
- screenshot evidence spec
- Hebrew UI/UX guidance
- initial Hebrew translation file

## Included patch
Patched backend files are under:
`patch/backend/app/plate_pipeline/`

## Recommended next additions
New modules still to add:
- metadata_extractor.py
- vehicle_ranker.py
- vehicle_classifier.py
- plate_rectifier.py
- crop_quality.py
- digit_segmenter.py
- registry_client.py
- registry_matcher.py
- confidence_engine.py
- evidence_writer.py
