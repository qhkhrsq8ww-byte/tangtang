# presentation — 表现层

负责 TTS、动作 ID、视频/PNG 播放、投影输出。

## 解耦原则

上层只产生稳定动作 ID，例如 `idle`、`happy`、`caring`、`walk`、`run`。

表现层通过媒体注册表决定实际资源。未来短视频优先，PNG/SVG作为辅助和 fallback。