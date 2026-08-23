# GET /api/wfm/rivens/attributes —— 紫卡词条列表

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**裂罅 MOD 词条全集**：每张紫卡由随机词条构成，本表列出全部 32 种词条的效果名、生成紫卡名称用的前缀/后缀音节（如 Visi-Tox）与适用武器类别。

```bash
curl "http://127.0.0.1:8099/api/wfm/rivens/attributes?lang=zh"
```
```json
{ "attributes": [ {
    "slug": "toxin",
    "prefix": "Visi",
    "suffix": "Tox",
    "units": "percent",
    "group": "default",
    "exclusive_to": [],
    "effect": "毒素伤害"
} ], "total": 32 }
```
