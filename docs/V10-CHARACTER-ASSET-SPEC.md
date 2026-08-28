# 糖糖 V10 角色形象与动画素材规范

## 目标

V10 不改变 V4 Brain，只升级 Presentation Layer 的角色素材。

核心原则：糖糖像一只真实生活在家里的小狗，而不是始终盯着人的 AI 头像。

## 角色基准

- 名称：糖糖 / TangTang
- 品种视觉：奶油白、蓬松的小型比熊风格
- 年龄感：幼犬、约 3 岁人类幼犬感
- 气质：温柔、活泼、聪明、亲近、不吓人
- 识别特征：**浅蓝色领巾 + 金色骨头吊牌**（设计总图为准）
- 眼睛：大而有神，但避免过度放大和持续直视
- 表情：自然、柔和、轻微夸张
- 风格：warm / soft / family / child-friendly / real-puppy / low-stimulation。禁止 cyber / robot / uncanny。

## 领巾冲突（必须跟总图）

| 来源 | 配件 | 处理 |
| --- | --- | --- |
| 设计总图 `7f1d68cd-…png` | 浅蓝领巾 + 金骨头牌 | **唯一视觉主** |
| 3/4 产品渲染 `635e951c-…png` | 黄色皮革项圈 + 金骨头牌 | 冲突，**不采用** |
| 备用规格图 `b859ebb7-…png` | 浅蓝领巾 | 与总图一致，作补充 |

运行时 PNG 全部使用蓝领巾。黄项圈原图保存在 `assets/character/tangtang/v10/reference/tangtang-34-render-yellow-collar-CONFLICT.png`。

## 视角

`assets/character/tangtang/v10/base/`：

1. 正面 `front.png`
2. 3/4 左前 `three_quarter_left.png`
3. 左侧 `left.png`
4. 3/4 左后 `three_quarter_back_left.png`
5. 背面 `back.png`
6. 3/4 右后 `three_quarter_back_right.png`
7. 右侧 `right.png`
8. 3/4 右前 `three_quarter_right.png`
9. 低头 `look_down.png`
10. 抬头 `look_up.png`
11. 歪头 `tilt_left.png` / `tilt_right.png`
12. 坐下 `sit.png` / 趴下 `lie.png`

## 核心动画（V10 正式包）

路径：`assets/character/tangtang/v10/animations/<name>/<name>_01.png …`

| 动画 | 帧数 | FPS | loop | 说明 |
| --- | ---: | ---: | --- | --- |
| idle | 16 | 12 | yes | 呼吸 + 眨眼 + 耳/尾微动 |
| listen | 12 | 12 | yes | 转头、竖耳、歪头 |
| happy | 12 | 16 | yes | 摇尾巴、身体轻晃 |
| walk | **12** | 12 | yes | **真实步态周期，12 个不同 hash** |
| run | **12** | 18 | yes | **真实跑步周期，12 个不同 hash** |
| trot | 12 | 15 | yes | 小跑步态 |
| sleep | 12 | 8 | yes | 卷曲闭眼呼吸 |
| get_up | 8 | 12 | no | 睡 → 伸懒腰 → 站起 |

不允许「同一张静帧复制 12 次」冒充走路/跑步。

## 帧素材要求

- 透明 PNG（RGBA）
- 画布统一 **512×512**
- 角色比例 / 锚点统一（脚底约 y=0.957，水平居中）
- 不得出现帧间跳动、突然放大、瞬移
- 不得改变领巾、吊牌、毛色
- 不使用 GIF 作为运行时主素材
- 推荐 15–30 FPS 上限；睡眠更慢

## 运行时结构

```text
Brain
  -> Response / PresentationAction
  -> AnimationAction
  -> AnimationController
  -> AssetManifest (v10/manifest.json)
  -> FrameRenderer
  -> assets/character/tangtang/v10/...
```

Brain 不直接引用具体图片路径。TTS / 投影 / 动画解耦：TTS 失败 ≠ 停动画。

`manifest.json` 每个动画包含：`frames` `fps` `loop` `anchor` `width` `height` `files`。

## 目录

```text
assets/character/tangtang/v10/
├── base/
├── expressions/
├── animations/
│   ├── idle/      idle_01.png … idle_16.png
│   ├── listen/    listen_01.png … listen_12.png
│   ├── happy/     happy_01.png … happy_12.png
│   ├── walk/      walk_01.png … walk_12.png
│   ├── run/       run_01.png … run_12.png
│   ├── trot/      trot_01.png … trot_12.png
│   ├── sleep/     sleep_01.png … sleep_12.png
│   └── get_up/    get_up_01.png … get_up_08.png
├── actions/
├── scenes/
├── reference/     设计总图与冲突说明
└── manifest.json
```

旧包 `assets/character/tangtang/{idle,walk,run,…}` + `metadata.json` 仍保留，供既有 Animation Lab 使用。V10 正式包是 `v10/`。

## 状态机过渡（100–200ms crossFade）

```text
idle ↔ listen ↔ happy
idle → walk → run → idle
idle → sleep → get_up → idle
```

睡觉时不允许普通高频动作直接打断，需经 `get_up`。

## 防恐怖 / 像真小狗

- 不持续直视用户
- 不突然瞬移 / 放大脸
- 不高频闪烁
- 夜间降低剧烈动作（walk/run/trot/happy 软化为 sit/idle）
- 观察 → 转头 → 判断 → 动作

## 版本策略

V10 只升级角色表现层，不修改：

- EventBus
- Memory
- PrivacyPolicy
- Context
- Decision
- Family Brain

演示页：`presentation/v10-character-demo.html`。测试：`tests/v4/test_character_assets.py`。
