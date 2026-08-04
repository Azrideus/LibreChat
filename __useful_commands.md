docker compose down --remove-orphans
docker network prune -f
docker compose up -d --build

docker compose --profile tools run --rm gebra-knowledge-ingest


<!-- ----------------------------- Add Balance ----------------------------- -->
docker compose --profile tools run --rm --name gebra-knowledge-ingest gebra-knowledge-ingest



<!-- ------------------ Rebuild each time you change code ------------------ -->
docker compose --profile tools build gebra-knowledge-ingest
docker compose --profile tools run --rm --name gebra-knowledge-ingest gebra-knowledge-ingest