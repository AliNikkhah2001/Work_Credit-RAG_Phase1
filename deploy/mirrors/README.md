# Package mirrors (Iran / regional) — fallback only

Official registries are always primary. Iranian mirrors are extras / retry
targets when upstream stalls (Squid timeouts, sanctions path, etc.).

| Ecosystem | Primary (always) | Fallback |
|-----------|------------------|----------|
| **pip / uv** | `pypi.org/simple` | shecan, runflare, liara (`PIP_EXTRA_INDEX_URL`) |
| **npm** | `registry.npmjs.org` | shecan → runflare → liara (retry after failure) |
| **Docker Hub** | `docker.io` | opt-in `daemon.json` mirrors (Docker tries mirrors *before* Hub — do not install for Hub-first) |
| **apt (Ubuntu)** | Ubuntu archives | optional host rewrite (Arvan / `ir.archive`) |

## CI + local (automatic)

`scripts/ci_apply_iran_mirrors.sh` is sourced from the Jenkins **Build images**
stage on **laptop and GPU/prod** (default `CI_USE_IRAN_MIRRORS=1`).

It exports:

- `PIP_INDEX_URL=https://pypi.org/simple` (unless already set)
- `PIP_EXTRA_INDEX_URL=` Iranian mirrors only
- `NPM_CONFIG_REGISTRY=https://registry.npmjs.org/`
- `IRAN_NPM_REGISTRIES=` for `npm_with_iran_fallback`
- `promote_iran_pip_primary` — used only after compose build retries exhaust

Override / disable:

```bash
CI_USE_IRAN_MIRRORS=0                 # no Iran extras
CI_IRAN_MIRRORS_AS_PRIMARY=1          # last resort: Iran as index-url
PIP_INDEX_URL=https://pypi.org/simple
NPM_CONFIG_REGISTRY=https://registry.npmjs.org
```

Local compose (without Jenkins):

```bash
source scripts/ci_apply_iran_mirrors.sh
docker compose -f deploy/compose/compose.base.yml \
  -f deploy/compose/compose.local.yml --env-file deploy/compose/.env build
```

## Docker Hub mirrors (opt-in, Hub-blocked hosts only)

Docker Engine contacts `registry-mirrors` **before** docker.io. Installing
`deploy/mirrors/docker-daemon-registry-mirrors.json` therefore prefers Iranian
mirrors — use only when Hub is unreachable, not as a soft fallback:

```bash
sudo cp deploy/mirrors/docker-daemon-registry-mirrors.json /etc/docker/daemon.json
sudo systemctl restart docker
docker info | grep -A5 'Registry Mirrors'
```

## References

- Shecan: https://pkg.shecan.ir/mirrors/
- Runflare / Liara / Arvan — see `iran.env`
