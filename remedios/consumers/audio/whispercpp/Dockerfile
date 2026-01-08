FROM debian:bookworm-slim AS builder

ARG APP_SRC=remedios
ARG GO_VERSION=1.23.2
ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    build-essential \
    cmake \
    pkg-config \
    ffmpeg \
    libopenblas-dev \
    libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Go toolchain (match build architecture)
RUN if [ "${TARGETARCH}" = "amd64" ]; then GO_ARCH="amd64"; \
    elif [ "${TARGETARCH}" = "arm64" ]; then GO_ARCH="arm64"; \
    else echo "Arquitectura no soportada: ${TARGETARCH}" >&2; exit 1; fi \
 && curl -fsSL https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz -o /tmp/go.tgz \
 && tar -C /usr/local -xzf /tmp/go.tgz \
 && rm /tmp/go.tgz
ENV PATH="/usr/local/go/bin:${PATH}"

WORKDIR /app

# --- build whisper.cpp (shared lib) ---
RUN git clone --depth 1 --branch v1.8.2 https://github.com/ggerganov/whisper.cpp.git /tmp/whisper.cpp \
 && cd /tmp/whisper.cpp \
 && cmake -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_NATIVE=OFF \
      -DWHISPER_BUILD_SHARED_LIB=ON \
      -DWHISPER_BUILD_SERVER=OFF \
      -DWHISPER_BUILD_EXAMPLES=ON \
      -DGGML_OPENMP=ON \
      -DGGML_BLAS=ON \
      -DGGML_BLAS_VENDOR=OpenBLAS \
 && cmake --build build -j \
 && cmake --install build --prefix /usr/local \
 && ldconfig

# --- build Go consumer ---
COPY ${APP_SRC}/consumers/audio/whispercpp/go/ /app/whispercpp/
WORKDIR /app/whispercpp
RUN go mod tidy && go build -o /usr/local/bin/whispercpp-consumer .

# Final image
FROM debian:bookworm-slim
ARG APP_SRC=remedios
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    netcat-openbsd \
    libgomp1 \
    libopenblas0-openmp \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/whispercpp-consumer /usr/local/bin/whispercpp-consumer
COPY --from=builder /usr/local/lib/ /usr/local/lib/
COPY --from=builder /usr/local/include/ /usr/local/include/
COPY ${APP_SRC}/consumers/audio/whispercpp/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH:-}"

WORKDIR /app

# Arranca whisper-server y luego el consumer Go
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
