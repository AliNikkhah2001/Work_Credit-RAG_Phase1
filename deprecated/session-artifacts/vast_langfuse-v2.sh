#!/bin/bash
# Real Langfuse v2 UI from source (no Docker). Uses local Postgres 14.
# v2 (not v3) because v3 requires ClickHouse; v2 runs on Postgres alone.
# Result: UI on 0.0.0.0:3001, traces DB `langfuse`.
# Secrets are GENERATED at runtime into /tmp/opencode/langfuse.env (never committed).
set -u
SRC="${LANGFUSE_SRC:-/tmp/langfuse-src}"
PORT="${LANGFUSE_PORT:-3001}"
export PATH="/opt/nvm/versions/node/v22.14.0/bin:$PATH"

if [ ! -d "$SRC" ]; then
  git clone https://github.com/langfuse/langfuse.git "$SRC"
fi
cd "$SRC"
TAG="$(git tag | grep -E '^v2' | sort -V | tail -1)"
git checkout -q "$TAG" && echo "langfuse tag: $TAG"

corepack enable 2>/dev/null
corepack prepare pnpm@9.5.0 --activate 2>&1 | tail -1
pnpm install 2>&1 | tail -1

mkdir -p /tmp/opencode
ENVF=/tmp/opencode/langfuse.env
if [ ! -f "$ENVF" ]; then
  PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='langfuse'" | grep -q 1 \
    || PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE langfuse" \
    || PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE langfuse_shadow"
  PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='langfuse_shadow'" | grep -q 1 \
    || PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE langfuse_shadow"
  ADMIN_PASS="$(openssl rand -base64 24)"
  API_PUB="pk-lf-$(openssl rand -hex 4)"
  API_SEC="sk-lf-$(openssl rand -hex 8)"
  cat > "$ENVF" <<EOF
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/langfuse
DIRECT_URL=postgresql://postgres:postgres@127.0.0.1:5432/langfuse
SHADOW_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/langfuse_shadow
NEXTAUTH_URL=http://127.0.0.1:$PORT
NEXTAUTH_SECRET=$(openssl rand -base64 32)
SALT=salt-$(openssl rand -hex 8)
ENCRYPTION_KEY=$(openssl rand -hex 32)
LANGFUSE_INIT_USER_EMAIL=admin@local.test
LANGFUSE_INIT_USER_PASSWORD=$ADMIN_PASS
LANGFUSE_INIT_USER_NAME=admin
LANGFUSE_INIT_ORG_ID=org-seeded-001
LANGFUSE_INIT_ORG_NAME=Seeded Org
LANGFUSE_INIT_PROJECT_ID=proj-seeded-001
LANGFUSE_INIT_PROJECT_NAME=Seeded Project
LANGFUSE_INIT_PROJECT_PUBLIC_KEY=$API_PUB
LANGFUSE_INIT_PROJECT_SECRET_KEY=$API_SEC
EOF
  chmod 600 "$ENVF"
  echo "seeded admin: admin@local.test / (password in $ENVF)"
fi
set -a; . "$ENVF"; set +a
cp "$ENVF" "$SRC/.env"

pnpm --filter @langfuse/shared run db:deploy 2>&1 | tail -1
pnpm --filter @langfuse/shared run db:generate 2>&1 | tail -1
pnpm --filter @langfuse/shared run build 2>&1 | tail -1
pnpm --filter web build 2>&1 | tail -2

setsid nohup pnpm --filter web start -- -p "$PORT" -H 0.0.0.0 > /tmp/langfuse-real.log 2>&1 < /dev/null &
sleep 12
curl -s --max-time 10 "http://127.0.0.1:$PORT/api/public/health"; echo
echo "UI: http://127.0.0.1:$PORT/ (keys in $ENVF)"
echo "Point orchestrator at it: LANGFUSE_HOST=http://127.0.0.1:$PORT + keys from $ENVF"
