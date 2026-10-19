# ADR-0002: 云端大脑直连 OpenAI 兼容端点

## Status: Accepted（2026-10-19）

## Context
糖糖对话层需要一个 LLM 端点。候选：智谱官方直连 / AutoClaw 网关代理 / 本地模型。
约束：2014 双核 4GB 硬件（本地模型不可行）；网关 chatCompletions 端点为运行时保护配置，agent 与脚本不可自开；儿童对话需要低成本可持续。

## Decision
cat-chat.py 直连 https://open.bigmodel.cn/api/paas/v4，模型 glm-4-flash（免费），key 存本机 .llm_key（600），支持 QCLAW_LLM_* 环境变量覆盖；失败时离线规则大脑兜底。

## Consequences
正：零新增进程、零费用、离线兜底保底、key 可轮换。
负：直连意味着人设提示词在客户端拼装（无服务端会话）；依赖外部服务可用性。
中性：云端大脑与规则大脑并存为长期形态。

## Alternatives Considered
- OpenClaw 网关代理：拒绝——endpoint 开启属受保护配置，且该端点为操作员级权限面。
- 本地模型（Ollama/whisper 类）：拒绝——4GB 硬件不满足。
- Hermes Agent：拒绝——已移除（上游文档以 Linux 为主，Docker 隔离超出硬件内存）。

## References
docs/test-report-20261019.md · docs/adr/0006-child-privacy-boundary.md
