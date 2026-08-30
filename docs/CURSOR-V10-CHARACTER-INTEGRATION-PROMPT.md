# Cursor 执行提示词：糖糖 V10 角色形象接入 V4

你现在负责把糖糖 V10 角色素材接入现有 V4 Presentation Layer。

基线分支：`cursor/v4-five-rounds-449b`
本任务分支：`feature/v4-character-assets-v10`

先阅读：

- `docs/V10-CHARACTER-ASSET-SPEC.md`
- `docs/V4-FINAL-REVIEW.md`
- 当前 AnimationController / Presentation Layer

## 第一原则

不要修改 V4 Brain。

不要把动画逻辑塞进 Brain。

最终数据流必须是：

```text
Event
 -> Brain
 -> Response
 -> PresentationAction
 -> AnimationController
 -> TangTang asset
```

## 素材整理

将新的糖糖 V10 素材放入：

```text
assets/character/tangtang/
```

建立统一 metadata：

```text
assets/character/tangtang/metadata.json
```

至少包含：

- animation name
- frame count
- fps
- loop
- anchor
- preferred state
- fallback state

## 动画

优先接入：

1. idle
2. blink
3. listen
4. happy
5. encourage
6. sad
7. walk
8. run
9. sit
10. lie
11. sleep

walk/run 必须使用连续帧，不允许用两个静态图片来回切换假装动画。

## 状态机

AnimationController 至少支持：

```text
IDLE
LISTEN
HAPPY
ENCOURAGE
SAD
WALK
RUN
SIT
LIE
SLEEP
```

并支持：

```text
interrupt
priority
loop
transition
fallback
```

例如：

```text
IDLE
 -> LISTEN
 -> HAPPY
 -> IDLE
```

睡觉时：

```text
SLEEP
 -> 不允许普通高频动作打断
```

## 防恐怖设计

必须保证：

- 不突然瞬移
- 不突然放大
- 不持续盯着用户
- 不高频闪烁
- 不在夜间播放剧烈动作
- 状态切换有过渡
- 图片尺寸/锚点统一

## V4 集成

如果发现现有代码存在：

```text
Brain -> image path
Brain -> TTS
Brain -> projector
```

不要直接删除。

通过 Adapter / Presentation Layer 迁移。

## 设备失败

动画素材缺失时：

```text
fallback -> idle
```

投影失败不能导致 Brain 崩溃。

## 测试

增加：

```text
tests/v4/test_tangtang_animation_controller.py
tests/v4/test_tangtang_animation_assets.py
tests/v4/test_tangtang_presentation.py
```

测试：

- 每个动画帧数正确
- 所有 PNG 可读取
- frame 尺寸统一
- anchor 稳定
- loop 正确
- walk 连续
- run 连续
- idle 不跳帧
- sleep 不闪烁
- 状态切换不会崩溃
- 缺素材自动 fallback
- Brain 不依赖具体图片文件

## 真实运行

如果 Mac 当前环境可以运行投影页面：

至少实际观察：

1. idle
2. listen
3. happy
4. walk
5. run
6. sleep

重点检查：

- 是否像一只真实小狗
- 是否自然
- 是否有“盯人”的恐怖感
- 是否出现图片跳动
- walk/run 是否真正连续

## Git

不要修改 main。

完成后提交：

```text
feat(v10): integrate TangTang character assets
```

必要时拆分为多个 commit。

最终生成：

```text
docs/V10-CHARACTER-INTEGRATION-REPORT.md
```

报告必须明确：

- 使用了哪些素材
- 哪些动画已接入
- 每个动画帧数
- AnimationController 修改点
- V4 Brain 是否保持不变
- 测试 PASS/FAIL/SKIP
- 真实设备测试情况
- 仍存在的问题

最后 push 当前分支并停止，不要自行 merge main。
