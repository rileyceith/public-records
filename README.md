# Public Records Workspace

A full-stack application for searching public records and managing the records, accounts, and supporting files behind them. The original phpMyAdmin capture files remain at the project root as read-only OneDrive items; [`legacy-snapshot/`](./legacy-snapshot/) documents them. The capture was an HTML error page, not the phpMyAdmin application or a source database.

## Project structure

```text
backend/
  app/
    api/             Authentication, records, attachments, and audit endpoints
    core/            Configuration, password/session helpers, audit service
    cli.py           First administrator setup
    database.py      SQLAlchemy engine and session lifecycle
    models.py        Users, records, files, audit events, login sessions
    schemas.py       Request validation and response contracts
  tests/             API and permission tests
frontend/
  src/
    app/             Workspace shell and navigation
    components/      Shared dialogs and controls
    features/        Authentication, records, users, and audit modules
    lib/             API client and shared types
    styles/          Responsive workspace design
legacy-snapshot/     Note documenting the preserved original capture
*.html, *.png, *.js.download
                   Original read-only capture files retained at the workspace root
```

## Features

- Search and filter the public archive by text, record type, and jurisdiction; browse paginated results and record details.
- Create, edit, publish, archive, and delete records. Draft and archived records are hidden from public visitors.
- Add staff accounts with `USER` or `ADMIN` roles. Administrators manage records, files, and accounts; users can browse public records.
- Upload and download PDF, PNG, JPG, TXT, and CSV attachments. Uploads are limited to 10 MB and stored outside the frontend's served files.
- Review an append-only audit trail for authentication and administrator changes.
- Browse the generated OpenAPI reference at `/api/docs`.

The initial record fields are deliberately generic because the captured files do not contain an actual public-records database: title, type, reference number, jurisdiction, description, date, and publication status.

## Requirements

- Python 3.11 or later
- Node.js 20 or later with npm

## Run locally on Windows

Open a PowerShell terminal at this project root.

1. Install the backend dependencies and create the local administrator:

   ```powershell
   cd backend
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m app.cli create-admin
   ```

   The CLI prompts for the administrator's email, name, and password. Passwords must be at least 12 characters; no default account or password is created.

2. In that terminal, start the API:

   ```powershell
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. Open a second terminal at the project root and start the React interface:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open the address printed by Vite (normally `http://127.0.0.1:5173`) and sign in with the administrator created in step 1.

SQLite data defaults to `backend/data/records.db`. Attachment files default to `backend/data/attachments/`. Both locations can be overridden with `RECORDS_DATA_DIR` and `RECORDS_UPLOAD_DIR`. The frontend development server proxies `/api` to `127.0.0.1:8000`.

If port 8000 is occupied, start the API on another port and set `API_PROXY_TARGET` in the frontend PowerShell terminal before running Vite, for example:

```powershell
# Backend terminal:
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8186

# Frontend terminal:
$env:API_PROXY_TARGET = "http://127.0.0.1:8186"
npm run dev -- --port 5178
```

## API and access model

| Endpoint | Access |
| --- | --- |
| `GET /api/health` | Public health check |
| `GET /api/records`, `GET /api/records/{id}`, `GET /api/records/facets` | Public records; administrators also see drafts and archived records |
| `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` | Session management |
| `POST /api/records`, `PUT /api/records/{id}`, `DELETE /api/records/{id}` | Administrator |
| `POST /api/auth/users`, `GET /api/auth/users` | Administrator |
| `POST /api/records/{id}/attachments`, `DELETE /api/attachments/{id}` | Administrator |
| `GET /api/attachments/{id}/download` | Public attachment for public records; administrator for non-public records |
| `GET /api/audit` | Administrator |
| `GET /api/docs` | OpenAPI / Swagger UI |

The browser keeps its bearer session token in memory rather than local storage, so a page reload requires signing in again. This avoids persistent browser storage of staff credentials. Production deployments should serve the frontend and API over HTTPS, protect and back up both the database and attachment directory, and configure `ALLOWED_ORIGINS` for the deployed frontend.

## Tests

From the `backend` directory, after installing its requirements:

```powershell
python -m pytest
```

From the `frontend` directory:

```powershell
npm run typecheck
npm run build
```
