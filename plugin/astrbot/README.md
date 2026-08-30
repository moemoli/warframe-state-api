# astrbot_plugin_warframe_helper

AstrBot 星际战甲（Warframe）查询助手插件，对接 [warframe-api](../../) REST 服务。

## 功能

- **世界状态**：警报 / 突击 / 执刑官猎杀 / 入侵 / 虚空裂缝(普通) / 钢铁裂缝 / 虚空风暴(九重天) /
  奸商 / Darvo 特惠 / 午夜电波 / 新闻 / 活动 / 沉沦之地 21 层 / 1999日历 / 小小黑
- **循环**：地球平原、金星山谷、火卫二 Fass/Vome、扎里曼、双衍王境（本地推算）
- **仲裁**：当前进行中 + 未来排程（每小时轮换）
- **资料**：统一搜索（116 条中文简称：血妈→Garuda…）、掉落反查、Wiki 链接、节点详情
- **市场**：WM 实时价格、紫卡拍卖全语法筛选（词条/洗数/价格/极性）、词条价差、
  价格趋势（48h/90d 真实成交）、杜卡德垃圾分档、赤毒/信条武器库
- **订阅**：`蹲钢月`、`蹲赛中`、`蹲三傻`、`蹲奸商` 等口语简称 → 命中主动推送
- **LLM Tools**：接入大模型后可自然语言问答（自动调用搜索/查价/世界摘要）

所有结果默认渲染为图片卡片；追加 `-1` 强制纯文本，`-en` 英文，`-数字` 翻页。

## 安装

1. 部署 warframe-api（见仓库根 README），确认 `GET /health` 通；
2. AstrBot WebUI → 插件 → 从本地上传 `dist/astrbot_plugin_warframe_helper.zip`
   （或解压到 `data/plugins/astrbot_plugin_warframe_helper/`）；
3. 插件配置里填 warframe-api 地址（默认 `http://127.0.0.1:8099`）。

发 `帮助` 查看全部指令。

## 开发

```bash
# 打包（在 warframe-api 仓库根目录）
cargo plugin-pack          # 产出 dist/*.zip

# 本地调试
git clone --depth 1 https://github.com/AstrBotDevs/AstrBot temp/AstrBot
mkdir -p temp/AstrBot/data/plugins
ln -sfn "$(pwd)/plugin/astrbot" "$(pwd)/temp/AstrBot/data/plugins/astrbot_plugin_warframe_helper"
```

实现细节：[doc/plugin_implementation.md](../doc/plugin_implementation.md)
API 契约：[doc/api/README.md](../doc/api/README.md)
