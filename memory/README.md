# memory — 记忆层

负责事件、今日记忆、近期趋势、长期习惯和重要记忆。

## 数据流

`event → today → trends → habits`

不要让 LLM 直接修改长期记忆；长期记忆必须经过规则/阈值与来源追踪。