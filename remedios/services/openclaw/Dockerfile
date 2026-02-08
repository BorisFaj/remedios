FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
  && rm -rf /var/lib/apt/lists/*

RUN npm i -g openclaw@2026.2.2-3 \
  && npm cache clean --force

RUN mkdir -p /home/ubuntu/.openclaw \
  && chown -R node:node /home/ubuntu

USER node
WORKDIR /home/ubuntu

ENV HOME=/home/ubuntu

ENTRYPOINT ["openclaw"]
CMD ["gateway"]
