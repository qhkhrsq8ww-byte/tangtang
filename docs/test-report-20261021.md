# 糖糖全面测试报告（2026-10-21）

> 依据 docs/test-plan-20261021.md 执行 · 设备归属已确认：姐姐=HONOR-70，弟弟=vivo-Y70s
> 环境：MacBook Air 2014 · macOS 11.7.11 · 路由器 R3D ROM 2.28.17

## 一、执行路径

测试计划（本计划文档）→ 统计采集器上线（cat-usage-stats.py + LaunchAgent）→ V4 运行时与生产钉住策略确认（团队 docs/runtime-and-provisioning.md）→ 冒烟套件适配（pin 机制 + 本机配置豁免）→ 全面测试 T1–T8 → 报告入库。

## 二、测试结果（T1–T8 全过）

| # | 测试项 | 结果 | 证据 |
|---|---|---|---|
| T1 | 路由 API 登录与读取 | ✅ | 温度 40°C / 内存 56% / 固件 2.28.17 |
| T2 | 行为统计采集 | ✅ | 快照写入 usage.jsonl（本机） |
| T3 | 统计持久化 | ✅ | LaunchAgent com.tangtang.usage 已加载（15min） |
| T4 | 控制动作可逆 | ✅ | block/unblock 双向 code:0（打印机靶标） |
| T5 | 定时体系 | ✅ | cat-server/proactive/usage 三代理加载 |
| T6 | 语音环就位 | ✅ | cat-voice-chat/cat-talk/quiet-hours 就位（夜间未实际发声） |
| T7 | 冒烟套件 | ✅ | 全 PASS（含 PINNED 机制首秀） |
| T8 | 隐私 | ✅ | .llm_key/.router_key/cat-devices.json 全 600，gitignore 覆盖 |

## 三、生产钉住机制（新）

团队 runtime-and-provisioning 文档确认：V4 需 Python ≥3.10，生产在 3.11 就绪前保持已验证直连版。冒烟套件新增 `.pinned-live-files` 机制——被钉住的文件（当前：cat-chat.py）不参与 repo↔live 漂移比对，显示为 PINNED 状态而非 FAIL。解除条件：安装 Python 3.10+ 并通过 V4 上线验收清单（见团队文档 §4）。

## 四、上网行为统计基线（采样起步，持续积累中）

| 设备 | 归属 | 在线时长 | 峰值下载 | 说明 |
|---|---|---|---|---|
| vivo-Y70s | 弟弟 | 4.3h（本次连接） | 192 KB/s | 最活跃设备，均值 35 KB/s |
| HONOR-70 | 姐姐 | 2.2h（本次连接） | 0 | 静默在线 |
| Redmi-Note-11-5G | 待指认 | **39.0h 连续在线** | **832 KB/s** | 待指认设备中流量最大，建议家长指认 |
| M2007J17C（红米9） | 待指认 | 2.0h | 0 | 待指认 |
| Unknown | 待指认 | 1.0h | 126 KB/s | 待指认 |
| EPSON310FDE | IoT | 168h | 0 | 常通 |
| Mac（管理机） | 家长 | 46.8h | 15 KB/s | 永不断网组 |

- 统计启动时间：2026-10-21 20:58（usage.jsonl，本机 ~/Library/Logs/tangtang/）
- 采集频率：15 分钟/次（机器睡眠时自动暂停，属正常）
- 已观察行为：弟弟设备有持续下载活动；姐姐设备静默在线；Redmi-Note-11-5G 有 832KB/s 峰值且 39h 未断线

## 五、V4 上线待办（团队侧，依团队文档）

1. 本机安装 Python ≥3.10（独立目录），确认 python3.11 --version
2. 从可信本机备份恢复 V4 所需本机文件（密钥/状态，勿从仓库或聊天记录取）
3. 按 V4 上线验收清单逐项验收（门控/异常退出/成员缺失/实机语音投影联动）
4. 验收全过 → 解除 .pinned-live-files 中 cat-chat.py → 部署 V4 → 冒烟复跑

## 六、回滚方式

若 V4 部署后异常：`git show <稳定提交>:code/cat/cat-chat.py > ~/tangtang/cat/cat-chat.py`（当前稳定版 = b29ee95 的直连版），随后重跑冒烟套件。
