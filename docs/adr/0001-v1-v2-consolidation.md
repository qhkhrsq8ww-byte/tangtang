# ADR-0001: V1 脚本栈与 V2 core 框架的整合策略

## Status: Proposed

## Context
系统存在两代资产：V1 脚本栈（code/cat，61 文件，生产运行，当日全链路实测通过）与 V2 core 框架（8045 行，类型注解齐全、含 legacy_adapter 迁移桥，从未部署）。V2 的 memory/emotion_drift 数值与 V1 cat-brain 完全对齐（loneliness +5/h、happiness −1.5/h），说明迁移设计过但停在部署前。

## Decision
分阶段整合，不重写也不归档：①短期冻结 V2 新功能，V1 持续演进（生产真理源）；②按 memory → tasks → persona 顺序，经 behavior/legacy_adapter 逐模块替换；③V2 测试（tests/）随每模块替换启用。

## Consequences
正：保住 8000 行高质量资产；每次替换有测试闸门；风险分片。
负：双代并存期延长，需要零漂移检查持续护航；V2 部分模块仍需适配 live 的 Bash 集成。

## Alternatives Considered
- 立即全量切 V2：拒绝——迁移当日风险大，live 的修复（密钥/路径/直连）会与 V2 未验证代码冲突。
- 归档 V2：拒绝——工程质量高、隐私设计对齐产品目标，且 legacy_adapter 证明迁移成本已被支付大半。
