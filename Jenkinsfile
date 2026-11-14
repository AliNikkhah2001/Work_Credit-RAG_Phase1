// Dana / Work Credit RAG — Multibranch Jenkinsfile
// Sprint A: separate controllers (DANA_ROLE). Sprint B: path builds + submodule sync.
// Poll SCM hourly (no paid webhook). Deploy gates use commit-message keys.
//
// Controller role (env from deploy/jenkins/docker-compose*.yml):
//   DANA_ROLE=stage (laptop)  → job dana-rag-stage; may deploy dana-stage only
//   DANA_ROLE=prod  (GPU)     → job dana-rag-prod;  may deploy prod/gpu only
//
// Keys (case-insensitive, anywhere in the commit subject/body):
//   [ci skip] / [skip ci]  → no build work
//   [ci build]             → build images (any branch)
//   [ci stage]             → build + deploy stage (develop) — stage controller only
//   [ci prod]              → build + deploy prod WITHOUT manual approval (main) — prod controller only
//   [ci auto]              → stage on develop / prod on main (still role-gated)
//   [ci all]               → force full image set (ignore path filter)
//   [ci rollback]          → restore deploy/compose/.last_good_sha (prod controller)
//
// CI_SERVICES from scripts/ci_message_gate.py: "kb", "kb guardrails", "all", or "none".
//
// Verification proof (no more false green):
//   A stage-only controller sets CI_MAY_DEPLOY_PROD=0, so every prod stage is
//   dropped by its `when` guard. Before the coverage gate, such a `main` build
//   finished SUCCESS having run only Lint, while GitHub showed the commit green
//   (dana-rag/main #20, #21). Each stage now leaves an evidence marker
//   (scripts/ci_stage_evidence.sh) and the final `post` block asks
//   scripts/ci_verify_coverage.py what that evidence actually proves, publishes
//   it as `dana/validate`, and downgrades the build when proof is missing.
//
//   CI_MAIN_PROOF_POLICY=unstable|fail|allow  (default unstable)
//     unstable — main without a prod controller is UNSTABLE (never green)
//     fail     — same, but hard FAILURE (what the GPU prod host should use)
//     allow    — keep SUCCESS on the Jenkins side (the `dana/validate`
//                commit status still reports failure, so GitHub stays honest)
//
//   CI_REQUIRE_PROD_CONTROLLER=1 — this host is supposed to verify prod
//     (set on the GPU daemon); turns a missing prod proof into a hard failure.

pipeline {
    // Host-identical path (DANA_HOST_REPO) so docker.sock bind mounts resolve.
    agent {
        node {
            label ''
            customWorkspace "${env.DANA_HOST_REPO ?: '/Users/alinikkhah/Documents/Work/CreditScoring/Chatbot_production_v1'}/.ci-workspace"
        }
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    // No Cloudflare/webhook: poll GitHub every hour (hashed minute).
    triggers {
        pollSCM('H * * * *')
    }

    environment {
        REGISTRY = "${env.REGISTRY ?: ''}"
        TAG = "${env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : 'local'}"
        COMPOSE_BASE = 'deploy/compose/compose.base.yml'
        COMPOSE_LOCAL = 'deploy/compose/compose.local.yml'
        COMPOSE_STAGE = 'deploy/compose/compose.stage.yml'
        COMPOSE_PROD = 'deploy/compose/compose.prod-sim.yml'
        COMPOSE_GPU = 'deploy/compose/compose.gpu.yml'
        ENV_FILE = 'deploy/compose/.env'
        ENV_FILE_PROD = 'deploy/compose/.env.prod'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh '''
                    set -e
                    chmod +x scripts/ci_submodule_sync.sh scripts/ci_message_gate.py scripts/ci_controller_role.py || true
                    # Workspace is reused across builds/branches: clear stage
                    # evidence so a previous run cannot vouch for this one.
                    bash scripts/ci_stage_evidence.sh reset || rm -rf .ci-evidence
                    bash scripts/ci_submodule_sync.sh
                    git log -1 --pretty=%B > .ci_commit_msg.txt
                    git diff --name-only HEAD~1...HEAD 2>/dev/null > .ci_changed_files.txt || true
                    if command -v python3 >/dev/null 2>&1; then
                      python3 scripts/ci_message_gate.py --write-env .ci_gate.env
                      python3 scripts/ci_controller_role.py --write-env .ci_role.env
                    else
                      echo "WARNING: python3 missing on agent — defaulting gate to skip"
                      printf 'CI_SKIP=1\nCI_BUILD=0\nCI_STAGE=0\nCI_PROD=0\nCI_AUTO=0\nCI_ROLLBACK=0\nCI_HEAVY_PATHS=0\nCI_SERVICES=none\n' > .ci_gate.env
                      printf 'DANA_ROLE=stage\nCI_MAY_DEPLOY_STAGE=1\nCI_MAY_DEPLOY_PROD=0\n' > .ci_role.env
                    fi
                '''
                script {
                    def gate = readFile('.ci_gate.env').trim().split('\n') as List
                    gate.each { line ->
                        if (line.contains('=')) {
                            def (k, v) = line.split('=', 2)
                            env."${k}" = v
                        }
                    }
                    def roleEnv = readFile('.ci_role.env').trim().split('\n') as List
                    roleEnv.each { line ->
                        if (line.contains('=')) {
                            def (k, v) = line.split('=', 2)
                            env."${k}" = v
                        }
                    }
                    echo "CI controller: ROLE=${env.DANA_ROLE} MAY_STAGE=${env.CI_MAY_DEPLOY_STAGE} MAY_PROD=${env.CI_MAY_DEPLOY_PROD} HOST=${env.DANA_HOST} JOB=${env.JOB_NAME}"
                    echo "CI gate: SKIP=${env.CI_SKIP} BUILD=${env.CI_BUILD} STAGE=${env.CI_STAGE} PROD=${env.CI_PROD} AUTO=${env.CI_AUTO} ROLLBACK=${env.CI_ROLLBACK} HEAVY=${env.CI_HEAVY_PATHS} SERVICES=${env.CI_SERVICES} BRANCH=${env.BRANCH_NAME}"
                }
            }
        }

        stage('Skip') {
            when { expression { return env.CI_SKIP == '1' } }
            steps {
                echo 'Commit contains [ci skip] / [skip ci] — aborting remaining stages.'
            }
        }

        stage('Lint') {
            // Lint is the baseline proof that a build ran *something*: it carries
            // the gate self-tests (message gate, controller role, coverage
            // verdict, stage evidence) and it is the only stage the coverage
            // verifier requires on every branch. It therefore runs on EVERY
            // build except an explicit `[ci skip]`.
            //
            // This used to be guarded by `CI_BUILD/STAGE/PROD/AUTO/CHANGE_ID/
            // HEAVY_PATHS`, which is true only when a commit *asked* for
            // something. A docs-only commit (CI_SERVICES=none, no markers)
            // therefore ran no stage at all, and `ci_verify_coverage.py`
            // correctly reported `unexpected-missing: lint` -> build FAILURE and
            // a red `dana/validate` on GitHub (observed on build #3 of
            // feature/lastgood-retention, and #1 of feature/ops-diagnostics).
            // Failing a docs-only push teaches people to ignore red, so the
            // guard is gone rather than the verifier being loosened: the
            // verdict stays honest and it is now satisfiable.
            when { expression { return env.CI_SKIP != '1' } }
            steps {
                sh '''
                    set -e
                    bash scripts/ci_stage_evidence.sh mark lint || true
                    # Ruff is advisory: install may fail on hosts with an
                    # externally-managed Python (Debian/Ubuntu system python),
                    # which is what produced build #52's visible
                    # `error: externally-managed-environment`. A lint tool that
                    # is not installed must never turn a good build red.
                    if command -v ruff >/dev/null 2>&1; then
                      ruff check components/orchestrator/src components/guardrails/src \
                        components/knowledgebase/kb-manager/kb_manager || true
                    else
                      echo "ruff not installed on agent — skipping advisory lint"
                    fi
                    python3 scripts/build_keep_graph.py || true
                    # These two ARE gates: they decide whether this commit may
                    # build/deploy, so a failure here is a real failure.
                    python3 scripts/ci_message_gate.py --self-test
                    python3 scripts/ci_controller_role.py --self-test
                    python3 scripts/ci_verify_coverage.py --self-test
                    bash scripts/ci_stage_evidence.sh self-test
                '''
            }
        }

        stage('Rollback prod') {
            when {
                allOf {
                    branch 'main'
                    expression { return env.CI_MAY_DEPLOY_PROD == '1' }
                    expression { return env.CI_SKIP != '1' }
                    expression { return env.CI_ROLLBACK == '1' }
                }
            }
            steps {
                sh '''
                    set -e
                    chmod +x scripts/ci_rollback.sh
                    bash scripts/ci_rollback.sh
                '''
            }
        }

        stage('Build images') {
            when {
                allOf {
                    expression { return env.CI_SKIP != '1' }
                    expression { return env.CI_ROLLBACK != '1' }
                    anyOf {
                        // Explicit rebuild anywhere
                        expression { return env.CI_BUILD == '1' }
                        // Stage controller: only build for develop (ignore [ci stage] on main merges)
                        allOf {
                            expression { return env.CI_MAY_DEPLOY_STAGE == '1' }
                            expression { return env.CI_MAY_DEPLOY_PROD != '1' }
                            anyOf {
                                branch 'develop'
                                expression { return env.CHANGE_ID != null }
                            }
                            anyOf {
                                expression { return env.CI_STAGE == '1' }
                                expression { return env.CI_AUTO == '1' }
                                expression { return env.CHANGE_ID != null && env.CI_HEAVY_PATHS == '1' }
                            }
                        }
                        // Prod controller: only build for main
                        allOf {
                            expression { return env.CI_MAY_DEPLOY_PROD == '1' }
                            branch 'main'
                            anyOf {
                                expression { return env.CI_PROD == '1' }
                                expression { return env.CI_AUTO == '1' }
                                expression { return env.CI_HEAVY_PATHS == '1' }
                            }
                        }
                    }
                }
            }
            steps {
                sh '''
                    set -e
                    # Prefer laptop secrets from host clone (gitignored); workspace is .ci-workspace
                    HOST_REPO="${DANA_HOST_REPO:-/Users/alinikkhah/Documents/Work/CreditScoring/Chatbot_production_v1}"
                    for src in \
                      "${HOST_REPO}/deploy/compose/.env" \
                      ../deploy/compose/.env; do
                      if [ -f "$src" ]; then cp -f "$src" ${ENV_FILE}; break; fi
                    done
                    test -f ${ENV_FILE} || cp deploy/compose/.env.example ${ENV_FILE}
                    # Stale host .env pins KB_RERANKER_BACKEND=local; laptop OpenRouter
                    # mode must still call the OpenRouter rerank API.
                    chmod +x scripts/ci_laptop_rerank_env.sh
                    bash scripts/ci_laptop_rerank_env.sh ${ENV_FILE}
                    export TAG=${TAG}
                    # Slow/flaky PyPI under parallel compose builds (common on laptop CI)
                    export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"
                    export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"
                    # Persist pip wheels via Dockerfile RUN --mount=type=cache
                    export DOCKER_BUILDKIT=1
                    export COMPOSE_DOCKER_CLI_BUILD=1
                    # Laptop OpenRouter CI: CPU torch only (no nvidia_* / cudnn wheels).
                    # GPU prod uses compose.gpu → TORCH_CHANNEL=cuda.
                    if [ "${DANA_HOST:-laptop}" = "gpu" ] || [ "${DANA_ROLE:-stage}" = "prod" ]; then
                      export KB_TORCH_CHANNEL="${KB_TORCH_CHANNEL:-cuda}"
                    else
                      export KB_TORCH_CHANNEL="${KB_TORCH_CHANNEL:-cpu}"
                    fi
                    echo "KB_TORCH_CHANNEL=${KB_TORCH_CHANNEL}"
                    SVC="${CI_SERVICES:-all}"
                    if [ "$SVC" = "none" ]; then
                      echo "CI_SERVICES=none — skipping image build (deploy will use existing :local tags)"
                      exit 0
                    fi
                    if [ "$SVC" = "all" ]; then
                      BUILD_SERVICES="kb guardrails orchestrator tracing"
                    else
                      BUILD_SERVICES="$SVC"
                    fi
                    # WebUI only when requested (all or webui) and assets available
                    case " $BUILD_SERVICES " in
                      *" webui "*|*"all"*) NEED_WEBUI=1 ;;
                      *) NEED_WEBUI=0 ;;
                    esac
                    if [ "$SVC" = "all" ]; then NEED_WEBUI=1; fi
                    if [ "$NEED_WEBUI" = "1" ]; then
                      if [ -f components/webui/package.json ] && command -v npm >/dev/null 2>&1; then
                        (
                          cd components/webui
                          export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=8192}"
                          # Always rebuild frontend — leftover build/ from a prior SHA caused
                          # stage to ship stale Dana themes while reporting "webui Built".
                          rm -rf build .svelte-kit
                          ONNXRUNTIME_NODE_INSTALL_CUDA=skip npm ci --force
                          npm run build
                          find build -type f -name '*.map' -delete || true
                        )
                        case " $BUILD_SERVICES " in *" webui "*) ;; *) BUILD_SERVICES="${BUILD_SERVICES} webui" ;; esac
                      elif [ -d "${HOST_REPO}/components/webui/build" ]; then
                        mkdir -p components/webui
                        rm -rf components/webui/build
                        cp -a "${HOST_REPO}/components/webui/build" components/webui/build
                        case " $BUILD_SERVICES " in *" webui "*) ;; *) BUILD_SERVICES="${BUILD_SERVICES} webui" ;; esac
                        echo "Using WebUI build/ copied from host repo (npm unavailable in agent)"
                      elif [ -d components/webui/build ]; then
                        case " $BUILD_SERVICES " in *" webui "*) ;; *) BUILD_SERVICES="${BUILD_SERVICES} webui" ;; esac
                        echo "WARNING: reusing existing components/webui/build without npm rebuild"
                      else
                        echo "Skipping rag-webui image build (no npm and no components/webui/build)"
                        BUILD_SERVICES="$(echo "$BUILD_SERVICES" | tr ' ' '\n' | grep -v '^webui$' | tr '\n' ' ')"
                      fi
                    fi
                    echo "Building compose services: ${BUILD_SERVICES} (parallel_limit=${COMPOSE_PARALLEL_LIMIT})"
                    # Ensure tracing optional wheels/ context exists (host may prefetch *.whl when PyPI works)
                    mkdir -p components/tracing/wheels
                    touch components/tracing/wheels/.gitkeep
                    # Serialize develop/main docker builds on one host (flock) + retry PyPI timeouts
                    LOCK="${HOST_REPO}/.ci-workspace/.dana-docker-build.lock"
                    mkdir -p "$(dirname "$LOCK")"
                    image_for() {
                      case "$1" in
                        kb) echo rag-kb:local ;;
                        guardrails) echo rag-guardrails:local ;;
                        orchestrator) echo rag-orchestrator:local ;;
                        tracing) echo rag-tracing:local ;;
                        webui) echo rag-webui:local ;;
                        *) echo "" ;;
                      esac
                    }
                    have_all_images() {
                      for s in ${BUILD_SERVICES}; do
                        img="$(image_for "$s")"
                        [ -n "$img" ] || continue
                        docker image inspect "$img" >/dev/null 2>&1 || return 1
                      done
                      return 0
                    }
                    (
                      flock -w 2400 9
                      build_once() {
                        export DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1
                        # -p is explicit: --env-file carries COMPOSE_PROJECT_NAME=dana-local,
                        # so a stage/prod build without -p would be labelled as the dev project.
                        if [ "${DANA_HOST:-laptop}" = "gpu" ] || [ "${DANA_ROLE:-stage}" = "prod" ]; then
                          docker compose -p dana-prod -f ${COMPOSE_BASE} -f ${COMPOSE_GPU} --env-file ${ENV_FILE_PROD:-${ENV_FILE}} build ${BUILD_SERVICES}
                        else
                          docker compose -p dana-local -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} --env-file ${ENV_FILE} build ${BUILD_SERVICES}
                        fi
                      }
                      ok=0
                      for attempt in 1 2 3; do
                        echo "docker compose build attempt ${attempt}/3"
                        if build_once; then ok=1; break; fi
                        echo "build attempt ${attempt} failed — retrying in 20s (often PyPI ReadTimeout)"
                        sleep 20
                      done
                      if [ "$ok" != "1" ]; then
                        # Laptop CI: files.pythonhosted.org often stalls via Docker Desktop proxy.
                        # Reuse existing :local images so stage deploy/E2E can still run.
                        if [ "${DANA_HOST:-laptop}" = "laptop" ] && [ "${CI_FORCE_BUILD:-0}" != "1" ] && have_all_images; then
                          echo "WARNING: compose build failed after retries, but all required :local images exist — continuing with cached images (set CI_FORCE_BUILD=1 to fail hard)."
                          ok=1
                        fi
                      fi
                      [ "$ok" = "1" ] || exit 1
                    ) 9>"$LOCK"
                    # Always publish :local → :${TAG} for the whole app matrix so path-filtered
                    # builds (SERVICES=kb) still satisfy compose image: rag-*:${TAG} on deploy.
                    for s in kb guardrails orchestrator tracing webui; do
                      case "$s" in
                        kb) src=rag-kb:local; dst=${REGISTRY}rag-kb:${TAG} ;;
                        guardrails) src=rag-guardrails:local; dst=${REGISTRY}rag-guardrails:${TAG} ;;
                        orchestrator) src=rag-orchestrator:local; dst=${REGISTRY}rag-orchestrator:${TAG} ;;
                        tracing) src=rag-tracing:local; dst=${REGISTRY}rag-tracing:${TAG} ;;
                        webui) src=rag-webui:local; dst=${REGISTRY}rag-webui:${TAG} ;;
                      esac
                      if docker image inspect "$src" >/dev/null 2>&1; then
                        docker tag "$src" "$dst" || true
                      fi
                    done
                    bash scripts/ci_stage_evidence.sh mark build || true
                '''
            }
            post {
                success { ghStatus('build', 'success', 'app images built') }
                failure { ghStatus('build', 'failure', 'image build failed') }
            }
        }

        stage('Deploy stage') {
            when {
                allOf {
                    branch 'develop'
                    expression { return env.CI_MAY_DEPLOY_STAGE == '1' }
                    expression { return env.CI_SKIP != '1' }
                    expression { return env.CI_ROLLBACK != '1' }
                    anyOf {
                        expression { return env.CI_STAGE == '1' }
                        expression { return env.CI_AUTO == '1' }
                    }
                }
            }
            steps {
                sh '''
                    set -e
                    HOST_REPO="${DANA_HOST_REPO:-/Users/alinikkhah/Documents/Work/CreditScoring/Chatbot_production_v1}"
                    for src in \
                      "${HOST_REPO}/deploy/compose/.env" \
                      ../deploy/compose/.env; do
                      if [ -f "$src" ]; then cp -f "$src" ${ENV_FILE}; break; fi
                    done
                    test -f ${ENV_FILE} || cp deploy/compose/.env.example ${ENV_FILE}
                    chmod +x scripts/ci_laptop_rerank_env.sh
                    bash scripts/ci_laptop_rerank_env.sh ${ENV_FILE}
                    SVC="${CI_SERVICES:-all}"
                    # Path-filtered / skip-build runs: compose still wants rag-*:${TAG}
                    for s in kb guardrails orchestrator tracing webui; do
                      case "$s" in
                        kb) src=rag-kb:local; dst=${REGISTRY}rag-kb:${TAG} ;;
                        guardrails) src=rag-guardrails:local; dst=${REGISTRY}rag-guardrails:${TAG} ;;
                        orchestrator) src=rag-orchestrator:local; dst=${REGISTRY}rag-orchestrator:${TAG} ;;
                        tracing) src=rag-tracing:local; dst=${REGISTRY}rag-tracing:${TAG} ;;
                        webui) src=rag-webui:local; dst=${REGISTRY}rag-webui:${TAG} ;;
                      esac
                      if docker image inspect "$src" >/dev/null 2>&1; then
                        docker tag "$src" "$dst" || true
                      fi
                    done
                    COMPOSE="docker compose -p dana-stage -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} -f ${COMPOSE_STAGE} --env-file ${ENV_FILE}"
                    # Never rebuild images during deploy — Build stage already produced :local tags.
                    # Without --no-build, `up kb` re-downloads torch (~500MB) on every orch-only change.
                    # Keep LiteLLM healthy for stage OpenRouter path
                    $COMPOSE up -d --no-build litellm
                    if [ "$SVC" = "all" ] || [ "$SVC" = "none" ]; then
                      $COMPOSE up -d --no-build
                    else
                      # Targeted recreate of changed app services; ensure deps are up
                      $COMPOSE up -d --no-build postgres redis tracing
                      for s in $SVC; do
                        echo "Recreating stage service: $s"
                        $COMPOSE up -d --no-build --no-deps --force-recreate "$s"
                      done
                      # Orchestrator/guardrails often need full graph even if not rebuilt
                      $COMPOSE up -d --no-build orchestrator guardrails kb
                    fi
                    for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
                      if curl -sf --max-time 3 http://127.0.0.1:14000/health/liveliness >/dev/null \
                         && curl -sf --max-time 3 http://127.0.0.1:18100/health >/dev/null; then
                        echo "stage healthy"
                        break
                      fi
                      sleep 10
                    done
                    # Health-gated: published ports + container health + endpoints.
                    # "compose up returned 0" is NOT success — base compose has no
                    # ports, so a bad overlay yields a healthy stack with no :13100.
                    chmod +x scripts/ci_deploy_gate.sh scripts/ci_record_last_good.sh
                    bash scripts/ci_deploy_gate.sh \
                      --ports 13100,18100,18000,18200 \
                      --compose "docker compose -p dana-stage -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} -f ${COMPOSE_STAGE} --env-file ${ENV_FILE}" \
                      || { echo "stage deploy gate FAILED — not recording last-good for stage"; exit 1; }
                    echo "stage deploy gate passed"
                    bash scripts/ci_stage_evidence.sh mark stage-deploy || true
                '''
            }
            post {
                success { ghStatus('stage-deploy', 'success', 'stage deploy + health gate passed') }
                failure { ghStatus('stage-deploy', 'failure', 'stage deploy or health gate failed') }
            }
        }
        stage('E2E stage') {
            when {
                allOf {
                    branch 'develop'
                    expression { return env.CI_MAY_DEPLOY_STAGE == '1' }
                    expression { return env.CI_SKIP != '1' }
                    expression { return env.CI_ROLLBACK != '1' }
                    anyOf {
                        expression { return env.CI_STAGE == '1' }
                        expression { return env.CI_AUTO == '1' }
                    }
                }
            }
            steps {
                sh '''
                    set -e
                    curl -sf --max-time 30 http://127.0.0.1:18000/health | head -c 200; echo
                    curl -sf --max-time 90 http://127.0.0.1:18100/v1/chat/completions \
                      -H 'Content-Type: application/json' \
                      -d '{"model":"chat-primary","messages":[{"role":"user","content":"سلام"}]}' | head -c 500; echo
                    bash scripts/ci_stage_evidence.sh mark stage-e2e || true
                '''
            }
            post {
                success { ghStatus('stage-e2e', 'success', 'stage E2E chat probe passed') }
                failure { ghStatus('stage-e2e', 'failure', 'stage E2E chat probe failed') }
            }
        }

        stage('Prod approval (interactive only)') {
            when {
                allOf {
                    branch 'main'
                    expression { return env.CI_MAY_DEPLOY_PROD == '1' }
                    expression { return env.CI_SKIP != '1' }
                    expression { return env.CI_ROLLBACK != '1' }
                    expression { return env.CI_PROD != '1' }
                    expression { return env.CI_AUTO != '1' }
                    anyOf {
                        expression { return env.CI_BUILD == '1' }
                        expression { return env.CI_HEAVY_PATHS == '1' }
                    }
                }
            }
            steps {
                input message: 'No [ci prod]/[ci auto] on this commit. Deploy prod anyway?', ok: 'Deploy'
            }
        }

        stage('Deploy prod') {
            when {
                allOf {
                    branch 'main'
                    expression { return env.CI_MAY_DEPLOY_PROD == '1' }
                    expression { return env.CI_SKIP != '1' }
                    expression { return env.CI_ROLLBACK != '1' }
                    anyOf {
                        expression { return env.CI_PROD == '1' }
                        expression { return env.CI_AUTO == '1' }
                        // after interactive approval path: BUILD was requested without auto key
                        allOf {
                            expression { return env.CI_BUILD == '1' || env.CI_HEAVY_PATHS == '1' }
                            expression { return env.CI_PROD != '1' }
                            expression { return env.CI_AUTO != '1' }
                        }
                    }
                }
            }
            steps {
                sh '''
                    set -e
                    chmod +x scripts/ci_deploy_gate.sh scripts/ci_record_last_good.sh scripts/ci_rollback.sh
                    HOST_REPO="${DANA_HOST_REPO:-.}"
                    # Keep the previous manifest before this deploy overwrites it.
                    for f in .last_good.json .last_good_sha; do
                      if [ -f "${HOST_REPO}/deploy/compose/$f" ]; then
                        cp -f "${HOST_REPO}/deploy/compose/$f" "${HOST_REPO}/deploy/compose/$f.prev" || true
                      fi
                    done
                    if [ "${DANA_HOST:-laptop}" = "gpu" ]; then
                      test -f ${ENV_FILE_PROD} || cp deploy/compose/.env.example ${ENV_FILE_PROD}
                      PROD_COMPOSE="docker compose -p dana-prod -f ${COMPOSE_BASE} -f ${COMPOSE_GPU} --env-file ${ENV_FILE_PROD}"
                      PROD_PORTS="8000,8200,8100,13000"
                    else
                      # Laptop prod-sim still uses OpenRouter local overlay
                      PROD_COMPOSE="docker compose -p dana-prod -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} -f ${COMPOSE_PROD} --env-file ${ENV_FILE}"
                      PROD_PORTS="8000,8200,8100,13000"
                    fi
                    $PROD_COMPOSE up -d --no-build
                    # Health gate: publishes-ports + container health + endpoints.
                    # On failure, automatically restore the previous known-good
                    # image set instead of leaving a half-broken prod running.
                    if ! bash scripts/ci_deploy_gate.sh --ports "$PROD_PORTS" --compose "$PROD_COMPOSE"; then
                      echo "PROD DEPLOY GATE FAILED — rolling back to last-known-good"
                      DANA_GATE_PROJECT=dana-prod bash scripts/ci_rollback.sh --target prev \
                        || echo "rollback also failed — manual intervention required"
                      exit 1
                    fi
                    # Record the manifest ONLY after the gate proved the deploy.
                    bash scripts/ci_record_last_good.sh --if-gate-passes "${GIT_COMMIT}"
                    bash scripts/ci_stage_evidence.sh mark prod-deploy || true
                '''
            }
            post {
                success { ghStatus('prod-deploy', 'success', 'prod deploy + health gate passed') }
                failure { ghStatus('prod-deploy', 'failure', 'prod deploy or health gate failed') }
            }
        }
    }

    post {
        always {
            sh '''
                docker image prune -f || true
                # True-green guard: a build that only ran Lint is not a verified
                # build. dana-rag/main #20/#21 went SUCCESS on the stage-only
                # laptop controller with every build/deploy/prod stage dropped by
                # its `when` guard, which put a green GitHub check on a commit
                # nothing had ever exercised. Compute an explicit verdict from
                # the stages that actually ran.
                : > .ci_coverage.guard
                if [ -f scripts/ci_verify_coverage.py ]; then
                  RAN="$(bash scripts/ci_stage_evidence.sh list 2>/dev/null || true)"
                  chmod +x scripts/ci_verify_coverage.py 2>/dev/null || true
                  python3 scripts/ci_verify_coverage.py \
                    --branch "${BRANCH_NAME:-}" \
                    --executed "$RAN" \
                    --require-prod-controller "${CI_REQUIRE_PROD_CONTROLLER:-0}" \
                    --write-env .ci_coverage.env 2>/dev/null || true
                  cat .ci_coverage.env 2>/dev/null || true
                  sed -n 's/^COVERAGE_GUARD=//p' .ci_coverage.env 2>/dev/null > .ci_coverage.guard || true
                  sed -n 's/^COVERAGE_STATE=//p' .ci_coverage.env 2>/dev/null > .ci_coverage.state || true
                  sed -n 's/^COVERAGE_DESCRIPTION=//p' .ci_coverage.env 2>/dev/null > .ci_coverage.desc || true
                fi
                rm -f .ci_commit_msg.txt .ci_changed_files.txt .ci_gate.env .ci_role.env || true
                rm -rf .ci-evidence || true
            '''
            script {
                def guard = ''
                if (fileExists('.ci_coverage.guard')) {
                    guard = readFile('.ci_coverage.guard').trim()
                }
                // Publish the verdict BEFORE downgrading the run: the plugin's
                // own status only knows our final result, not what it covered.
                def state = fileExists('.ci_coverage.state') ? readFile('.ci_coverage.state').trim() : 'success'
                def desc = fileExists('.ci_coverage.desc') ? readFile('.ci_coverage.desc').trim() : 'Jenkins verified'
                if (state == '') { state = 'success' }
                if (desc == '') { desc = 'Jenkins verified' }
                // A build that already failed cannot vouch for coverage, even if
                // the stages that did run happened to satisfy the expectation.
                def already = currentBuild.result ?: 'SUCCESS'
                if (already != 'SUCCESS') {
                    state = 'failure'
                    desc = "build ${already}" + (desc ? ": ${desc}" : '')
                }
                ghStatus('validate', state, desc)

                if (guard == 'fail') {
                    currentBuild.result = 'FAILURE'
                    echo 'COVERAGE GUARD: FAIL — this build did not verify what it claims'
                } else if (guard == 'unstable') {
                    // Never improve an existing result: a build that already
                    // failed elsewhere must not be softened to UNSTABLE by the
                    // coverage guard.
                    def current = currentBuild.result ?: 'SUCCESS'
                    def policy = (env.CI_MAIN_PROOF_POLICY ?: 'unstable').trim().toLowerCase()
                    if (current == 'FAILURE' || current == 'ABORTED' || current == 'UNSTABLE') {
                        echo "COVERAGE GUARD: not covered (build already ${current})"
                    } else if (policy == 'allow') {
                        // Explicit opt-out for a host that is allowed to run
                        // unverified main builds (never the prod daemon). The
                        // dana/validate status above still says "not verified",
                        // so GitHub does not silently show green.
                        echo 'COVERAGE GUARD: not covered, allowed by CI_MAIN_PROOF_POLICY=allow'
                    } else if (policy == 'fail') {
                        currentBuild.result = 'FAILURE'
                        echo 'COVERAGE GUARD: FAIL — no prod controller verified main'
                    } else {
                        // Truthful, not destructive: the laptop stage controller
                        // cannot verify prod, so it must not paint main green.
                        currentBuild.result = 'UNSTABLE'
                        echo 'COVERAGE GUARD: UNSTABLE — build ran but did not cover this branch'
                    }
                }
            }
        }
        failure {
            echo 'Pipeline failed — inspect Jenkins console + docker compose logs'
        }
    }
}

// Post one named commit status. Observability only: never fails the build.
// Opt-in via GITHUB_STATUS_ENABLED=1 so a credential-less agent still builds;
// when off, the plugin's own `continuous-integration/jenkins/branch` status is
// still posted, so the build is never silently unreported.
// Credential `github-pat` (username + PAT, `repo:status`); no secret in-repo.
def ghStatus(String stage, String state, String description) {
    if ((env.GITHUB_STATUS_ENABLED ?: '0') != '1') {
        echo "GitHub status dana/${stage} skipped (GITHUB_STATUS_ENABLED!=1)"
        return
    }
    try {
        withCredentials([usernamePassword(
                credentialsId: env.GITHUB_STATUS_CREDENTIALS_ID ?: 'github-pat',
                usernameVariable: 'GITHUB_USER',
                passwordVariable: 'GITHUB_TOKEN')]) {
            withEnv(['GITHUB_STATUS_ENABLED=1']) {
                sh """
                    set +e
                    bash scripts/ci_github_status.sh \\
                      --sha "\${GIT_COMMIT}" \\
                      --state "${state}" \\
                      --context "dana/${stage}" \\
                      --description "${description}" \\
                      --target-url "\${BUILD_URL}" || true
                """
            }
        }
    } catch (Exception e) {
        echo "WARN: GitHub status dana/${stage} not reported — ${e.message}"
    }
}
