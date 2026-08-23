# POST /api/aliases —— 别名提交（受 API Key 保护）

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

社区昵称映射表的维护接口（如新增 "血妈→Garuda"）。需要 API Key 鉴权，供运营者补充玩家惯用语。

- 请求头 `X-API-Key`（值 = 环境变量 `ALIAS_API_KEY`）；未携带/错误 → 401；未配置 → 503
- 批量 upsert（幂等）

```bash
curl -X POST "http://127.0.0.1:8099/api/aliases" \
  -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  -d '{"aliases":[{"alias":"血妈","entity_type":"warframes","entity_id":"/Lotus/Powersuits/Garuda/Garuda"}]}'
```
```json
{ "inserted": 1 }
```

---
