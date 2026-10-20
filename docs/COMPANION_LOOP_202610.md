# 糖糖生活伙伴闭环改进（2026-10）

## 1. 每日计划与习惯标签联动

- 新增 `core/companion/daily_plan.py` 与 `code/cat/cat-plan.py`。
- 计划可以按成员、日期、类别、时间记录；带时间的计划会创建现有 `TaskService` 私人任务。
- 完成反馈会关闭对应任务，并将“完成/部分完成/跳过/不适用”映射为现有习惯系统的粗粒度标签（joined/defer/silent/skip）。
- 不采集原始对话，不把语音转写、提示词或音频写入计划记录。
- 命令示例：
  `./cat.sh plan add --member hanghang --date 2026-10-21 --title "读英语10分钟" --category habit --time 19:30`
  `./cat.sh plan list --member hanghang --date 2026-10-21`
  `./cat.sh plan reflection --member hanghang --date 2026-10-21`
  `./cat.sh plan feedback PLAN_ID --member hanghang --result completed`

## 2. 主动关怀与冷却

- 新增 `core/companion/proactive.py` 和 `code/cat/cat-proactive-gate.py`。
- V4 客厅主动场景在输出语音前，先检查既有习惯标签、安静时段和同一成员/场景的冷却时间；默认冷却 45 分钟。
- 冷却记录只存成员/场景键和时间戳，不存话术或原始对话。
- 配置：`TANGTANG_SCENE_COOLDOWN_MINUTES`（5–360 分钟）、`TANGTANG_QUIET_START`、`TANGTANG_QUIET_END`。
- 已有场景决策仍负责最终文案；本层只负责是否开口，不替代安全与场景策略。

## 3. 定时派发闭环

- `cat-task-dispatch.py --deliver` 追加最小化运行记录至本机 `tasks/dispatch-health.jsonl`，只记时间、运行模式、统计、结果，不写任务标题或语音内容。
- 新增 `cat-task-health.py`，核对 crontab 是否安装、最近实际派发记录是否超过 3 分钟、失败任务是否待处理。
- 命令：`./cat.sh task-health` 或 `./cat.sh task-health --json`。
- 安装检查只读取当前用户 crontab；不会自动覆盖或修改用户的 crontab。
- “命令成功”仅代表本机播放命令返回成功，不代表孩子实际听见。中断的 running 任务仍标记为结果不确定并要求人工核查，不自动重播。
- 默认 PRIVATE 的任务不会在公共音箱播报具体内容，只发通用本机通知并进入待确认；健康检查会把待确认任务列为需跟进，避免将“有运行记录”误报成“提醒已送达”。只有明确设置为 FAMILY 的任务才允许在共享空间播报内容。

## 验收边界

代码与自动化测试通过后，仍需在家庭 Mac 上手动检查：生成的 crontab 是否已合并、Mac 是否处于唤醒状态、声音输出设备是否正确，以及语音是否真的能听见。云端 CI 无法替代这些硬件和登录会话验证。
