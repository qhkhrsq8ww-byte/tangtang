# presentation — 表现层

负责 TTS、动作 ID、PNG 播放、投影输出。V10 只升级角色素材，不改 V4 Brain。

## 数据流

```text
Event → Brain → Response → PresentationAction → AnimationAction → AnimationController → AssetManifest → FrameRenderer
```

上层只产生稳定动作 ID（`idle` / `happy` / `walk` / `run` / …）。
Brain 不引用具体 PNG 路径。TTS / 投影 / 动画相互解耦：TTS 失败不会停动画。

## V10 角色

- 视觉基准：`assets/character/tangtang/TangTang-V10-character-design-sheet.png`
- 旧包元数据：`assets/character/tangtang/metadata.json`
- V10 正式包：`assets/character/tangtang/v10/manifest.json`（idle16 / listen12 / happy12 / walk12 / run12 / trot12 / sleep12 / get_up8）
- 控制器：`presentation/animation_controller.py`
- 动画实验室：`presentation/animation_lab.html`
- V10 演示：`presentation/v10-character-demo.html`（按钮 Idle Listen Happy Walk Run Trot Sleep Get Up；桌面显示 FPS/Frame/Animation/Loop/Speed；`?projection=1` 或 `?phone=1` 隐藏调试）

本地预览（不是新微服务）：

```text
python3 -m http.server 8765
# 打开 http://127.0.0.1:8765/presentation/animation_lab.html
```
