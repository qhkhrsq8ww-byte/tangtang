# 糖糖团队克隆测试报告（2026-10-20）

> 模拟团队成员入职：从 GitHub 全新克隆 → 稀疏检出（绕过 179MB 媒体）→ 全量语法/安全/冒烟测试 → V4 管线验证
> 结论先行：**代码资产健康，但发现一个部署阻断级兼容问题（V4 需要 Python ≥3.9）**

## 一、克隆与结构验证

- 稀疏克隆（git 2.32 `--filter=blob:none` + 非 cone 模式 `/*` 排除 `code/cat/assets/`）：只拉代码不拉 179MB 媒体，慢网络可用；cone 模式在 git 2.32 有 CLI 缺陷（`--no-cone` 会被误当模式，见附录）
- **密钥与儿童数据在新克隆中零存在**：.llm_key / .baidu_token / cat-stt-config.sh / family.json / school_calendar.txt 全部缺席 ✓（gitignore 从新克隆视角生效）
- code/cat 86 文件就位，关键脚本（cat-chat/cat-talk/cat-voice-chat/deploy.sh）齐全

## 二、测试结果

| 项 | 结果 |
|---|---|
| bash -n 全部 .sh（27 个） | ✅ 全过 |
| py_compile 全部 .py（含 V2 core 8045 行） | ✅ 全过 |
| 冒烟套件（指向克隆） | 3 FAIL 均为预期：新克隆按设计缺 .llm_key / cat-stt-config.sh / 运行时记忆——属**配置引导缺口**（见 §四） |
| cat-chat.py 干跑（无 key） | ✅ 401 → 离线大脑兜底秒回 |
| dotfile HTTP 防护 | ✅（宿主服务仍在跑） |
| LaunchAgent | ✅ cat-server + proactive 均加载，夜间静默符合设计 |

## 三、P1 发现：V4 管线与本机 Python 3.8.9 不兼容（阻断级）

**现象**：克隆版 cat-chat.py（团队 V4 版，427 行）调用 `tangtang-speak-gate.py` 时崩溃：`TypeError: 'ABCMeta' object is not subscriptable`（core/events/event_bus.py 的 `collections.abc.Callable[...]` 下标语法需 Python ≥3.9）。门控为 **fail-closed**——崩溃即静默，若此版直接部署到本机，糖糖将彻底不出声。

**量化**：18 个文件使用同模式（Callable 下标）；约 45 个文件疑似含其他 3.9+ 语法。

**验证性修复**：将 event_bus.py 的导入改为 `from typing import Callable`（3.8 可下标）后，门控立即通过（输出 speak）。说明兼容层可行，但需团队统一决策而非零散补丁。

**建议（二选一，写入 README 运行要求）**：
1. 声明运行时要求 Python ≥3.9 并提供安装引导（python.org 包或 uv 托管解释器）
2. 或建立 3.8 兼容层：全仓 `collections.abc.Callable` → `typing.Callable`，并排查 union `|` 语法（~45 文件需复查）

## 四、V4 管线行为确认（设计正确）

- **发声门控 fail-closed**：presence/成员不可解析 → 静默。符合"没人时不乱说话"
- **儿童内容默认拒绝出网**：`_runtime_llm` 对 PRIVATE scope 要求 `TANGTANG_ALLOW_PRIVATE_LLM=1`、未知说话人要求 `TANGTANG_ALLOW_UNKNOWN_LLM=1` 双开关，默认走离线兜底
- **.llm_key 接线保留**：V4 的 `_runtime_llm` 内部复用 `chat()`（即智谱直连 + .llm_key）
- **遗留集成缺口**：V4 需要完整 core 数据面（context builder → filtered prompt）才能产出非兜底回复；新克隆缺 data/ 运行文件时静默兜底。建议团队提供 provisioning 清单（见 §四）

## 五、新克隆配置引导清单（建议固化为 cat-provision.sh）

1. `cp` 密钥三件套：.llm_key / cat-stt-config.sh（本机保留，不入库）
2. `cp` 运行时状态：cat-state.json / cat-memory.json / cat-chat-history.json / cat-habits.json / data/family.json
3. `chmod 600` 全部密钥文件
4. Python 版本确认（见 §三）
5. `bash tests/smoke-20261019.sh` 必跑

## 六、给团队的三个立即行动项

1. **声明 Python 运行时要求**（≥3.9）或完成 3.8 兼容层——否则 V4 部署即静音
2. 把本报告 §五 的 provisioning 清单固化为脚本/文档
3. `.github/workflows/v4-tests.yml` 已存在——建议把 smoke 套件（语法+安全节）纳入 CI

## 附录：本机克隆技巧（慢网络团队参考）

```bash
git clone --filter=blob:none --no-checkout git@github.com:qhkhrsq8ww-byte/tangtang.git
cd tangtang-test
git config core.sparseCheckoutCone false
printf '/*\n!/code/cat/assets/\n' > .git/info/sparse-checkout
git read-tree -mu HEAD
```
（git 2.32 的 cone 模式 CLI 会把 --no-cone 误当模式；非 cone 直接写文件可绕过。已有完整本地克隆的同事可用 objects/info/alternates 指向本地对象库秒级完成。）

## 追加（2026-10-20 20:5x）：第三个兼容断点确认

V4 部署实测（经 deploy.sh 常规漂移修复带入 live）暴露完整兼容链：
1. `collections.abc.Callable[...]`（event_bus.py，已补 typing.Callable 并提交）
2. `zoneinfo`（core/tasks/reminders.py）——Python 3.9+ 标准库，3.8 无对应标准模块
3. 修复 1+2 后 gate 通过、V4 管线可运行，但 context 数据面在克隆/部署环境仍走兜底（需 V2 数据目录 ~/Library/Application Support/Tangtang 完整）

**处置**：live 的 cat-chat.py 已回退至直连版（b29ee95，含记忆注入，实测 GLM 生成回复正常）——V4 在 py≥3.9 运行时就绪前不部署。本提交同时携带 event_bus.py 的 3.8 兼容补丁。
