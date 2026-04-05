.PHONY: help install dev docker-up docker-down mongo-shell

help:
	@echo ""
	@echo "  IARS — Full-Stack Recruitment System"
	@echo "  ────────────────────────────────────"
	@echo "  make install      Install Python deps"
	@echo "  make dev          Start FastAPI dev server"
	@echo "  make docker-up    Start full stack (API + MongoDB)"
	@echo "  make docker-down  Stop all containers"
	@echo "  make mongo-shell  Open MongoDB shell"
	@echo ""

install:
	cd backend && pip install -r requirements.txt

dev:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-up:
	docker compose up --build -d
	@echo "✅ API → http://localhost:8000/docs"
	@echo "✅ MongoDB GUI → http://localhost:8081"
	@echo "✅ Frontend → open frontend/dashboard.html in browser"

docker-down:
	docker compose down

mongo-shell:
	docker exec -it iars_mongo mongosh iars_recruitment
