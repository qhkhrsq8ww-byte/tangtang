# Character State Engine

糖糖先理解发生了什么，再决定自己现在是什么状态，再决定要不要说话，最后才由身体（视频）表现出来。

## 为什么存在

`cat-brain.EVENT_STATE` 和 `cat-mood.txt → switchState()` 会让业务事件直接开车。本引擎是**唯一**状态决策入口。

## 输入

Event（type / emotion / intent / scene / companion）  
Identity（member_id）  
Context（now, active_conversation）  
Policy（SPEAK / SILENT / DELAY / LOG_ONLY, quiet_hours）

**不得**把 utterance / transcript 交给引擎。

## 输出

`CharacterStateDecision`：state, priority, intensity, reason, interruptible, speech_allowed, transition_hint, self_state, social_state, presentation_state

再经 `CharacterPresenter` → `PresentationAction`（仍无 mp4 路径）。

`AssetRegistry` 只在 Presentation Layer 把 state 换成文件名。

## 优先级

100 睡眠/夜晚/Quiet Hours（22:30–07:00）  
90 明确互动  
80 对话  
70 情绪  
60 欢迎/到家  
50 活动  
30 日常  
10 idle  

低优先级不能覆盖高优先级。2 秒（重要状态更长）防抖动。

## 自己的情绪 vs 对孩子的反应

考砸了：self=calm, social=caring, presentation=caring  
考 100：self=happy, social=happy, presentation=happy  

## Legacy

`behavior/legacy_adapter.py` 把 cat-brain 旧事件变成 Event。  
`cat-mood.txt` 仍可写，但是 **legacy only**。生产读 `cat-presentation-action.json`。

## 隐私

引擎不存原话。PRIVATE 原话不得进 Family Summary / 普通 log / 其他成员 context。
