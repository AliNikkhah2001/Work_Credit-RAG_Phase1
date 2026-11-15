# Package mirrors (Iran / regional fallbacks)

Used when corporate Squid + upstream PyPI/npm/Docker Hub time out on the H200
(`dana-rag-prod` #18: PyPI ReadTimeout + `Skipping rag-webui` with no npm).

| Ecosystem | Primary (CI default on GPU) | Fallbacks |
|-----------|-----------------------------|-----------|
| **pip / uv** | `mirror-pypi.pkg.shecan.ir` | runflare, liara, `pypi.org` |
| **npm** | `mirror-npm.pkg.shecan.ir` | runflare |
| **Docker Hub** | host `daemon.json` mirrors | Arvan, focker, shecan, kargadan |
| **apt (Ubuntu)** | optional host config | Arvan, `ir.archive.ubuntu.com` |

## CI (automatic)

`scripts/ci_apply_iran_mirrors.sh` is sourced from the Jenkins **Build images**
stage when `DANA_HOST=gpu` / `DANA_ROLE=prod` (or `CI_USE_IRAN_MIRRORS=1`).

It exports `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `UV_INDEX_URL`,
`NPM_CONFIG_REGISTRY`, and compose build-args consume the pip vars.

Override or disable:

```bash
CI_USE_IRAN_MIRRORS=0          # keep upstream only
PIP_INDEX_URL=https://pypi.org/simple
NPM_CONFIG_REGISTRY=https://registry.npmjs.org
```

## GPU host Docker Hub mirrors (one-time, root)

```bash
sudo cp deploy/mirrors/docker-daemon-registry-mirrors.json /etc/docker/daemon.json
# or merge registry-mirrors into an existing daemon.json
sudo systemctl restart docker
docker info | grep -A5 'Registry Mirrors'
```

## References

- Shecan: https://pkg.shecan.ir/mirrors/
- Runflare / Liara / Arvan / IranServer community lists (see `iran.env`)
