---
description: Start the Aikrut development environment with hot-reload
---

# Start Aikrut Dev Environment

This workflow starts all services needed for local development with hot-reload.

## Prerequisites
- Docker must be running
- Node.js and yarn must be available

## Steps

// turbo-all

1. Start MongoDB in Docker:
```bash
cd /Users/irshadiwardhana/Antigravity/AikrutProtoV0-staging3-pdffeature && docker compose -f docker-compose.dev.yml up -d
```

2. Start the backend with hot-reload (runs in background):
```bash
cd /Users/irshadiwardhana/Antigravity/AikrutProtoV0-staging3-pdffeature/backend && source venv/bin/activate && MONGO_URL=mongodb://localhost:27017 DB_NAME=aikrut JWT_SECRET=aikrut-secret-key-2024 ADMIN_JWT_SECRET=aikrut-admin-secret-key-2024 CORS_ORIGINS='*' uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

3. Start the frontend with hot-reload (runs in background):
```bash
cd /Users/irshadiwardhana/Antigravity/AikrutProtoV0-staging3-pdffeature/frontend && REACT_APP_BACKEND_URL=http://localhost:8000 yarn start
```

## Access Points
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MongoDB**: mongodb://localhost:27017

## Stop Everything
```bash
# Stop frontend & backend: Ctrl+C in their terminals
# Stop MongoDB:
cd /Users/irshadiwardhana/Antigravity/AikrutProtoV0-staging3-pdffeature && docker compose -f docker-compose.dev.yml down
```
