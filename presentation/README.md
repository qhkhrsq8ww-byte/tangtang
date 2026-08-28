# presentation — 表现层

负责 TTS、动作 ID、PNG 播放、投影输出。V10 只升级角色素材，不改 V4 Brain。

## 数据流

```text
Event → Brain → Response → PresentationAction → AnimationController → assets/character/tangtang/
```

上层只产生稳定动作 ID（`idle` / `happy` / `walk` / `run` / …）。
Brain 不引用具体 PNG 路径。

## V10 角色

- 视觉基准：`assets/character/tangtang/TangTang-V10-character-design-sheet.png`
- 元数据：`assets/character/tangtang/metadata.json`
- 控制器：`presentation/animation_controller.py`
- 动画实验室：`presentation/animation_lab.html`（16:9 投影画布 1920×1080，角色 512×512）

本地预览（不是新微服务）：

```text
python3 -m http.server 8765
# 打开 http://127.0.0.1:8765/presentation/animation_lab.html
```
