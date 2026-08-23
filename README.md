# warframe 数据工作区

| 文件 | 用途 |
|---|---|
| `init.sql` | **初始化数据库 SQL**：建 92 张表 + loc() 函数 + v_localized 视图 + languages 种子（幂等，可重复执行）。用法：`psql -U <user> -d <db> -f init.sql` |
| `load.py` | **数据导入脚本**：从 GitHub 拉取 warframe-public-export-plus 最新数据并生成 `import.sql`。用法：`python3 load.py --fetch --langs zh` |
| `import.sql` | **生成的数据导入 SQL**（每次生成都会先 TRUNCATE 清空全部表再全量写入，保证最新）。上传到服务器后：`psql -U <user> -d <db> -f import.sql` |
| `Cargo.toml` / `src/` | Rust（Axum + PostgreSQL）**API 服务**：WorldState 解析翻译 / 世界循环 / 节点 / 物品（简写）/ Mod / 武器（紫卡倾向）/ 掉落 |
| `doc/` | 设计（`design.md`）+ 实现（`implementation.md`）+ 调用（`api_usage.md`）文档 |

## API 服务

```bash
cd /root/warframe
cargo run --release        # 编译并启动（默认 0.0.0.0:8080，连本地 warframe 库）
# 配置: BIND_ADDR / DATABASE_URL / DEFAULT_LANG / WORLDSTATE_CACHE_TTL / ALIAS_API_KEY 等（见 doc/api_usage.md §15）

curl localhost:8080/health
curl "localhost:8080/api/worldstate?sections=alerts,fissures,cycles"
curl "localhost:8080/api/cycles"
curl "localhost:8080/api/nodes/SolNode94"
curl "localhost:8080/api/items/血妈"
curl "localhost:8080/api/weapons/斯特朗/riven"
```

端点清单与响应示例见 **`doc/api_usage.md`**（调用文档，供其他程序参考）。

## 使用流程

```bash
# 1) 本地生成最新数据导入 SQL（临时文件在 temp/，导入后自动清理）
python3 load.py --fetch --langs zh        # 默认只带 zh 字典；--langs zh,en 可多语言
#   可选: --force-fetch 强制全量重下 / --keep-data 保留下载缓存 / --out 指定输出路径

# 2) 上传到服务器（只需 psql，无需 Python/网络）
scp import.sql server:/tmp/
psql -U warframe -d warframe -f /tmp/import.sql

# 3) 新服务器初始化：先建库建表，再导数据
psql -U postgres -c "CREATE ROLE warframe LOGIN PASSWORD 'warframe123';"
psql -U postgres -c "CREATE DATABASE warframe OWNER warframe;"
psql -U warframe -d warframe -f init.sql
psql -U warframe -d warframe -f import.sql
```

## 说明

- **清理机制**：`import.sql` 开头 `TRUNCATE TABLE ... CASCADE` 清空全部 92 张表，因此每次导入都是全量最新数据（幂等、无残留）。
- **枚举映射**：`worldstate_enums` 表收录 `ExportFactions`/`ExportMissionTypes`（FC_*/MT_* → loc tag），用于解析官方 WorldState 的枚举字段（如 `MT_SURVIVAL` → 中文"生存"）。
- **数据源**：calamity-inc/warframe-public-export-plus master 分支（默认走 ghproxy 代理，`GH_MIRROR` 可覆盖；`ExportMisc.json` 上游已移除，自动跳过）。
- 上游新增的 ExportAnimals/Boosters/Bounties/Challenges/Codex 等 11 个导出暂未建表，属后续扩展。
