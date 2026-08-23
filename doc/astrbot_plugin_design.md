# astrbot_plugin_warframe_helper 设计文档

> 版本 v0.2 · 对接 warframe-api（本项目 REST 服务）
> 参考：`doc/api_usage.md`、[AstrBot 插件开发指南](https://docs.astrbot.app/dev/star/guides/simple.html)、
> 《Warframe Rabbit(因幡帝)机器人4.0版使用说明》（指令形态参照，功能以本 API 能力为准）

---

## 1. 定位与目标

为 AstrBot（v4.x）提供星际战甲（国际服）游戏数据查询插件，作为 **warframe-api 的聊天前端**：

- 插件只做 **HTTP 调用 + HTML 渲染排版**，翻译/数据/缓存全部由 warframe-api 完成；
- **每个指令的结果默认渲染成图片输出**（HTML 模板 → 截图），`-1` 参数强制纯文本；
- 指令形态向"因幡帝"看齐（中文短指令 + 内容 + 附加参数），降低 Warframe 玩家迁移成本；
- **国服相关功能本期留空**：玩家使用对应指令时统一回复「暂不支持」；
- 同时注册 **LLM Tool**，让接入大模型的 AstrBot 能用自然语言自动调用查询。

非目标：签到/娱乐小游戏、跨群组队、账号绑定、VIP 体系（详见 §6 清单）。

---

## 2. 总体架构

```
QQ/TG/Discord...
      │ (消息)
      ▼
┌────────────────────────┐     HTTP      ┌──────────────────┐
│ astrbot_plugin_         │ ────────────▶ │ warframe-api     │
│ warframe_helper         │ ◀──────────── │ (Axum :8099)     │
│  · 指令解析/参数校验      │     JSON      │  · worldstate    │
│  · formatter 裁剪数据    │               │  · search        │
│  · Jinja2 模板渲染       │               │  · wfm/arbitrations│
│  · 订阅轮询任务          │               │  · PostgreSQL    │
└────────────────────────┘               └──────────────────┘
      │ html_render → image_url
      ▼
   图片消息回复（降级：纯文本）
```

| 层 | 职责 | 说明 |
|---|---|---|
| 指令层 | `@filter.command` 注册中文指令 + `/wf` 指令组别名 | 解析内容与附加参数 |
| 服务层 | `aiohttp.ClientSession` 封装 GET，超时/重试/错误映射 | 单例 session，`terminate()` 时关闭 |
| 渲染层 | **每个指令结果先经 HTML 模板渲染成图片输出** | 见 §7.5；`-1` 或渲染失败时降级纯文本 |
| 订阅层 | 简称解析 + 后台轮询任务（asyncio Task）+ 命中推送 | 见 §5.3；推送同样走图片卡片 |
| 工具层 | `@filter.llm_tool` 暴露 3 个工具供 LLM 调用 | 见 §8；LLM 返回走纯文本（不渲染） |

---

## 3. 插件配置

`_conf_schema.json`（AstrBot WebUI 可视化配置）：

```json
{
  "api_base":     { "description": "warframe-api 地址", "type": "string", "default": "http://127.0.0.1:8099" },
  "lang":         { "description": "返回语言", "type": "string", "default": "zh" },
  "timeout":      { "description": "请求超时秒数", "type": "int", "default": 15 },
  "max_lines":    { "description": "文本模式单条回复最大行数", "type": "int", "default": 40 },
  "render_mode":  { "description": "输出方式 auto/image/text", "type": "string", "default": "auto" },
  "t2i_endpoint": { "description": "自建 text2img 端点（留空用 AstrBot 官方）", "type": "string", "default": "" }
}
```

读取方式：`self.config`（AstrBotConfig 字典）。热更新无需重启。

---

## 4. 通用附加参数

沿用兔子的使用习惯，位置随意、可叠加：

| 参数 | 行为 |
|---|---|
| `-en` | 本次以英文返回（`lang=en` 覆盖默认 zh） |
| `-1` / `-w` | **强制纯文本输出**（跳过 HTML 渲染，便于复制粘贴） |
| `-t` | 强制图片输出（默认行为；渲染失败时带此参数会重试一次而非静默降级文本） |
| `-数字` | 翻页（对支持分页的指令生效，见各节"分页"标注） |
| `-pc/-ps/-xb/-sw` | 平台标记。**仅接受不报错**（本 API 数据全平台一致），解析后忽略 |
| `-cn` | 国服。**回复「暂不支持国服查询」并终止** |

参数解析器：一个公共 `_parse(text) -> (content, flags)`，所有指令复用。

---

## 5. 指令清单

### 5.1 世界状态与周期

| 主指令 | 别名 | 上游端点 | 输出要点 | 分页 |
|---|---|---|---|---|
| `夜灵` `平原时间` `循环` | — | `GET /api/cycles` | 地球/夜灵平原/金星/双衍/扎里曼 当前状态+剩余时间，卡片式 | ✗ |
| `警报` | — | `/api/worldstate?sections=alerts` | 节点·类型·派系·等级·奖励（每条一张小卡） | ✓ |
| `突击` | — | `sections=sortie` | Boss + 三段任务（类型/修正/节点）+ 奖励概览 | ✗ |
| `猎杀` `执刑官` | — | `sections=liteSorties`（透传已翻译） | 同突击格式 | ✗ |
| `入侵` | — | `sections=invasions` | 进攻方 vs 防守方、进度条、双方奖励 | ✓ |
| `裂隙` `裂缝` | `钢铁裂隙`(过滤 hard=true) | `sections=fissures` | 遗物纪元徽章·星球·类型·剩余时间 | ✓ |
| `奸商` | — | `sections=void_trader` | 到达/离开倒计时 + 商品网格（ducats+星币） | ✓ |
| `特惠` `每日特惠` | — | `sections=daily_deals` | Darvo 折扣品：原价/现价/折扣/库存 | ✗ |
| `电波` | — | `sections=nightwave` | 赛季 + 每日/每周/精英挑战列表 | ✓ |
| `新闻` `最近新闻` | — | `sections=events` | 已按语言筛选的新闻标题+时间 | ✓ |
| `仲裁` `仲裁表` | — | `GET /api/arbitrations` | latest 大卡 + schedule 时间线 | ✓ |
| `恶魔塔` `沉沦之地` | — | `sections=descents` | 21 层挑战：type_name/challenge_name/level_name | ✓ |
| `日历` `1999日历` | — | `sections=knownCalendarSeasons` | 当季 + 近期事件（CET_* 已译） | ✓ |
| `活动` | — | `sections=goals` | 进行中活动名称/描述/起止时间 | ✓ |
| `帮助 [指令]` | — | 本地静态模板 | 无参=总目录；带参=单指令详细用法 | ✗ |

### 5.2 资料、掉落与市场

| 主指令 | 格式 | 上游端点 | 输出要点 |
|---|---|---|---|
| `查 <关键词>` | `查 血妈` | `GET /api/search?q=&trade=` | 来源 `[alias/official/wfm/riven/lich/sister]` 徽章 + 名称 + slug + **wiki 链接按钮**；`可交易` 参数过滤 |
| `wiki <名>` | `wiki 绝路` | 复用 `/api/search?q=` | 取首个含 `wiki_link` 的结果，回复名称 + Wiki 链接（链接随 lang 自动切换 huiji/wiki.warframe.com/fandom） |
| `掉落 <物品>` | `掉落 Forma` | `GET /api/items/{name}/drops` | 按 source_type 分组列出来源与概率 |
| `wm <物品名>` | `wm 绝路` | search 解析 slug → `GET /api/wfm/items/{slug}` | 卖一/卖均/收一对比卡 + 前 3 单（价格·数量·状态）；未带 slug 先搜索取第一条 |
| `wr` = `wmr` = `wk` <武器名> | `wr 绝路` | `GET /api/wfm/rivens?name=` | 三指令**完全等价**（兼容兔子用户肌肉记忆）：倾向值环形图·类型·段位·wiki 链接 |
| `词条` | `词条` | `GET /api/wfm/rivens/attributes` | 全部 32 条：中文名 + 前缀/后缀 + 适用类型 |
| `玄骸` | `玄骸 努寇` | `GET /api/wfm/liches?name=` | 赤毒武器列表/详情（名称·段位·wiki） |
| `信条` | `信条 典客` | `GET /api/wfm/sisters?name=` | 姐妹武器列表/详情 |
| `倾向 <武器>` | `倾向 斯特朗` | `GET /api/weapons/{name}/riven` | 官方 omega_attenuation |

### 5.3 订阅推送（蹲）

「蹲」= 条件订阅，命中后主动推送该会话。核心是把玩家口语简称**解析为结构化订阅条件**，
由后台轮询任务定期比对 worldstate/cycles。

#### 5.3.1 指令格式

```
蹲 <简称|完整条件> [规则] [时长]
蹲 列表                      # 查看本会话全部订阅
蹲 <序号> 取消               # 取消单条
蹲 取消                      # 清空本会话订阅
```

时长缺省 = 命中一次自动取消；支持 `7天 / 两周 / 长期 / 永久 / 数字+h/d/w/m`。

#### 5.3.2 简称解析词典（内置，可扩展）

| 用户输入 | 解析结果 |
|---|---|
| `蹲钢月` | `{kind: fissure, hard: true, system: 月球, mission: 生存}` |
| `蹲赛中` | `{kind: fissure, system: 赛德娜, mission: 中断}` |
| `蹲三傻` | `{kind: cycle, cycle: cetus, state: night}` |
| `蹲奸商` | `{kind: void_trader}` （Baro 到达时提醒） |
| `蹲夜灵` | `{kind: cycle, cycle: cetus, state: night}` 同三傻 |
| `蹲普通捕获` | `{kind: fissure, mission: 捕获}` （不带 hard → 普通+钢铁都推） |

组合语法同样支持：`蹲 钢铁 虚空 生存`、`蹲 普通捕获,钢铁虚空生存`（逗号分隔多条）。

词典结构：`{关键词: (维度, 标准值)}`，维度 ∈ {system, mission, tier, kind, state}；
解析器把输入切词后逐词归一化，未识别词原样报错提示。

#### 5.3.3 匹配引擎

| kind | 数据源 | 轮询间隔 | 命中条件 |
|---|---|---|---|
| `fissure` | `/api/worldstate?sections=fissures` | 60s | 条目的星球/任务类型/钢铁标记与订阅条件一致 |
| `cycle` | `/api/cycles?name=` | 30s | 对应循环 `state` 变为目标状态（边沿触发，仅切换瞬间推一次） |
| `void_trader` | `sections=void_trader` | 300s | activation 已过且 expiry 未过（到达边沿触发） |

- 推送去重：以条目 id / 循环切换时间戳记录已推送集合
- 一次轮询合并所有同 kind 订阅（单次 API 调用服务 N 个订阅者）
- 存储使用 AstrBot 插件存储 API（SQLite），重启不丢

#### 5.3.4 输出样式（subscribe_hit 卡片）

```
🔔 订阅命中【钢月】
[前纪 · 生存] 月球 · Copernicus · 剩余 42 分钟
（发送『蹲 取消』可清空订阅）
```

### 5.4 国服指令（本期占位）

| 指令 | 回复 |
|---|---|
| `cm <...>` / `cr <...>` / `rm <...>` / `交易 <...>` | 「暂不支持国服市场查询」 |
| 任意指令带 `-cn` | 「暂不支持国服数据」 |

实现上集中在一个 `_CN_UNSUPPORTED` 常量表 + 入口拦截，后续接国服数据源时只需替换处理函数。
`.默认平台` 类群管理指令不提供；平台参数整体忽略。

---

## 6. 暂不支持功能清单（后期扩展对照）

> 以下指令当前**不做**，统一回复「该功能暂不支持，可用指令见『帮助』」——避免静默无响应。
> 实现集中于 `_UNSUPPORTED_COMMANDS` 常量表；任一功能落地后从此表移除并补入 §5。

### 6.1 资料与攻略类

| 指令 | 兔子功能 | 缺口 | 后期可行路径 |
|---|---|---|---|
| `物品 <名>` / `萌新` | 物品用途说明文案 | 无长描述语料 | wfm i18n.description + 后续接 wiki API |
| `配卡 <名>` | 分流派配卡推荐 | 无攻略数据源 | 接 Overframe/Divek 数据或 LLM 生成 |
| `伤害模拟` | 文字版幻影装置 DPS 计算 | 无计算引擎 | 纯客户端实现，工作量大 |
| `结合目标` | 结合仪式目标地点 | 无数据源 | 官方 worldstate 无此节，需社区数据 |
| `合成 / 铸造查询` | 蓝图材料/铸造信息 | **已有 recipes 表** | 可做：drops 端点已含配方；补独立排版即可 |
| `浮印 <名>` | 浮印代码查询 | 无浮印库 | ExportCustoms 有数据可扩展端点 |
| `三线琴 / 和弦琴` | 曲谱搜索试听 | 无曲谱库 | 需外部曲谱数据源 |
| `教程 <关键词>` | B 站搜索 | 外部依赖 | 调 B 站搜索接口 |
| `在线翻译 / 中翻英` | 日常句子翻译 | 非 API 职责 | 建议 LLM 会话直接完成 |

### 6.2 市场进阶类

| 指令 | 兔子功能 | 缺口 | 后期可行路径 |
|---|---|---|---|
| `wr <武器> <词条筛选>` 全语法 | 词条/洗数/价格/极性槽过滤紫卡拍卖 | wfm 拍卖 API 未接入 | 接 `/v2/riven/auctions`（wfm 拍卖端点） |
| `rm <...>` | Riven.Market 挂单 | 第三方站无公开 v2 API | 单独适配器 |
| `紫卡分析 <截图>` | OCR + 数值/价格评估 | OCR + 估价模型 | 文字识别 + 词条价差表 |
| `模拟开卡` | 娱乐随机开紫卡 | — | 纯本地随机，工作量小，可提前 |
| `wm趋势 / 紫卡趋势` | 价格走势图 | 无历史价存储 | 自建每日快照表，积累后绘图 |
| `紫卡词条价差` | 哪个词条更值钱 | 同上需历史数据 | 快照表聚合 |
| `紫卡价格 / 官方周报` | DE 官方成交报告 | 无数据源 | DE 论坛/社区抓取 |
| `热门紫卡` | 按热度排序 | 无拍卖数据 | wr 拍卖接入后顺带 |
| `部件 / 金垃圾 / 银垃圾 / 铜垃圾` | 杜卡德性价比筛选 | **已有 ducats 数据** | 可做：wfm_items 按 ducats/tax 查询，补端点+排版 |
| `排行 / 甲排行 / 卡排行 ...` | 市场热门排行 | 无成交量数据 | wfm statistics 端点或自建快照 |

### 6.3 图片识别与娱乐类

| 指令 | 兔子功能 | 缺口 |
|---|---|---|
| `文字识别` | OCR 提取文字 | 需 OCR 引擎 |
| `截图翻译` | 截图+翻译 | OCR + 翻译 |
| `批量查价 <截图>` | 识别多物品查价 | OCR + search |
| `核桃 / 查价 <截图>` | 开遗物奖励识别查价 | OCR |
| `黄历 / 签到 / 打卡` | 群娱乐 | 与查询定位无关，不建议做 |
| `抽奖 / 射爆` | 小游戏 | 同上 |

### 6.4 社交与管理类

| 指令 | 兔子功能 | 说明 |
|---|---|---|
| `组队 类型 人数 时长` | 跨群组队 | 需跨会话状态服务，超出插件职责 |
| `兔 <聊天>` | LLM 陪聊 | AstrBot 本体 LLM 会话已覆盖 |
| `.状态 / .授权 / .绑定 / .赞助 ...` | VIP/萝卜体系 | 商业功能，不复制 |
| `.默认平台 pc/ps/xb/sw` | 群平台切换 | 本 API 数据全平台一致，无意义 |
| `蹲 <推送时间> @全体` 等 | 定时推送窗口/@全体 | 订阅 M5 先做基础命中推送，窗口化推送后期评估 |

> 以上任一指令后续落地时：在 §5 对应小节补充正式定义，并从此表移除。

---

## 7. 关键流程设计

### 7.1 指令分发

```
event.message_str
   ├─ flags 解析（-cn 拦截 / -en / -1 / 分页 / 平台忽略）
   ├─ 主指令表 COMMANDS: dict[str, handler]  （含全部中文别名）
   ├─ 未命中 → 是否 @机器人/私聊？→ LLM 流程（若启用）
   └─ 命中 → handler(api, content, flags)
              ├─ 取数 → formatter 裁剪 view-model
              ├─ render_mode != text → html_render → image_result
              └─ 降级/`-1` → 文本排版 → plain_result
```

- 用 `@filter.command("警报")` 等逐一注册；同一 handler 多别名的用 `alias={"..."}` 
- 另注册 `@filter.command_group("wf")` 提供 `/wf 警报` 入口（防与其他机器人撞词）

### 7.2 API 访问封装

```python
class ApiClient:
    def __init__(self, base, timeout): ...
    async def get(self, path, **params) -> dict      # 2xx→json; 其他→ApiError(msg)
    async def close(self)
```

- 错误映射：上游 `{"error": "..."}` 或非 200 → 统一「查询失败：{原因}」，不打堆栈到群里
- 超时/连接失败 → 「warframe-api 服务不可达，请稍后再试」

### 7.3 文本排版规范（`-1` 模式与降级输出）

- 标题行：`【警报】`/`【突击】`…；空行分隔条目
- 时间一律显示相对时间（"3小时后结束"，由 ISO 字符串换算）
- 超过 `max_lines`：截断 + `……共 N 条，发送『指令 -2』翻页`
- `-1` 精简模式：去标题/装饰，仅保留数据行

### 7.4 翻页

内存 LRU 缓存 `(session_id, command_key) -> 分页数据列表`，容量 128 条、TTL 5 分钟。
`-N` 直接取第 N 页，不重新请求上游。**缓存的是结构化数据**（view-model dict），
渲染时再套模板——同一份缓存既能出图片也能出文本。

### 7.5 渲染系统（图片输出，主路径）

**所有指令结果默认渲染为图片发送**。已核实 AstrBot v4.x 渲染机制（源码 `astrbot/core/star/base.py` L92）：

- `Star.html_render(tmpl: str, data: dict, return_url=True, options=None)`：
  接收 **Jinja2 模板字符串 + 数据字典**，返回图片 URL（或本地路径）
- 引擎两种策略（`astrbot/core/utils/t2i/`）：
  - **NetworkRenderStrategy**（自定义 HTML 模板唯一可用路径）：POST 模板+数据到
    text2img 端点（官方端点自动获取，或 WebUI 配置自建 chromium endpoint），
    默认 `full_page=True, type=jpeg, quality=40`
  - LocalRenderStrategy：仅支持 Markdown→PIL 文本转图，**不支持自定义模板**
    （`render_custom_template` 抛 NotImplementedError）
- 发送：`yield event.image_result(url_or_path)`

#### 7.5.1 模板体系

```
plugin/astrbot/templates/
├── base.html            # 公共骨架：<head> 样式 + 标题栏 + 内容块 + 页脚
├── components/
│   ├── reward_row.html  # 奖励条目宏
│   ├── countdown.html   # 倒计时徽章宏
│   └── progress.html    # 进度条宏（入侵）
├── alerts.html          # extends base
├── sortie.html
├── lite_sorties.html
├── fissures.html        # 表格式：纪元徽章 | 星球 | 类型 | 剩余
├── cycles.html          # 卡片式：每个循环一张卡
├── arbitrations.html    # latest 大卡 + schedule 时间线
├── invasions.html
├── voidtrader.html      # 商品网格（ducats+星币）
├── daily_deals.html
├── nightwave.html
├── news.html
├── goals.html
├── descents.html        # 21 层挑战列表
├── calendar.html        # 1999 日历
├── search.html          # 列表 + 来源徽章 + wiki 链接按钮
├── drops.html
├── wfm_price.html       # 卖/收对比 + 订单表
├── riven.html           # 倾向值环形图（CSS conic-gradient）
├── lich_sister.html     # 赤毒/姐妹共用
├── help.html            # 指令目录
└── subscribe_hit.html   # 订阅命中推送卡
```

- 模板用 **Jinja2 语法**，数据即 §5 各指令 JSON 的裁剪版（formatter 负责裁剪与相对时间换算）
- `base.html` 统一：暗色主题、Warframe 风格金色标题、中文字体栈、宽度 800px、
  页脚 `Powered by warframe-api`；各指令模板 `extends base` 只写内容块
- 纯 CSS 实现视觉效果（徽章/进度条/环形图），**不引外部 JS/图片**——截图端点无需额外网络请求即可渲染

#### 7.5.2 输出管线

```
handler 取数 → formatter 裁剪为 view-model(dict)
   ├─ flags 含 -1 或 render_mode=text ──▶ 文本排版 ─▶ plain_result
   └─ 默认：html_render(tmpl_str, vm)
        ├─ 成功 ─▶ image_result(url)
        └─ 失败 ─▶ flags 含 -t ? 重试一次 : 降级文本排版（并 log 原因）
```

- 渲染超时上限 10s；连续失败 3 次自动熔断 5 分钟（期间直接文本），避免刷屏等待
- 图片 URL 有效期未知，**不缓存 URL**，每次现渲染

#### 7.5.3 渲染相关配置

`render_mode`（§3）：`auto`=失败降级文本（默认）；`image`=失败直接报错不降级（便于发现模板问题）；
`text`=全局纯文本。`t2i_endpoint` 留空用官方端点，填自建 chromium 服务地址。

---

## 8. LLM Tools（自然语言入口）

通过 `@filter.llm_tool` 注册，供已配置大模型的会话自动调用：

| 工具名 | 参数 | 映射 |
|---|---|---|
| `wf_search_item` | `query: str` | `/api/search?q=` → 返回前 5 条 名称+slug+可交易+wiki 链接 |
| `wf_market_price` | `slug: str` | `/api/wfm/items/{slug}` → sell.min/avg、buy.max |
| `wf_world_summary` | 无 | cycles + sortie + arbitrations.latest 浓缩摘要 |

LLM 返回一律纯文本（不走渲染管线）。纯指令用户不受影响。

---

## 9. 文件结构

```
plugin/astrbot/
├── main.py              # Star 子类：指令注册 + 分发 + 订阅指令入口
├── api_client.py        # ApiClient 封装
├── formatter.py         # JSON → view-model 裁剪 + 相对时间换算 + 文本排版
├── renderer.py          # html_render 封装：模板加载/熔断/render_mode 分支
├── parser.py            # 附加参数解析 + 翻页缓存
├── subscribe.py         # 蹲/订阅：简称词典、条件解析、轮询任务、命中推送
├── templates/           # §7.5.1 全套 Jinja2 模板
├── _conf_schema.json    # WebUI 配置 schema
├── metadata.yaml        # 已完成
├── requirements.txt     # aiohttp>=3.8, jinja2（AstrBot 自带环境通常已含）
└── README.md            # 使用说明（发布时补）
```

---

## 10. 错误与边界

| 场景 | 行为 |
|---|---|
| API 不可达/超时 | 「warframe-api 服务不可达」 |
| 上游 404/未知节 | 「未找到：xxx」 |
| 上游 worldstate 502（官方源故障） | 透传 error 信息 + 建议「稍后再试」（API 有 stale 回退，多数情况仍能出数） |
| 空结果（如无警报） | 「当前没有进行中的警报」 |
| 国服指令 / `-cn` | 「暂不支持」 |
| HTML 渲染失败 | auto 模式静默降级文本；image 模式报错；连续 3 次失败熔断 5 分钟 |
| 未收录指令 | 「该功能暂不支持，可用指令见『帮助』」（对照 §6 清单） |

---

## 11. 里程碑

| 阶段 | 内容 |
|---|---|
| M1 | 骨架 + ApiClient + **渲染基建（base.html + cycles/alerts/sortie/fissures 四模板跑通）** + 帮助 |
| M2 | 世界状态全量指令（§5.1）+ 对应模板 + 翻页 |
| M3 | 搜索/wiki/掉落/wm/紫卡(wr=wmr=wk)/玄骸/信条 + 模板 |
| M4 | LLM Tools + README + 发布 metadata 校验 |
| M5 | 蹲/订阅系统：简称解析词典 + 轮询引擎 + 命中推送卡（§5.3） |
| M6 | 快做项：`合成`、`部件(垃圾筛选)`（§6.2 标注"可做"两项） |
| M7（远期） | wfm 拍卖接入、价格趋势快照、OCR 系列、国服数据源 |

---

*本文档对应代码仓库 `plugin/astrbot`；API 细节以 `doc/api_usage.md` 为准。*
