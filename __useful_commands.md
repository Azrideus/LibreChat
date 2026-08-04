docker compose down --remove-orphans
docker network prune -f
docker compose up -d --build