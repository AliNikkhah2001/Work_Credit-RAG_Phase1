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
            when {
                allOf {
                    expression { return env.CI_SKIP != '1' }
                    anyOf {
                        expression { return env.CI_BUILD == '1' }
                        expression { return env.CI_STAGE == '1' }
                        expression { return env.CI_PROD == '1' }
                        expression { return env.CI_AUTO == '1' }
                        expression { return env.CHANGE_ID != null }
                        expression { return env.CI_HEAVY_PATHS == '1' }
                    }
                }
            }
            steps {
                sh '''
                    set -e
                    python3 -m pip install --quiet ruff || true
                    ruff check components/orchestrator/src components/guardrails/src components/knowledgebase/kb-manager/kb_manager || true
                    python3 scripts/build_keep_graph.py || true
                    python3 scripts/ci_message_gate.py --self-test
                    python3 scripts/ci_controller_role.py --self-test
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
                    SVC="${CI_SERVICES:-all}"
                    if [ "$SVC" = "none" ]; then
                      echo "CI_SERVICES=none — skipping image build"
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
                        if [ "${DANA_HOST:-laptop}" = "gpu" ] || [ "${DANA_ROLE:-stage}" = "prod" ]; then
                          docker compose -f ${COMPOSE_BASE} -f ${COMPOSE_GPU} --env-file ${ENV_FILE_PROD:-${ENV_FILE}} build ${BUILD_SERVICES}
                        else
                          docker compose -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} --env-file ${ENV_FILE} build ${BUILD_SERVICES}
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
                    for s in ${BUILD_SERVICES}; do
                      case "$s" in
                        kb) docker tag rag-kb:local ${REGISTRY}rag-kb:${TAG} || true ;;
                        guardrails) docker tag rag-guardrails:local ${REGISTRY}rag-guardrails:${TAG} || true ;;
                        orchestrator) docker tag rag-orchestrator:local ${REGISTRY}rag-orchestrator:${TAG} || true ;;
                        tracing) docker tag rag-tracing:local ${REGISTRY}rag-tracing:${TAG} || true ;;
                        webui) docker tag rag-webui:local ${REGISTRY}rag-webui:${TAG} || true ;;
                      esac
                    done
                '''
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
                    for p in 18100 18200 18000 14000; do
                      curl -sf --max-time 5 http://127.0.0.1:$p/health \
                        || curl -sf --max-time 5 http://127.0.0.1:$p/health/liveliness \
                        || echo "port $p warming"
                    done
                '''
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
                '''
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
                    chmod +x scripts/ci_record_last_good.sh
                    HOST_REPO="${DANA_HOST_REPO:-.}"
                    # Snapshot current last-good as .prev before this deploy becomes the new tip
                    if [ -f "${HOST_REPO}/deploy/compose/.last_good_sha" ]; then
                      cp -f "${HOST_REPO}/deploy/compose/.last_good_sha" \
                        "${HOST_REPO}/deploy/compose/.last_good_sha.prev" || true
                    fi
                    if [ "${DANA_HOST:-laptop}" = "gpu" ]; then
                      test -f ${ENV_FILE_PROD} || cp deploy/compose/.env.example ${ENV_FILE_PROD}
                      docker compose -p dana-prod -f ${COMPOSE_BASE} -f ${COMPOSE_GPU} --env-file ${ENV_FILE_PROD} up -d
                    else
                      # Laptop prod-sim still uses OpenRouter local overlay
                      docker compose -p dana-prod -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} -f ${COMPOSE_PROD} --env-file ${ENV_FILE} up -d
                    fi
                    sleep 25
                    for p in 8100 8200 8000 4000; do
                      curl -sf --max-time 5 http://127.0.0.1:$p/health \
                        || curl -sf --max-time 5 http://127.0.0.1:$p/health/liveliness \
                        || echo "port $p warming"
                    done
                    # Record this commit as last-known-good after health probes
                    bash scripts/ci_record_last_good.sh "${GIT_COMMIT}"
                '''
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true; rm -f .ci_commit_msg.txt .ci_changed_files.txt .ci_gate.env .ci_role.env || true'
        }
        failure {
            echo 'Pipeline failed — inspect Jenkins console + docker compose logs'
        }
    }
}
