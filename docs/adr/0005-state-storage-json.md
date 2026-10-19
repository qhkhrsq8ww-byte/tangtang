# ADR-0005: 状态存储采用 JSON 文件（设 Revisit 触发器）

## Status: Accepted；Revisit 触发器已定义

## Context
糖糖的状态（情绪、记忆、习惯、聊天历史）当前为多个小 JSON 文件（每个 <3KB），由单进程顺序读写，原子写入（tmp+rename）。

## Decision
维持 JSON 文件方案；写入必须保持 tmp+os.replace 原子模式与"儿童原话不入账本"约束。触发以下任一条件时迁移 SQLite（参考已验证的 state.db+WAL+FTS5 模式）：①出现多写者并发；②任一历史文件 >1MB；③需要跨文件事务。

## Consequences
正：零依赖、可读可调试、与脚本栈天然兼容。
负：并发写风险靠"单写者"纪律维持；查询能力弱（FTS 类需求出现即触发迁移）。
