# GET /api/wfm/components —— 杜卡德部件筛选

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**杜卡德（Ducats）垃圾分档**：多余的 Prime 部件可在中继站兑换为杜卡德金币，用于购买 Baro 限量商品。部件固定三档价值：金 100 / 银 45 / 铜 15，本端点按档位筛选部件清单。

| 参数 | 说明 |
|---|---|
| `tier` | `gold`(100) / `silver`(45) / `bronze`(15) / 缺省=全部部件 |
| `lang` / `limit` / `offset` | 常规 |

```bash
curl "http://127.0.0.1:8099/api/wfm/components?tier=gold&lang=zh&limit=5"
```
```json
{ "tier": "gold", "items": [
  { "slug": "corvas_prime_barrel", "item_name": "科瓦斯 Prime 枪管",
    "ducats": 100, "trading_tax": 2000 }
] }
```
