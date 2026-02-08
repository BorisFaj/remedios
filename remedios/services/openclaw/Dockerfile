FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
  && rm -rf /var/lib/apt/lists/*

RUN npm i -g openclaw@2026.2.2-3 \
  && npm cache clean --force

USER node
WORKDIR /home/node

ENV HOME=/home/node

ENTRYPOINT ["openclaw"]
CMD ["gateway"]
