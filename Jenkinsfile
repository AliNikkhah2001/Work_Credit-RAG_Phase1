// Dana / Work Credit RAG — Multibranch Jenkinsfile (laptop → H200)
// Poll SCM hourly (no paid webhook). Deploy gates use commit-message keys.
//
// Keys (case-insensitive, anywhere in the commit subject/body):
//   [ci skip] / [skip ci]  → no build work
//   [ci build]             → build images (any branch)
//   [ci stage]             → build + deploy stage (develop)
//   [ci prod]              → build + deploy prod WITHOUT manual approval (main)
//   [ci auto]              → same as stage on develop / prod on main (unattended)
//
// Cron alone does not deploy: poll only discovers commits; keys still required
// for stage/prod deploy (except optional path-triggered feature builds).

pipeline {
    // Same absolute path as the Mac host repo (see deploy/jenkins/docker-compose.yml)
    // so docker.sock bind mounts resolve. Nested .ci-workspace keeps the clone clean.
    agent {
        node {
            label ''
            customWorkspace '/Users/alinikkhah/Documents/Work/CreditScoring/Chatbot_production_v1/.ci-workspace'
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
                    git submodule update --init --recursive || true
                    git log -1 --pretty=%B > .ci_commit_msg.txt
                    git diff --name-only HEAD~1...HEAD 2>/dev/null > .ci_changed_files.txt || true
                    if command -v python3 >/dev/null 2>&1; then
                      python3 scripts/ci_message_gate.py --write-env .ci_gate.env
                    else
                      echo "WARNING: python3 missing on agent — defaulting gate to skip"
                      printf 'CI_SKIP=1\nCI_BUILD=0\nCI_STAGE=0\nCI_PROD=0\nCI_AUTO=0\nCI_HEAVY_PATHS=0\n' > .ci_gate.env
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
                    echo "CI gate: SKIP=${env.CI_SKIP} BUILD=${env.CI_BUILD} STAGE=${env.CI_STAGE} PROD=${env.CI_PROD} AUTO=${env.CI_AUTO} HEAVY=${env.CI_HEAVY_PATHS} BRANCH=${env.BRANCH_NAME}"
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
                '''
            }
        }

        stage('Build images') {
            when {
                allOf {
                    expression { return env.CI_SKIP != '1' }
                    anyOf {
                        expression { return env.CI_BUILD == '1' }
                        expression { return env.CI_STAGE == '1' }
                        expression { return env.CI_PROD == '1' }
                        expression { return env.CI_AUTO == '1' }
                        expression { return env.CHANGE_ID != null && env.CI_HEAVY_PATHS == '1' }
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
                    export TAG=${TAG}
                    # Laptop/test Multibranch uses OpenRouter local overlay unless DANA_HOST=gpu
                    if [ "${DANA_HOST:-laptop}" = "gpu" ]; then
                      docker compose -f ${COMPOSE_BASE} -f ${COMPOSE_GPU} --env-file ${ENV_FILE_PROD:-${ENV_FILE}} build
                    else
                      docker compose -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} --env-file ${ENV_FILE} build
                    fi
                    docker tag rag-kb:local ${REGISTRY}rag-kb:${TAG} || true
                    docker tag rag-guardrails:local ${REGISTRY}rag-guardrails:${TAG} || true
                    docker tag rag-orchestrator:local ${REGISTRY}rag-orchestrator:${TAG} || true
                    docker tag rag-tracing:local ${REGISTRY}rag-tracing:${TAG} || true
                '''
            }
        }

        stage('Deploy stage') {
            when {
                allOf {
                    branch 'develop'
                    expression { return env.CI_SKIP != '1' }
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
                    docker compose -p dana-stage -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} -f ${COMPOSE_STAGE} --env-file ${ENV_FILE} up -d --force-recreate litellm
                    docker compose -p dana-stage -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} -f ${COMPOSE_STAGE} --env-file ${ENV_FILE} up -d
                    # litellm image can take >25s to become healthy
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
                    expression { return env.CI_SKIP != '1' }
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
                    expression { return env.CI_SKIP != '1' }
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
                    expression { return env.CI_SKIP != '1' }
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
                '''
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true; rm -f .ci_commit_msg.txt .ci_changed_files.txt .ci_gate.env || true'
        }
        failure {
            echo 'Pipeline failed — inspect Jenkins console + docker compose logs'
        }
    }
}
