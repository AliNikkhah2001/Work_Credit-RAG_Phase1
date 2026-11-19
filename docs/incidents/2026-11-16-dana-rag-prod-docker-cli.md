# Incident 2026-11-16 — dana-rag-prod Build images failing (docker CLI)

**Status:** Resolved. dana-rag-prod build #36 SUCCESS on `main` (HealthCheck `20261116T115157Z-ai-gpu1`, `jenkins.build_ok=true`).
**Owner:** Ali Nikkhah. **Host:** ai-gpu1 (H200), controller `dana-jenkins-prod`.

## Impact
- Builds #21–#25 failed at "Build images". No new prod images were baked for those commits; the stack kept running on older digests.
- HealthCheck stack reported HEALTHY while CI was red, so the failure was only visible in Jenkins forensics.

## Root cause (layered)
1. **Host docker binary bind-mount.** `docker-compose.h200.yml` mounted host `/usr/bin/docker` into the controller. The host CLI is dynamically linked, so inside the container the ELF loader is missing → ENOENT → bash reports `docker: command not found`.
2. **Image had no static CLI.** `dana-jenkins:production` lacked a working `/usr/local/bin/docker`.
3. **Recreate dropped the overlay.** Jenkins was recreated with only `docker-compose.yml` + `docker-compose.gpu.yml`, skipping `h200.yml`. A `git pull` alone never applied the fix.
4. **CLI without compose plugin.** The static CLI fetched by CI had no `compose` plugin → `unknown shorthand flag: 'f' in -f`.
5. **Image digest drift (after build worked).** `retag` preferred a stale `:local` tag and overwrote fresh compose digests, so "SUCCESS" did not mean images refreshed. Fixed by preferring the compose `:TAG` (commit f317f5e).
6. **OpenJDK dropped from PATH.** Setting PATH without `/opt/java/openjdk/bin` made the controller exit 127.

## Fix (landed on main)
- PR #100 — static CLI path / `bootstrap_jenkins_docker_cli.sh` / `Dockerfile.docker-cli`
- PR #111 / #113 — client-only Dockerfile verify, OpenJDK on h200 PATH, `ci_resolve_docker.sh` fetches compose plugin, recreate scripts always include `h200.yml`
- PR #116 — explicit `[ci prod]` trigger
- commits 95d0806 / 1707dc7 / f317f5e / 989c503 — REGISTRY unbound fix, WebUI recreate, retag preference, no recreate during a running build

## Verification
- Build #30 and later: real `docker compose build`, no `command not found`, no `unknown shorthand flag`.
- Build #34: webui digest refreshed (`sha256:c4fa98f84e6a`).
- Build #36 on main: SUCCESS, images_ok, build_ok (HealthCheck monitoring report).

## Lessons / rules
- Always recreate Jenkins with all three compose files on H200.
- Do not recreate Jenkins while `dana-rag-prod` is building.
- A green build proves compose ran; prove image refresh with `docker image inspect` Created/Id.
- Child repo change → child main → umbrella gitlink bump with `[ci prod]`.
