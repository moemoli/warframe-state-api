# GET /api/weapons/{name}/riven —— 紫卡倾向

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**紫卡倾向（Riven Disposition, omega_attenuation）**：DE 按武器使用率定期调整的平衡系数。倾向越高，该武器裂罅 MOD 的词条数值上限越高——决定一张紫卡是否值得洗。

```bash
curl "http://127.0.0.1:8099/api/weapons/斯特朗/riven?lang=zh"
```
```json
{ "weapon": "/Lotus/Weapons/Tenno/Shotgun/Shotgun",
  "name": "斯特朗",
  "omega_attenuation": 1.4,
  "prime_omega_attenuation": null }
```

---
