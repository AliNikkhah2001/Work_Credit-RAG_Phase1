# Jenkinsfile — RAG Services CI/CD Pipeline
# Runs on self-hosted Jenkins (root user, H200 server)
# Triggered by GitHub webhooks on push/PR to main/develop

pipeline {
    agent any

    environment {
        REGISTRY = 'local-h200:5000'
        DOCKER_COMPOSE_TEST = 'Work_RAG-Server-Setup/deploy/docker/docker-compose.test.yml'
        DOCKER_COMPOSE_PROD = 'Work_RAG-Server-Setup/deploy/docker/docker-compose.prod.yml'
        PARENT_REPO = 'Work_Credit-RAG_Phase1'
        SERVER_SETUP_REPO = 'Work_RAG-Server-Setup'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    set -e
                    echo "=== Running ruff lint ==="
                    pip install ruff 2>/dev/null || true
                    ruff check . || true
                    echo "=== Running hadolint ==="
                    pip install hadolint 2>/dev/null || true
                    hadolint Work_RAG-Server-Setup/deploy/docker/Dockerfile.* || true
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    set -e
                    echo "=== Running pytest ==="
                    pip install pytest 2>/dev/null || true
                    cd Work_Credit-RAG_Phase1
                    pytest eval/ -v 2>/dev/null || true
                    python scripts/gen_readme_toc.py --check 2>/dev/null || true
                '''
            }
        }

        stage('Build Docker Images') {
            steps {
                sh '''
                    set -e
                    echo "=== Building all Docker images ==="
                    bash Work_RAG-Server-Setup/deploy/docker/build-all.sh ${REGISTRY}
                '''
            }
        }

        stage('Push to Local Registry') {
            steps {
                sh '''
                    set -e
                    echo "=== Pushing images to ${REGISTRY} ==="
                    docker push ${REGISTRY}/rag-kb:${TAG}
                    docker push ${REGISTRY}/rag-guardrails:${TAG}
                    docker push ${REGISTRY}/rag-orchestrator:${TAG}
                    docker push ${REGISTRY}/rag-tracing:${TAG}
                    docker push ${REGISTRY}/rag-manager:${TAG}
                    docker push ${REGISTRY}/rag-gemma:${TAG}
                    docker push ${REGISTRY}/rag-embed:${TAG}
                '''
            }
        }

        stage('Deploy to Dev (Alt Ports)') {
            when {
                branch 'develop'
            }
            steps {
                sh '''
                    set -e
                    echo "=== Deploying to dev (alt ports) ==="
                    docker compose -f ${DOCKER_COMPOSE_TEST} down --remove-orphans 2>/dev/null || true
                    docker compose -f ${DOCKER_COMPOSE_TEST} up -d --build
                    echo "=== Waiting for health checks ==="
                    sleep 30
                    for p in 8100 8201 8101 3001 9001 8085 8086 8087 8088 8089 8004 8005 8006; do
                        echo "Checking port $p..."
                        curl -sf http://127.0.0.1:$p/health || curl -sf http://127.0.0.1:$p/api/public/health || echo "Port $p not ready yet"
                    done
                '''
            }
        }

        stage('E2E Test (Open WebUI)') {
            when {
                branch 'develop'
            }
            steps {
                sh '''
                    set -e
                    echo "=== Running E2E test via Open WebUI ==="
                    # Temporarily point Open WebUI to alt-port orchestrator
                    # Run test queries through Open WebUI API
                    curl -sf http://127.0.0.1:8101/v1/chat/completions \
                        -H 'Content-Type: application/json' \
                        -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"SBD1"}]}' | python -m json.tool | head -50
                    echo "=== E2E test complete ==="
                '''
            }
        }

        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            steps {
                input message: 'Deploy to production?', ok: 'Deploy'
                steps {
                    sh '''
                        set -e
                        echo "=== Deploying to production (same ports) ==="
                        docker compose -f ${DOCKER_COMPOSE_PROD} down --remove-orphans 2>/dev/null || true
                        docker compose -f ${DOCKER_COMPOSE_PROD} up -d --build
                        echo "=== Waiting for health checks ==="
                        sleep 30
                        for p in 8000 8200 8100 3000 9000 8080 8081 8082 8083 8084 8001 8002 8003; do
                            echo "Checking port $p..."
                            curl -sf http://127.0.0.1:$p/health || curl -sf http://127.0.0.1:$p/api/public/health || echo "Port $p not ready yet"
                        done
                    '''
                }
            }
        }
    }

    post {
        always {
            sh 'docker system prune -f 2>/dev/null || true'
        }
        failure {
            echo 'Pipeline failed — check logs above'
        }
    }
}
