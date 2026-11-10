# Jenkins LTS with Docker CLI + Compose + Python for Dana CI agents.
FROM jenkins/jenkins:lts-jdk17
USER root
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 python3-pip \
 && curl -fsSL https://download.docker.com/linux/static/stable/$(uname -m)/docker-28.3.3.tgz \
      | tar -xz -C /tmp \
 && mv /tmp/docker/docker /usr/local/bin/docker \
 && mkdir -p /usr/local/lib/docker/cli-plugins \
 && curl -fsSL "https://github.com/docker/compose/releases/download/v2.39.2/docker-compose-linux-$(uname -m | sed 's/aarch64/aarch64/;s/x86_64/x86_64/')" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose \
 && chmod +x /usr/local/bin/docker /usr/local/lib/docker/cli-plugins/docker-compose \
 && rm -rf /var/lib/apt/lists/* /tmp/docker
USER jenkins
