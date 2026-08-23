# GET /api/weapons/{name} —— 武器详情

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

单把武器深度面板：暴击率/暴击倍率/触发几率/射速/弹匣/装填，**每一发伤害的物理与元素分量**，以及射击行为（连发/蓄力）与兼容标签——配装计算的基础数据。

按 unique_name 或名称精确匹配；含面板数据/伤害分量/行为伤害表/兼容标签。

```bash
curl "http://127.0.0.1:8099/api/weapons/斯特朗?lang=zh"
```
```json
{
  "unique_name": "/Lotus/Weapons/Tenno/Shotgun/Shotgun",
  "name": "斯特朗", "total_damage": 25.0,
  "critical_chance": 0.11, "fire_rate": 2.9,
  "damage_per_shot": [ { "slot": 0, "value": 6.0 } ],
  "behaviours": [ { "slot": 0, "state_name": "...",
    "damage": { "impact": { "DT_IMPACT": 6.0 } } } ],
  "compatibility_tags": ["PROJECTILE", "SHOTGUN"]
}
```
