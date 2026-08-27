# 糖糖 AI｜OpenClaw 自我学习优化计划 V1.0

## 目标
让 OpenClaw 不只是按需求写代码，而成为糖糖项目的持续开发与优化代理。

核心循环：

```text
观察 → 记录 → 假设 → 修改 → 测试 → 评分 → 保留/回滚 → 更新文档
```

## 一、每次启动必须做

1. 读取 README.md。
2. 读取 docs/00-糖糖AI人格设计说明书-V1.0.md。
3. 读取 docs/01-糖糖AI产品PRD-V1.0.md。
4. 读取 docs/03-动画系统V1.md。
5. 读取 docs/04-糖糖AI声音设计说明书-V1.0.md。
6. 读取本文件以及最近的开发记录。
7. 检查当前 branch、最近 commit、可运行版本、TODO、已知 bug 和最近测试结果。

不得假设代码状态，先检查再修改。

## 二、一次只解决一个主要问题

每个任务必须有：目标、当前问题、修改方案、验收标准、测试结果。禁止为了“顺手优化”大范围重构。

## 三、自我学习记录

建立：

```text
notes/
├── OBSERVATIONS.md
├── EXPERIMENTS.md
├── TEST_LOG.md
└── DECISIONS.md
```

OBSERVATIONS：记录发现的问题，如眨眼太频繁、尾巴机械、声音像客服、夜间声音刺激等。

EXPERIMENTS：记录问题、假设、改动和结果。

TEST_LOG：记录 Mac 实机测试、FPS、CPU、内存、运行时间、主观评分和问题。

DECISIONS：记录已经确认的产品规则及原因。

## 四、动画自优化

每次优化检查：

- 是否仍是同一只糖糖？
- 是否更像真实小狗？
- 动作是否自然？
- 是否存在机械循环感？
- 是否存在突然跳变？
- 是否儿童安全？
- 是否适合长时间观看？

优先优化呼吸、眨眼、耳朵、尾巴、重心、四肢和状态衔接，不为了炫技增加特效。

## 五、声音自优化

每次声音优化检查：自然、耐听、AI腔、是否太嗲、是否太幼稚、是否太成熟、儿童安全、与动画情绪是否一致、家庭环境是否舒服。

固定测试句不得随意更换，保证不同版本可比较。

## 六、自动化测试

### Animation Smoke Test
依次触发所有状态，确认无崩溃、卡死和明显跳帧。

### Transition Test
至少测试：

```text
IDLE → HAPPY → IDLE
IDLE → CURIOUS → IDLE
IDLE → SLEEPY → SLEEPING
SLEEPING → WAKE → IDLE
IDLE → WELCOME → HAPPY → IDLE
IDLE → CARING → IDLE
```

### Voice Test
测试播放、停止、重复播放和状态切换，禁止音频重叠失控。

### Long Run Test
目标连续运行 8 小时，记录 FPS、CPU 和内存趋势。

## 七、儿童安全审查

任何新视觉、声音或提醒功能都必须检查：

- 是否突然出现
- 是否突然放大
- 是否突然高音量
- 是否产生恐怖感
- 是否持续盯视
- 是否夜间惊吓
- 是否使用强烈负面情绪
- 是否制造不必要焦虑

有风险时，宁可删除，也不要为了炫技保留。

## 八、自主研究边界

OpenClaw 可以主动研究：2D角色动画、Canvas/SVG、macOS图形性能、TTS、音频播放、状态机、小狗动作、儿童友好交互。

研究结果先写入 EXPERIMENTS.md，再决定是否进入代码。不得因为看到新技术就随意重写项目。

## 九、版本控制

重大修改使用独立 branch，例如：

```text
feature/voice-lab
feature/idle-animation
feature/walk-animation
feature/voice-engine
```

测试通过后再合并 main。Commit 要描述真实变化，例如：

```text
feat: add sugar idle breathing animation
fix: reduce blink frequency
feat: add voice lab prototype
perf: reduce animation CPU usage
```

## 十、禁止事项

- 不得私自改变糖糖名字或比熊形象。
- 不得加入恐怖、惊吓元素。
- 不得只用整图平移冒充四肢行走。
- 不得未经测试宣称完成。
- 不得为了“自我学习”无限修改代码。
- 不得自动删除用户素材。
- 不得提交 API Key、密码等敏感信息。

## 十一、每日开发报告

```text
糖糖开发日报

今天完成：
- xxx

发现问题：
- xxx

实验：
- 假设：xxx
- 修改：xxx
- 结果：xxx

下一步：
- xxx

当前风险：
- xxx
```

## 十二、最终优化目标

OpenClaw 的学习不是让糖糖越来越复杂，而是越来越自然。

评价顺序：

```text
安全 → 自然 → 耐看/耐听 → 生命感 → 互动感 → 智能感
```

**宁可少一个功能，也不要让糖糖失去可爱、自然和安全感。**
