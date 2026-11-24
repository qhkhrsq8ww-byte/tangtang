# TangTang V4 记忆链路与入口审计

> 审计基线：main 分支 `d3d3e7009e12d9306db36dec8de00e6b575dbc10`
> 审计日期：2026-11-24
> 范围：V4 Core、CLI/语音入口、旧版兼容路径、持久化记忆与模型上下文

## 1. 当前可信主链

```text
cat-voice.sh / cat-chat.py
        │
        ▼
_private_cli_reply()
        │
        ▼
ChatAdapter.turn()
        │
        ▼
PrivacyPipeline.ingest()
        │
        ├─ IdentityResolver.resolve()
        ├─ PrivacyPolicy.assert_event_privacy()
        ├─ Event.create() + SafeLogger
        └─ gated stores
             ├─ PrivateMemory (PRIVATE owner-only)
             ├─ FamilyMemory (policy-gated)
             ├─ FamilySummary (structured fields)
             ├─ ParentContext (policy-gated)
             └─ HabitStore (policy-gated)
        │
        ▼
SpeakGate → ContextBuilder → structured recall → optional LLM
        │
        ▼
ResponseOrchestrator → PresentationAction
```

代码事实：
- `ChatAdapter.turn()` 当前调用 `pipeline.ingest()`，并在模型调用前执行风险识别、任务/提醒/记忆意图处理及 Speak Gate。
- `PrivacyPipeline.ingest()` 先执行身份解析和隐私分类，再创建事件并写入对应存储。
- 儿童私人对话默认不上传模型；需要显式 `TANGTANG_ALLOW_PRIVATE_LLM=1`。
- 未知身份默认不上传模型；需要显式 `TANGTANG_ALLOW_UNKNOWN_LLM=1`。
- 风险披露走本地安全回复，不进入普通模型调用。
- `retrieve_structured_memories()` 仅允许当前 member 与 viewer 精确一致，并只投影白名单字段；不把原始语音历史直接注入模型。
- FamilyMemory / FamilySummary / ParentContext 的写入有独立 PrivacyPolicy 检查；儿童原话不能写入家庭共享存储。

## 2. 存储分桶与数据边界

| 存储 | 用途 | 当前约束 |
|---|---|---|
| PrivateMemory | 成员个人私密内容、明确记住的偏好 | 按成员独立文件；读取要求 owner/viewer 一致；有 TTL |
| FamilyMemory | 家庭共享事实/成人可共享内容 | 独立策略校验；拒绝 PRIVATE 和儿童原话 |
| FamilySummary | 家庭结构化摘要 | 写入 mood/count 等结构化字段；不应放原话 |
| ParentContext | 家长可见的受控家庭事件 | 策略控制；当前 ingest 写入结构化 note |
| HabitStore / HabitTrendStore | 习惯与趋势标签 | 趋势账本只存标签/计数，不应存儿童原话 |
| Event / JsonlEventStore | 事件事实与审计 | Event payload 由 ingest 脱敏；JsonlEventStore 是独立适配器，不代表当前每条语音都已接入持久事件日志 |
| FamilyMemoryV2 | 从旧习惯账本生成家庭状态 | 读取旧账本并生成派生状态；不是原始语音记忆库 |

## 3. 已发现的边界与修复

### 3.1 已修复/正在修复

- 未知说话人身份不得写入家庭共享记忆：PR #83。
- ingest 不再用未经解析的原始 member_id/label 兜底建立身份：PR #86。
- ContextBuilder 不再从 observation.member_id 推断记忆 owner；viewer 必须与 Core 解析的 owner 一致：PR #89。
- 原始语音日志与儿童原话持久化风险已在此前代码中收紧；历史本地文件仍需迁移前单独清点。

### 3.2 仍需注意

- `PrivacyPipeline.ingest()` 是 V4 语音记忆的受支持入口，但不是所有旧脚本/所有记忆工具的统一写入口。
- `LearningMemoryService.on_interaction()`、`HabitTrendStore`、`FamilyMemoryV2`、任务服务属于独立服务/适配路径；必须继续审计调用方是否传入可信 member_id。
- `cat-living.py` 接受命令行/环境变量成员参数，再交给 Runtime；这些参数是身份候选，不应视为认证凭据。
- `cat-chat.py` 的 V4 路径会调用 ChatAdapter；但文件仍保留旧 V3 直连路径。
- `cat-chat-history.json` 仅在显式关闭 V4 后的旧分支读写，可能包含完整用户/助手对话。迁移前必须盘点本地文件并决定是否删除/导入，不能默认上传或合并。
- `cat-brain.py` 维护 `cat-memory.json` / `cat-state.json` 等旧状态文件；这些文件与 V4 PrivateMemory/FamilyMemory 不是同一套存储，不能未经转换直接并入新记忆。
- `JsonlEventStore` 当前是独立 adapter；不能把“模块存在”描述为生产事件审计链路已经闭环。

## 4. 下一步整改要求

1. 对所有 CLI、shell、voice、living-room、proactive、task、alarm 入口建立调用图，标注身份字段来自命令行、环境变量、传感器还是 Core。
2. 对每个持久化写入点建立矩阵：目标存储、成员范围、隐私级别、原话允许性、TTL、删除路径。
3. 所有 sensor/caller 的 member_id 都作为候选值；只有 Core resolver 的 canonical result 才能授权 owner-scoped recall。
4. 未知身份不得积累跨回合上下文，不得写入家庭共享记忆，不得进入儿童个人记忆。
5. 旧 V3 文件不自动导入 V4；迁移必须有逐文件清单、字段映射、隐私重分类、过期清理和备份/回滚方案。
6. 不以单元测试代替真实语音链路验证；Mac mini 实机阶段另行验证。

## 5. 验收标准

- 所有语音入口都能追溯到唯一隐私闸门，或明确标记为 legacy-only 并被默认关闭。
- 不存在由原始 observation.member_id / CLI 参数 / 环境变量直接授权读取私人记忆的路径。
- 任何访客输入均不能写入家庭共享记忆或复用跨回合上下文。
- 原始儿童语音仅在明确授权的个人私密存储中短期保存；云端上传仍为显式 opt-in。
- 旧 V3 对话历史不自动并入 V4。
- 关键红线测试覆盖所有入口，而不只覆盖 ChatAdapter 单测。
