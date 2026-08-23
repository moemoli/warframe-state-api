# GET /api/items/{name}/drops —— 物品掉落/来源聚合

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**刷材料反查工具**：输入一件物品（如 Forma、某 Prime 部件），返回它的全部获取途径——出现在哪些任务奖励表、哪些敌人会掉落、作为哪些蓝图的原料/产物、被哪些组合包包含。

反查 4 类来源：任务奖励表、敌人掉落表、配方（原料/产物）、组合包。

```bash
curl "http://127.0.0.1:8099/api/items/Forma/drops?lang=zh"
```
```json
{ "item": { "type": "/Lotus/Types/Items/MiscItems/Forma", "name": "Forma" },
  "drops": [
    { "source_type": "mission_reward", "source": "...", "chance": 0.025, "item_count": 3 }
  ] }
```

---
