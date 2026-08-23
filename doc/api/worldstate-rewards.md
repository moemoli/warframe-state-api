# GET /api/worldstate/rewards —— 全部奖励聚合

> 分组：世界状态　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

把当前所有能领取的奖励聚合为一个清单：警报奖励、入侵攻守双方奖励等，回答"我现在上线能顺手拿什么"。

聚合 alerts/invasions/events/goals/sortie 的所有奖励：

```bash
curl "http://127.0.0.1:8099/api/worldstate/rewards?lang=zh"
```
```json
{ "rewards": [
  { "source": "alert:0", "rewards": [ { "type": "...", "item_count": 175, "item_name": "娜卡珍珠" } ] },
  { "source": "invasion:2:attacker", "rewards": [...] }
] }
```

---
