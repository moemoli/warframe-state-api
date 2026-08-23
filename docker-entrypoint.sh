#!/bin/bash
set -e

# ============================================================
# warframe-api Docker 入口脚本
# ============================================================
# 用法：
#   docker run warframe-api serve          # 启动 API 服务（默认）
#   docker run warframe-api init-db        # 初始化数据库（建表+导入数据）
#   docker run warframe-api fetch-data     # 仅拉取最新数据生成 import.sql
#   docker run warframe-api import-sql     # 仅执行 import.sql 导入数据
#   docker run warframe-api health         # 健康检查
# ============================================================

CMD="${1:-serve}"

# 从 DATABASE_URL 提取连接信息
parse_db() {
  DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
  DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
  DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')
  DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
  DB_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
  export PGPASSWORD="$DB_PASS"
}

case "$CMD" in
  serve)
    echo "[entrypoint] 启动 warframe-api ..."
    echo "[entrypoint] DATABASE_URL=${DATABASE_URL%@*}@***"
    echo "[entrypoint] BIND_ADDR=${BIND_ADDR}"
    exec warframe-api
    ;;

  init-db)
    echo "[entrypoint] 初始化数据库 ..."
    parse_db

    echo "[entrypoint] 等待数据库就绪 ..."
    for i in $(seq 1 30); do
      if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        echo "[entrypoint] 数据库就绪"
        break
      fi
      echo "[entrypoint] 等待中 ($i/30) ..."
      sleep 2
    done

    echo "[entrypoint] 执行 sql/init.sql（建表） ..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f sql/init.sql

    echo "[entrypoint] 拉取最新数据并生成 sql/import.sql ..."
    python3 scripts/load.py --langs "${DEFAULT_LANG:-zh}" --fetch --out sql/import.sql

    echo "[entrypoint] 执行 sql/import.sql（导入数据） ..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f sql/import.sql

    echo "[entrypoint] 数据库初始化完成 ✓"
    ;;

  fetch-data)
    echo "[entrypoint] 拉取最新数据生成 sql/import.sql ..."
    python3 scripts/load.py --langs "${DEFAULT_LANG:-zh}" --fetch --out sql/import.sql
    echo "[entrypoint] sql/import.sql 已生成 ✓"
    ;;

  import-sql)
    parse_db
    echo "[entrypoint] 执行 sql/import.sql ..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f sql/import.sql
    echo "[entrypoint] 导入完成 ✓"
    ;;

  health)
    curl -sf "http://localhost:${BIND_ADDR##*:}/health" || exit 1
    ;;

  *)
    echo "[entrypoint] 未知命令: $CMD"
    echo "可用命令: serve | init-db | fetch-data | import-sql | health"
    exit 1
    ;;
esac
