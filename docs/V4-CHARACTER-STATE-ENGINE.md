# 糖糖 V4 Character State Engine

## 目标

把“发生了什么”与“糖糖该呈现什么状态”分开。

数据流：

`Observation → Event → Context → Policy → CharacterStateResolver → PresentationAction`

## 规则

- CharacterStateResolver 是确定性的，不由 LLM 决定。
- Quiet Hours / Policy 优先于普通动作。
- active conversation 优先于普通环境事件。
- 角色状态只允许 17 个已注册状态。
- Resolver 只输出 `state / reason / priority`，不产生文件路径、不调用 TTS、不执行 shell。

## 17 个状态

`idle, talk, happy, curious, thinking, caring, encouraging, walking, running, sitting, lying, sleepy, sleeping, welcome, accompany, wakeup, night`

## 重要体验原则

糖糖不是监控器。行为事件不应机械映射成“提醒”。例如 `screen.started` 本身不等于要说话；是否打扰由 Policy 决定，Character State 只负责决定视觉/动作状态。

夜间默认保持 `night` / `sleeping`，不因为普通低优先级事件突然切成说话或奔跑。
