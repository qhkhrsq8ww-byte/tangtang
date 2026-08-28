# 糖糖 V10 角色形象与动画素材规范

## 目标

V10 不改变 V4 Brain，只升级 Presentation Layer 的角色素材。

核心原则：糖糖像一只真实生活在家里的小狗，而不是始终盯着人的 AI 头像。

## 角色基准

- 名称：糖糖 / TangTang
- 品种视觉：奶油白、蓬松的小型比熊风格
- 年龄感：幼犬、约 3 岁人类幼犬感
- 气质：温柔、活泼、聪明、亲近、不吓人
- 识别特征：蓝色领巾 + 金色骨头吊牌
- 眼睛：大而有神，但避免过度放大和持续直视
- 表情：自然、柔和、轻微夸张

## 视角

基础素材至少包含：

1. 正面
2. 左 3/4
3. 右 3/4
4. 左侧面
5. 右侧面
6. 背面
7. 低头
8. 抬头
9. 歪头
10. 趴下
11. 坐下

## 核心动画

第一优先级：

- idle：呼吸 + 轻微耳朵/身体动作
- blink：自然眨眼
- listen：听到声音后转向 + 歪头
- happy：开心 + 摇尾巴
- encourage：温柔鼓励
- sad：低头/耳朵下垂，避免哭泣恐怖表情
- walk：12 帧连续动画
- run：12 帧连续动画
- sit：8 帧
- lie：8 帧
- sleep：8 帧呼吸循环

## 帧素材要求

- PNG
- 透明背景
- 尺寸统一
- 角色比例统一
- 锚点统一
- 不得出现帧间跳动
- 不得改变领巾、吊牌、毛色等核心识别元素
- 不使用 GIF 作为运行时主素材

## 运行时结构

```text
Brain
  -> Response
  -> PresentationAction
  -> AnimationController
  -> character/tangtang/<animation>/<frame>.png
```

Brain 不直接引用具体图片路径。

## 推荐目录

```text
assets/character/tangtang/
├── base/
├── angles/
├── expressions/
├── idle/
├── blink/
├── listen/
├── happy/
├── encourage/
├── sad/
├── walk/
├── run/
├── sit/
├── lie/
├── sleep/
└── metadata.json
```

## 动画体验原则

### 不恐怖

- 不持续直视用户
- 不突然瞬移
- 不突然放大脸部
- 不使用高频闪烁
- 夜间降低动作幅度
- 睡眠状态保持柔和呼吸

### 像真实小狗

动作应遵循：

观察 -> 转头 -> 判断 -> 动作

而不是：

收到事件 -> 立即播放夸张动作

## 当前生成素材

本轮已生成一张 V10 角色设计总览图，作为 Cursor 制作/整理素材时的视觉基准。

文件建议命名：

`TangTang-V10-character-design-sheet.png`

## 版本策略

V10 只升级角色表现层，不修改：

- EventBus
- Memory
- PrivacyPolicy
- Context
- Decision
- Family Brain

如需新增动作，只增加 AnimationController 与素材，不改变 Brain API。
