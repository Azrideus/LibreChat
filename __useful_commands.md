docker compose down --remove-orphans 
docker compose up -d

docker compose up -d --build
<!-- --------------------------- Build Frontend ---------------------------- -->

npm run frontend
docker compose down --remove-orphans
docker compose up -d


<!-- ----------------------------- Add Balance ----------------------------- -->
docker compose --profile tools run --rm --name gebra-knowledge-ingest gebra-knowledge-ingest



<!-- ------------------ Rebuild each time you change code ------------------ -->
docker compose --profile tools build gebra-knowledge-ingest
docker compose --profile tools run --rm --name gebra-knowledge-ingest gebra-knowledge-ingest