# astrbot_plugin_warframe_helper 实现文档

> 版本 v0.1 · 上游设计：[doc/astrbot_plugin_design.md](astrbot_plugin_design.md)
> 运行框架：AstrBot v4.x · Python ≥3.12 · 唯一运行时依赖 `aiohttp`
> 打包命令：**`cargo plugin-pack`** → `dist/astrbot_plugin_warframe_helper.zip`

---

## 1. 目标与范围

按设计文档实现 AstrBot 插件，作为 warframe-api 的聊天前端：

- 指令解析 → HTTP 调用 warframe-api → **HTML 模板渲染图片回复**（文本兜底）；
- 支持「蹲」订阅推送；
- 注册 LLM Tools 供 AI 会话自然语言调用；
- 国服指令占位回复「暂不支持」。

不在范围内：OCR、签到娱乐、跨群组队、账号绑定（见设计文档 §6 清单）。

---

## 2. 开发环境与工作流

```
warframe/
├── plugin/astrbot/          # 插件源码（独立仓库语义，可单独发布）
└── temp/AstrBot/            # AstrBot 本体（仅测试引用，禁止修改其代码）
    └── data/plugins/
        └── astrbot_plugin_warframe_helper -> /root/warframe/plugin/astrbot   # 软链接
```

首次搭建：

```bash
git clone --depth 1 https://github.com/AstrBotDevs/AstrBot temp/AstrBot
mkdir -p temp/AstrBot/data/plugins
ln -sfn "$(pwd)/plugin/astrbot" "$(pwd)/temp/AstrBot/data/plugins/astrbot_plugin_warframe_helper"
cd temp/AstrBot && pip install -r requirements.txt && python main.py
```

调试改代码只动 `plugin/astrbot`，AstrBot 重载插件即可生效。**不得修改 `temp/AstrBot` 内任何文件**。

---

## 3. 目录结构与文件职责

```
plugin/astrbot/
├── main.py              # 入口：Star 子类、指令注册表、分发、订阅指令入口
├── api_client.py        # warframe-api HTTP 封装（单例 session / 错误映射）
├── parser.py            # 通用附加参数解析 + 分页 LRU 缓存
├── formatter.py         # JSON → view-model 裁剪 / 相对时间 / 纯文本排版（降级输出）
├── renderer.py          # html_render 封装：模板加载、熔断器、render_mode 分支
├── subscribe.py         # 蹲/订阅：简称词典、条件解析、后台轮询任务、命中推送
├── templates/           # Jinja2 模板（见 §7 模板体系）
│   ├── base.html
│   ├── components/{reward_row,countdown,progress}.html
│   └── alerts.html … subscribe_hit.html   （24 个，见设计文档 §7.5.1）
├── _conf_schema.json    # WebUI 配置 schema
├── metadata.yaml        # 已完成（name=astrbot_plugin_warframe_helper）
├── requirements.txt     # aiohttp>=3.8
├── logo.png             # 可选，256×256
└── README.md            # 使用说明（M4 补齐后随 zip 发布）
```

### 3.1 `_conf_schema.json`（完整定义）

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

读取：`self.config["api_base"]` 等；AstrBotConfig 变更热生效，无需重启。

---

## 4. 指令注册表（main.py 核心）

统一入口 `dispatch(event, raw_args, flags)`，指令表驱动：

| @filter.command 主名 | alias 集 | handler | 上游端点 | 默认模板 |
|---|---|---|---|---|
| 夜灵 | 平原时间, 循环 | `cmd_cycles` | `/api/cycles` | cycles.html |
| 警报 | — | `cmd_alerts` | sections=alerts | alerts.html |
| 突击 | — | `cmd_sortie` | sections=sortie | sortie.html |
| 猎杀 | 执刑官 | `cmd_lite` | sections=liteSorties | lite_sorties.html |
| 入侵 | — | `cmd_invasions` | sections=invasions | invasions.html |
| 裂隙 | 裂缝, 钢铁裂隙* | `cmd_fissures` | sections=fissures | fissures.html |
| 奸商 | — | `cmd_baro` | sections=void_trader | voidtrader.html |
| 特惠 | 每日特惠 | `cmd_deals` | sections=daily_deals | daily_deals.html |
| 电波 | — | `cmd_nightwave` | sections=nightwave | nightwave.html |
| 新闻 | 最近新闻 | `cmd_news` | sections=events | news.html |
| 仲裁 | 仲裁表 | `cmd_arbitrations` | `/api/arbitrations` | arbitrations.html |
| 恶魔塔 | 沉沦之地 | `cmd_descents` | sections=descents | descents.html |
| 日历 | 1999日历 | `cmd_calendar` | sections=knownCalendarSeasons | calendar.html |
| 活动 | — | `cmd_goals` | sections=goals | goals.html |
| 查 | 物品 | `cmd_search` | `/api/search?q=&trade=&source=` | search.html |
| wiki | — | `cmd_wiki` | search 取首个 wiki_link | search.html |
| 掉落 | 合成, 铸造 | `cmd_drops` | `/api/items/{name}/drops` | drops.html |
| wm | — | `cmd_wm` | search→slug→`/api/wfm/items/{slug}` | wfm_price.html |
| wr | wmr, wk | `cmd_wr` | rivens(+auctions 全语法) | riven.html |
| 词条 | — | `cmd_attrs` | `/api/wfm/rivens/attributes` | attributes.html |
| 玄骸 | — | `cmd_lich` | `/api/wfm/liches` | lich_sister.html |
| 信条 | — | `cmd_sister` | `/api/wfm/sisters` | lich_sister.html |
| 倾向 | — | `cmd_disp` | `/api/weapons/{name}/riven` | riven.html |
| 结合目标 | 结合 | `cmd_synthesis` | `/api/synthesis?type&target` | synthesis.html |
| wm趋势 | — | `cmd_trend` | trends kind=item | trends.html |
| 紫卡趋势 | — | `cmd_rtrend` | trends kind=riven | trends.html |
| 词条价差 | — | `cmd_spread` | `/api/wfm/spread/{slug}` | spread.html |
| 部件 | 金垃圾,银垃圾,铜垃圾 | `cmd_components` | `/api/wfm/components?tier=` | components.html |
| 排行 | 甲排行,卡排行… | `cmd_rank` | `/api/wfm/rankings?type=` | rankings.html |
| 蹲 | — | `cmd_subscribe` | 本地+轮询引擎 | subscribe_hit.html |
| 帮助 | — | `cmd_help` | 静态 | help.html |

另注册：

- `@filter.command_group("wf")`：`/wf 警报` 等英文前缀入口，转发到同一 dispatch；
- 未命中主指令且在 `_UNSUPPORTED_COMMANDS` 表内 → 「该功能暂不支持」；
- `-cn` / cm/cr/rm → 「暂不支持国服」（`_CN_UNSUPPORTED` 表）。

### 4.1 LLM Tools

```python
@filter.llm_tool(name="wf_search_item")
async def tool_search(self, event, query: str) -> str      # → 前5条 name/slug/tradable/wiki
@filter.llm_tool(name="wf_market_price")
async def tool_price(self, event, slug: str) -> str        # → sell.min/avg, buy.max
@filter.llm_tool(name="wf_world_summary")
async def tool_summary(self, event) -> str                 # cycles+sortie+仲裁摘要
```

返回纯文本 JSON 字符串；不进入渲染管线。

---

## 5. 模块设计

### 5.1 api_client.py

```python
class ApiError(Exception): ...          # .message 面向用户展示

class ApiClient:
    def __init__(self, base: str, timeout: int)
    async def get(self, path: str, **params) -> dict | list
        # 2xx → json；{"error":..} → ApiError(error)；非2xx → ApiError(HTTP nnn)
        # aiohttp.ClientError / asyncio.TimeoutError → ApiError("服务不可达")
    async def close(self)
```

单例持有于 Star 子类；`terminate()` 时关闭。**不做重试**（上游已有缓存/stale 回退），失败直接走错误文案。

### 5.2 parser.py

```python
@dataclass
class Flags:
    lang_en: bool = False       # -en
    plain_text: bool = False    # -1/-w
    force_image: bool = False   # -t
    page: int = 1               # -N
    cn: bool = False            # -cn → 直接终止
    platform: str | None = None # -pc/-ps/-xb/-sw（接受但忽略）

def parse(text: str) -> tuple[str, Flags]     # 剥离 token 到 flags，余下为 content
class PageCache:                              # (session_id, cmd_key) → [view-model]
    MAX=128; TTL=300s; get/set/clear
```

正则：`^-(\d+)$` 翻页、`^-(en|1|w|t|cn|pc|ps|xb|sw)$` 标志。未知 `-xxx` 原样留在 content。

### 5.3 formatter.py

职责单一化——**不做网络请求**：

```python
def vm_alerts(data) -> dict            # {"title","items":[{node,type,faction,lvl,reward,expire_rel}],"total"}
def vm_sortie(data) -> dict            # boss + variants[3] + reward 摘要
def vm_cycles(list_) -> dict           # 每循环 state/state_name/expiry_rel
def rel_time(iso: str) -> str          # "3小时12分后结束"/"已过期"
...                                    # 其余节同名 vm_xxx
def to_text(vm: dict, max_lines: int, plain: bool) -> str   # 降级排版（§7.3 规范）
```

所有时间换算基于 `datetime.fromisoformat(z)`，缺失时显示"—"。
超长截断规则：保留前 `max_lines-1` 行 + `……共 N 条，发送『指令 -2』翻页`。

### 5.4 renderer.py

```python
class RenderBreaker:                    # 连续失败3次 → 熔断300s
    fail(), ok(), tripped()

class Renderer:
    def __init__(self, tmpl_dir: Path, mode: str)
    async def render(self, event, tpl_name: str, vm: dict, flags) -> MessageEventResult
        # 1) flags.plain_text 或 mode=text → None（调用方回退文本）
        # 2) breaker.tripped() 且非 force_image → None
        # 3) url = await event.html_render(tmpl_str, vm, return_url=True,
        #                                  options={"full_page":True,"type":"jpeg","quality":60})
        # 4) return event.image_result(url)；异常 → fail() 记录并返回 None
    def load(self, name) -> str           # templates/<name>.html 缓存
```

调用方模式（main.py 统一封装 `reply()`）：

```
result = await renderer.render(...)
if result is None: yield event.plain_result(to_text(vm, ...))
else: yield result
```

`render_mode=image` 时 render 失败改为抛错文案「渲染失败」，不静默降级。

### 5.5 subscribe.py

#### 存储（AstrBot 插件存储 API，SQLite）

```sql
CREATE TABLE IF NOT EXISTS subs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_type TEXT, session_id TEXT,          -- 会话标识
  at_id TEXT, at_name TEXT,                    -- 订阅者（命中推送时 @）
  kind TEXT,                                   -- fissure|cycle|void_trader
  cond TEXT,                                   -- JSON 条件
  created_at INT, expire_at INT,               -- expire_at=NULL=一次性；-1=永久
  last_hit_key TEXT                            -- 推送去重游标
);
CREATE TABLE IF NOT EXISTS seen_keys (k TEXT PRIMARY KEY);
```

#### 简称词典（内置 dict，可被配置追加）

```python
ALIAS = {
  "钢月": [("kind","fissure"),("hard",True),("system","月球"),("mission","生存")],
  "钢镜": [("hard",True),("system","火星"),("mission","镜像防御")],
  "赛中": [("kind","fissure"),("system","赛德娜"),("mission","中断")],
  "三傻": [("kind","cycle"),("cycle","cetus"),("state","night")],
  "夜灵": 同三傻,
  "奸商": [("kind","void_trader")],
  ...
}
DIMENSION_KEYS = {"system","mission","tier","hard","kind","cycle","state"}
```

解析算法：输入切词（词典最长匹配 + 逗号拆多条）→ 每词查 ALIAS 或视为维度赋值 →
未识别词抛 `ParseError(词)`。`普通捕获` 无 hard 维度 = 普通+钢铁均推。

#### 轮询引擎

```python
class Poller:
    INTERVALS = {"fissure":60, "cycle":30, "void_trader":300}
    async def run(self): 每 tick 按 kind 分组合并拉取 → match() → emit
    def match_fissure(cond, entry): 星球/任务/hard 一致
    def match_cycle(cond, cyc): state 相等且与 last_hit_key 不同（边沿触发）
    def match_voidtrader(cond, vt): activation<=now<expiry 且未推送过本轮 id
async def emit(session, title, lines, at_id=None, at_name=None):
    MessageChain(chain=[At(qq=at_id), Plain(text)]) → context.send_message
    At 组件被平台拒绝时自动退回纯文本（纯文字，不渲染图片）
```

生命周期：`initialize()` 创建 task；`terminate()` cancel。会话定位：存 `unified_msg_origin`，
推送用 `self.context.send_message(unified_msg_origin, chain)`。

#### 订阅指令语义

```
蹲 <简称|维度词…> [时长]     解析成功→入库，回显订阅卡
蹲 列表                      枚举本会话
蹲 <序号> 取消 / 蹲 取消      删除
时长: 7天|两周|长期|永久|数字+h/d/w/m；缺省=命中一次即删
```

---

## 6. view-model 数据契约示例

formatter 输出既是渲染数据也是文本排版数据，字段命名稳定供模板引用：

```jsonc
// vm_fissures.items[]
{ "tier":"前纪", "tier_badge":"MESO", "node":"Copernicus",
  "system":"月球", "mission":"生存", "hard":true,
  "expire_rel":"42分钟后", "expire_iso":"..." }

// vm_descents.challenges[]（21 层）
{ "index":7, "type_name":"祈运坛防御",
  "challenge_name":"易受曲翼枪械攻击的敌人",
  "level_name":"蜜桃竞技场",
  "specs":["Grineer"], "auras":["化学战"] }

// vm_arbitrations
{ "latest":{...同 schedule 单项}, "upcoming":[ {...}, ... ] }

// vm_wm_price（/api/wfm/items/{slug} 裁剪）
{ "name":"适应", "game_ref":"/Lotus/...", "wiki":"https://...",
  "sell_min":4, "sell_avg":4, "buy_max":41,
  "sell_orders":[{platinum,quantity,user,status}], "buy_orders":[...] }

// vm_search.results[]
{ "source":"wfm", "badge":"WM", "name":"绝路 Prime 枪管",
  "tradable":true, "slug":"rubico_prime_stock",
  "ducats":45, "wiki":"..." }
```

---

## 7. 模板约定

- `base.html`：`{% block title %}{% block body %}` 两槽；暗色主题 `#0e1116` 底 +
  金色 `#c9963f` 标题栏；中文字体栈 `"Noto Sans SC","Microsoft YaHei",sans-serif`；
  内容宽 800px；页脚 `Powered by warframe-api`。
- 子模板 `{% extends "base.html" %}` 只填两 block；宏放 components/ 用 `{% import %}`。
- 徽章/进度条/倾向环形图纯 CSS；**禁外链 JS/CSS/图片**。
- 数值样式约定：白金价 `{{ price }}p`；倒计时红字 `<5%` 剩余。

---

## 8. 错误处理矩阵（实现落点）

| 场景 | 抛出/处理位置 | 用户文案 |
|---|---|---|
| API 连接失败/超时 | ApiClient → ApiError | warframe-api 服务不可达 |
| 上游 error 字段/HTTP≠2xx | ApiClient | 查询失败：{原因} |
| 空结果 | handler 判空 | 当前没有进行中的警报（各指令定制） |
| 502 stale | 透传 error | 查询失败：…（官方源波动，稍后再试） |
| `-cn` / cm·cr·rm | dispatch 拦截 | 暂不支持国服查询 |
| §6 清单指令 | `_UNSUPPORTED_COMMANDS` | 该功能暂不支持，可用指令见『帮助』 |
| 渲染失败 | Renderer.fail() | auto:静默降级文本 / image:「渲染失败」 |
| 订阅解析失败 | ParseError | 无法识别『xx』，可用：星球/任务/钢铁/夜灵/奸商… |

---

## 9. 打包与安装

### 9.1 打包（本仓库内置工具）

```bash
cargo plugin-pack
# 等价：cargo run --release --features pack-plugin --bin pack-plugin
# 自动编译依赖 → 产出 dist/astrbot_plugin_warframe_helper.zip
```

- 工具源码：`src/bin/pack_plugin.rs`（zip 依赖仅此 bin 启用 `[features]`，主服务二进制不受影响）
- 排除项：`.git/`、`__pycache__/`、`*.pyc/pyo`、`.DS_Store`、`.gitignore`
- 条目排序稳定 → 重复构建 zip 二进制一致（利于校验）

### 9.2 安装到 AstrBot

任选其一：

1. **WebUI**：插件市场 → 从本地上传 `dist/astrbot_plugin_warframe_helper.zip`；
2. **手动**：解压至 `AstrBot/data/plugins/astrbot_plugin_warframe_helper/`，重启或在 WebUI 重载；
3. **开发态**：使用 §2 软链接，无需安装。

安装后在 WebUI 配置 `api_base` 指向 warframe-api 即可用。

### 9.3 发布 checklist

- [ ] `metadata.yaml` version 递增、repo 指向真实仓库
- [ ] README.md 使用说明齐全（指令表 + 截图）
- [ ] `logo.png` 256×256
- [ ] `cargo plugin-pack` 产物通过 AstrBot WebUI 安装冒烟
- [ ] tag 与 version 对齐（v0.x.y）

---

## 10. 测试要点

| 类别 | 用例 |
|---|---|
| 指令冒烟 | §4 表逐条：有数据/空结果/404 三态 |
| 参数 | `-en` `-1` `-2` `-t` `-cn` 组合乱序；未知 flag 不吞内容 |
| 渲染 | 每模板出图人工目检；断网 t2i 端点验证熔断与降级；`render_mode=text/image` 三态 |
| 分页 | >limit 列表翻页一致性；TTL 过期后重取 |
| 别名 | 血妈/猴子/福马/紫卡/wk/wmr 等价性 |
| 订阅 | 蹲钢月→构造 fissure 命中→收图；边沿触发只推一次；取消/过期清理；重启恢复 |
| LLM Tool | 配置模型后自然语言提问触发对应工具 |
| 兼容 | OneBot(aiocqhttp) 与 Telegram 双平台发图/长文 |

---

## 11. 里程碑对照

M1 骨架+ApiClient+渲染基建(cycles/alerts/sortie/fissures)+帮助 →
M2 世界状态全量 → M3 市场/资料(wr 含 §5.2.1 全语法) → M4 LLM Tools+README →
M5 订阅系统 → M6 已并入 M3 → M7 远期（拍卖中文词条别名扩展、OCR、国服）。

当前进度：**metadata.yaml 完成；打包工具完成；main.py 及各模块待 M1 编码**
（现有 `plugin/astrbot/main.py` 为 helloworld 占位模板）。

---

*API 契约以 [doc/api/README.md](api/README.md) 为准；视觉与交互规范见设计文档 §5–§7。*
