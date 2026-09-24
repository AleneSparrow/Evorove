#!/usr/bin/env sh
# One command: fresh databases, all three services, cycle 1 run, board check.
#   cd system && ./run-e2e.sh
set -eu
cd "$(dirname "$0")"

docker compose down -v --remove-orphans >/dev/null 2>&1 || true
docker compose up -d --build --wait postgres engine crm lead

# Cycle 1: brief from the fixture, people from the owner-observation stub.
docker compose run --rm lead python -m evorove_lead.run \
  --business-id acme-home-services \
  --site-url https://acme-home-services.example/ \
  --materials /fixtures/materials \
  --observations /fixtures/observations

docker compose exec -T engine python /system/e2e.py
