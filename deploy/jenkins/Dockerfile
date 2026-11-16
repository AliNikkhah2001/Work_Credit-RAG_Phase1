# Jenkins LTS with Docker CLI + Compose + Python for Dana CI agents.
# Behind Squid, pass proxy build-args:
#   docker build --build-arg HTTP_PROXY=http://192.168.203.2:3128 \
#     --build-arg HTTPS_PROXY=http://192.168.203.2:3128 \
#     -t dana-jenkins:lts -f deploy/jenkins/Dockerfile deploy/jenkins/
#
# To add CLI onto an *existing* plugin-rich prod image (no apt), use
# Dockerfile.docker-cli instead.
FROM jenkins/jenkins:lts-jdk17
USER root

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    no_proxy=${NO_PROXY}

ARG DOCKER_STATIC_VER=28.3.3
ARG COMPOSE_VER=v2.39.2

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 python3-pip \
 && arch="$(uname -m)" \
 && case "$arch" in x86_64|amd64) darch=x86_64; carch=x86_64 ;; aarch64|arm64) darch=aarch64; carch=aarch64 ;; *) exit 1 ;; esac \
 && curl -fsSL "https://download.docker.com/linux/static/stable/${darch}/docker-${DOCKER_STATIC_VER}.tgz" \
      | tar -xz -C /tmp \
 && mv /tmp/docker/docker /usr/local/bin/docker \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VER}/docker-compose-linux-${carch}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose \
 && chmod +x /usr/local/bin/docker /usr/local/lib/docker/cli-plugins/docker-compose \
 && rm -rf /var/lib/apt/lists/* /tmp/docker \
 && /usr/local/bin/docker version
USER jenkins
