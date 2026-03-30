# TTDS-CW3 - Search Engine

A full-stack search engine application with React + Vite frontend and Flask backend.

### Option 1: Run with Docker (Recommended)

Build the image:

`docker build -t cloud-run-app .`

Run the container:

`docker run -d --name cloud-run-app -e PORT=8080 -p 8080:8080 cloud-run-app`

Access the application:

Frontend: http://localhost:8080
API Health: http://localhost:8080/api/health

### Option 2: Run Manually

#### Prerequisites
- Node.js 20+ and npm
- Python 3.12+
- uv (Python package manager)

#### Backend Setup
```bash
cd backend

# Install dependencies
uv sync

# Run development server
uv run api.py
```
Backend runs on: http://localhost:5000

##### Running search engine with interactive cli (no api) for testing
```bash
cd backend
uv run main.py
```

#### Frontend Setup (in a new terminal)
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```
Frontend runs on: http://localhost:8080 (or http://localhost:5173 for default Vite port)

---

## API Endpoints

### Health Check
```bash
GET /api/health
```

### Search
```bash
GET /api/search?q=<search_term>
```