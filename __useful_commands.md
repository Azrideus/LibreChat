docker compose down --remove-orphans
docker network prune -f
docker compose up -d --build

docker compose --profile tools run --rm gebra-knowledge-ingest


<!-- ----------------------------- Add Balance ----------------------------- -->
docker compose exec api npm run add-balance mehrdadtavangar@gmail.com 50000