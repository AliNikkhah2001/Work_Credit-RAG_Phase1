// Dana / Work Credit RAG — umbrella Jenkinsfile (laptop Jenkins-in-Docker → H200 later)
// Multibranch: discover develop / main / feature/*

pipeline {
    agent any

    environment {
        REGISTRY = "${env.REGISTRY ?: ''}"
        TAG = "${env.GIT_COMMIT.take(7)}"
        COMPOSE_BASE = 'deploy/compose/compose.base.yml'
        COMPOSE_LOCAL = 'deploy/compose/compose.local.yml'
        COMPOSE_STAGE = 'deploy/compose/compose.stage.yml'
        COMPOSE_PROD = 'deploy/compose/compose.prod-sim.yml'
        ENV_FILE = 'deploy/compose/.env'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh '''
                    set -e
                    git submodule update --init --recursive || true
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    set -e
                    python3 -m pip install --quiet ruff || true
                    ruff check components/orchestrator/src components/guardrails/src components/knowledgebase/kb-manager/kb_manager || true
                    python3 scripts/build_keep_graph.py || true
                '''
            }
        }

        stage('Build images') {
            steps {
                sh '''
                    set -e
                    test -f ${ENV_FILE} || cp deploy/compose/.env.example ${ENV_FILE}
                    export TAG=${TAG}
                    docker compose -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} --env-file ${ENV_FILE} build
                    docker tag rag-kb:local ${REGISTRY}rag-kb:${TAG} || true
                    docker tag rag-guardrails:local ${REGISTRY}rag-guardrails:${TAG} || true
                    docker tag rag-orchestrator:local ${REGISTRY}rag-orchestrator:${TAG} || true
                    docker tag rag-tracing:local ${REGISTRY}rag-tracing:${TAG} || true
                '''
            }
        }

        stage('Deploy stage') {
            when { branch 'develop' }
            steps {
                sh '''
                    set -e
                    docker compose -p dana-stage -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} -f ${COMPOSE_STAGE} --env-file ${ENV_FILE} up -d
                    sleep 20
                    for p in 18100 18200 18000 14000; do
                      curl -sf --max-time 5 http://127.0.0.1:$p/health || curl -sf --max-time 5 http://127.0.0.1:$p/health/liveliness || echo "port $p warming"
                    done
                '''
            }
        }

        stage('E2E stage') {
            when { branch 'develop' }
            steps {
                sh '''
                    set -e
                    curl -sf --max-time 30 http://127.0.0.1:18000/health | head -c 200; echo
                    curl -sf --max-time 60 http://127.0.0.1:18100/v1/chat/completions \
                      -H 'Content-Type: application/json' \
                      -d '{"model":"chat-primary","messages":[{"role":"user","content":"سلام"}]}' | head -c 400; echo
                '''
            }
        }

        stage('Deploy prod-sim') {
            when { branch 'main' }
            steps {
                input message: 'Deploy laptop prod-sim?', ok: 'Deploy'
                sh '''
                    set -e
                    docker compose -p dana-prod -f ${COMPOSE_BASE} -f ${COMPOSE_LOCAL} -f ${COMPOSE_PROD} --env-file ${ENV_FILE} up -d
                    sleep 20
                    for p in 8100 8200 8000 4000; do
                      curl -sf --max-time 5 http://127.0.0.1:$p/health || curl -sf --max-time 5 http://127.0.0.1:$p/health/liveliness || echo "port $p warming"
                    done
                '''
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
        }
        failure {
            echo 'Pipeline failed — inspect Jenkins console + docker compose logs'
        }
    }
}
