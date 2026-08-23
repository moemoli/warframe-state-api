# ============================================================
# warframe-api Dockerfile（多阶段构建）
# ============================================================
# 构建：docker build -t warframe-api .
# 运行：docker run -p 8099:8099 --env-file .env warframe-api
# 初始化数据库：docker run --rm --env-file .env warframe-api init-db
# ============================================================

# ---- Stage 1: 构建 Rust 二进制 ----
FROM rust:1.82-bookworm AS builder

WORKDIR /app
COPY Cargo.toml Cargo.lock* ./
COPY src/ src/

# sqlx 离线模式（不需要编译期连库）
ENV SQLX_OFFLINE=true

RUN cargo build --release && strip target/release/warframe-api

# ---- Stage 2: 运行时 ----
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-pip \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制编译产物
COPY --from=builder /app/target/release/warframe-api /usr/local/bin/warframe-api

# 复制数据库初始化文件
COPY sql/ sql/
COPY scripts/ scripts/
COPY doc/ doc/

# 入口脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# 默认环境变量
ENV DATABASE_URL=postgres://warframe:warframe123@db:5432/warframe \
    BIND_ADDR=0.0.0.0:8099 \
    DEFAULT_LANG=zh \
    WORLDSTATE_URL=https://api.warframe.com/cdn/worldState.php \
    WORLDSTATE_CACHE_TTL=180 \
    WORLDSTATE_MIN_INTERVAL=30

EXPOSE 8099

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["serve"]
