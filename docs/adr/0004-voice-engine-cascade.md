# ADR-0004: 语音引擎级联（STT 与 TTS 均带回退）

## Status: Accepted

## Context
糖糖的听与说都依赖外部服务（百度 STT、微软 Edge TTS、百度翻译 TTS），运行环境网络不稳定（同日 GitHub 直连曾低至 KB/s 级），且夜间与离线场景需要静默与降级路径。

## Decision
STT：百度语音识别 REST（凭据仅存本机 cat-stt-config.sh，脚本自刷新 token）。TTS：Edge（晓晓）→ 百度翻译 → macOS say 系统嗓，三级级联。语音环任何一环失败 → 离线规则大脑兜底；儿童语音 PCM 即用即删。

## Consequences
正：任一外部服务故障不断线；隐私边界（原话不落盘）在管线内实现。
负：百度 STT 依赖凭据轮换；Edge TTS 依赖微软可达性；离线 STT 缺位（静音退出而非降级识别）。

## Alternatives Considered
- vosk 离线 STT（小模型 ~40MB）：备选——网络断续或隐私升级时启用，本轮未实施。
- 本地 whisper：拒绝——4GB 2014 硬件不满足。
