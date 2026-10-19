# 糖糖（TangTang）架构审核报告

> 审核方式：architecture-designer 流程（组件盘点 → NFR 评估 → ADR → 风险登记 → 路线图）
> 审核范围：双代代码资产（V1 脚本栈 + V2 core 框架）、部署管线、安全与隐私、测试体系
> 审核基线：commit b29ee95 之后、本次提交之前 · 运行环境 MacBook Air (Early 2014) / macOS 11.7.11

## 0. 立即行动项（P0，本次已缓解 + 需人工跟进）

**发现：仓库为 PUBLIC，且 git 追踪着家庭与儿童数据**（data/family.json 五口之家名册、data/school_calendar.txt 上学日历、data/rest_days.txt、data/habit_growth.json）。

- 本次已缓解：四文件解除追踪（本地保留）+ .gitignore 拦截 + 本报告与测试报告已做化名处理
- ⚠ **需人工立即执行：GitHub → Settings → General → Danger Zone → Change visibility → Private**（agent 无法代做）
- ⚠ 历史提交中仍含上述文件与孩子昵称，建议择期 git filter-repo 清理历史后强推
- 值得肯定的既有设计：儿童原话不落盘、声纹与习惯流水只在本机（family.json 注释与 V2 模块 docstring 均有明确声明）——本次疏漏是数据文件级，非原则级

## 1. 系统概览

### 部署拓扑

```text
[大眼橙投影 AirPlay] ←— 显示 cat-stage.html（客厅舞台）
[小米蓝牙音箱]       ←— 音频输出
[客厅 MacBook Air 2014 · 4GB] ←— 全部计算
  ├─ LaunchAgent com.tangtang.cat-server  → cat-serve.py :8080（静态+Range，dotfile 已拦截）
  ├─ LaunchAgent com.tangtang.proactive   → cat-proactive-bridge.sh(每30min) → cat-remind.sh
  │                                          → cat-talk.sh(事件发声器) → cat-brain.py(规则大脑) → cat-say.sh(TTS级联)
  ├─ 交互对话: cat-voice-chat.sh → cat-listen(麦克风) → cat-stt-baidu(百度STT)
  │              → cat-chat.py(智谱 glm-4-flash 云端大脑) → cat-say.sh
  ├─ 数据: cat-state/memory/habits/history JSON（本机）+ .llm_key/.baidu_token/cat-stt-config.sh（密钥，600）
  └─ 测试: tests/smoke-20261019.sh（九节离线冒烟）+ tests/v4
[GitHub 公开仓库] ←— 代码（儿童数据文件本次已移出）
[智谱 bigmodel / 百度翻译TTS / 百度ASR / 微软Edge-TTS] ←— 外部服务
```

### 双代代码资产（核心架构事实）

| 资产 | 规模 | 状态 | 说明 |
|---|---|---|---|
| V1 脚本栈（code/cat，61 文件） | ~1600 行核心 + 脚本群 | **生产运行中** | cat-brain 规则大脑、cat-chat 云端层、cat-talk 事件发声、cat-voice-chat 语音环、TTS/STT 级联、守护脚本 |
| V2 core 框架（core/，8045 行） | memory/tasks/persona/context/response/events/identity/adapters | **已编写、未部署** | 工程质量高：类型注解、隐私注释（“Never stores child utterances”）、behavior/legacy_adapter.py 专为吸收 V1 事件而设计 |
| behavior/ | character_state + legacy_adapter | 未部署 | V1→V2 事件翻译桥（迁移路径已预留） |

**核心判断：这不是"重写未完成"，而是一场完成度约 80% 的迁移在最后 20%（部署与切换）处停滞。**

### 关键数据流

1. 主动提醒流：launchd(30min) → 按小时挑事件 → 规则大脑（冷却闸）→ 情绪音色 TTS 级联 → 投影/音箱
2. 对话流：麦克风 → STT → glm-4-flash（人设+记忆注入+8轮历史+儿童安全过滤）→ 晓晓 TTS；任何一环失败 → 离线规则大脑兜底
3. 部署流：repo（唯一真理源）→ deploy.sh → live（密钥/运行时豁免）→ smoke 九节冒烟必跑

## 2. NFR 评估

| 维度 | 评级 | 依据 |
|---|---|---|
| 性能 | 合格（受硬件天花板约束） | 负载主因是宿主 AutoClaw；糖糖自身脚本均轻量；JSON 状态 <3KB |
| 安全 | 良好（本次修复后） | 密钥 600 + 不入库 + gitignore；HTTP dotfile 拦截；服务仅 loopback（patrol 兜底已改） |
| 隐私 | 设计优秀 / 执行曾疏漏 | 原则正确（原话不落盘、声纹本机）；公开仓库含家庭数据为本轮 P0（已缓解，见 §0） |
| 可维护性 | 显著改善 | deploy.sh + 零漂移检查 + 冒烟套件补齐了"双拷贝漂移"这块最大短板 |
| 可观测性 | 弱 | 日志散落各 logs/、无 healthcheck 聚合、launchd 输出独立 |
| 可持续/韧 | 弱 | 单机单点、无状态备份、硬件与 OS 双 EOL（Big Sur 无安全补丁） |

## 3. 架构决策记录（ADR）

完整 ADR 见 docs/adr/0001–0006。摘要：

| ADR | 决策 | 状态 | 核心取舍 |
|---|---|---|---|
| 0001 | 双代整合：分阶段经 legacy_adapter 吸收，不重写不归档 | Proposed | 立即切 V2=迁移风险大；归档 V2=浪费 8000 行高质量资产；推荐"先冻结 V2 新功能、V1 持续演进、按 memory→tasks→persona 顺序逐模块吸收" |
| 0002 | 云端大脑直连智谱 OpenAI 兼容端点（glm-4-flash 免费） | Accepted（今日） | 拒绝网关代理（chatCompletions 为受保护配置且多一层 operator 面）；拒绝本地模型（4GB 硬件）；Revisit 触发：隐私升级/付费模型/多模型路由 |
| 0003 | 部署管线：deploy.sh 单向 + smoke 后置闸门 | Accepted（今日） | 拒绝双向同步（正是历史漂移根因）；拒绝 git-pull 部署（live 混有豁免文件） |
| 0004 | 语音引擎级联：STT 百度云（凭据仅本机）；TTS Edge→百度翻译→系统嗓 | Accepted | 备选 vosk 离线 STT（网络断续/隐私升级时启用）；whisper 因硬件拒绝 |
| 0005 | 状态存储：JSON 文件 | Accepted，设 Revisit 触发器 | 当前 <3KB/文件够用；迁移 SQLite 触发条件：多写者并发 / 历史 >1MB / 需要事务 |
| 0006 | 儿童隐私边界：原话不落盘、声纹本机、密钥不入库、家庭数据不入库 | Accepted，含 P0 整改 | 违规项（§0 数据文件被追踪）本次整改；历史清理待办 |

## 4. 风险登记册

| 级别 | 风险 | 缓解/状态 |
|---|---|---|
| P0 | 公开仓库含家庭结构与上学日历 | 本次解除追踪+忽略；⚠ 用户转 Private；历史 filter-repo 清理待办 |
| P1 | 硬件与 OS 双 EOL（2014 机型 + Big Sur 无安全补丁） | 短期可用；中期建议迁 VPS 或新机（Node 24 环境下 OpenClaw 最新版已验证可用，本报告同日实测） |
| P1 | live 运行状态单点无备份 | 建议每日 tar 备份 state/memory/habits 至本机第二位置（后续落地） |
| P1 | V2 迁移停滞 | ADR-0001 分阶段路线；legacy_adapter 已备 |
| P2 | 媒体资产 100MB+ 未入库、无 LFS | Git LFS 或网络良好时单独提交 |
| P2 | 可观测性分散 | 统一日志聚合 + healthcheck 脚本（后续） |
| P2 | 睡觉文案昵称与配置昵称并存（姐姐/弟弟别名体系已明确） | 家庭确认统一 |

## 5. 路线图

**30 天**：仓库转 Private（人工）→ filter-repo 历史清理 → 密钥轮换 → 每日状态备份 → 昵称统一
**60 天**：冒烟套件接 GitHub Actions（语法+安全节，不跑音频）→ 主动提醒接 presence 门控（判断孩子是否在家）→ 记忆注入扩容（habits 摘要）
**90 天**：经 legacy_adapter 用 V2 memory 模块替换 V1 情绪漂移（数值已对齐：loneliness +5/h、happiness −1.5/h）→ 媒体 LFS → 可观测性聚合

## 6. 审核人备注

本次审核同时验证了"遗漏根因"机制假设：双拷贝漂移、路径时代残留、同名覆盖、依赖链断缺四类问题在一天内全部实际出现并被测试捕获（详见 test-report-20261019.md 第二节）。架构层面的结论：**先机制后迁移**——部署管线与测试闸门（今天已建）是任何 V2 迁移的前置条件，否则同样的遗漏会在新架构里重演。
