# 糖糖 V10 角色资产接入报告

分支：`cursor/v4-character-v10-449b`  
父分支：`feature/v4-character-assets-v10`（五轮评审线 + 已有较薄 V10 包）。不改 `main`，不改 V4 Brain。

## 做了什么

在既有 `feature/v4-character-assets-v10` 上**续做**，没有另起一套半成品树：

1. 新增正式包 `assets/character/tangtang/v10/`（设计总图蓝领巾）。
2. 扩展 `AnimationController`：play/stop/pause/resume/loop/setSpeed/crossFade(100–200ms)/transition。
3. 新增 `AssetManifest` + `FrameRenderer`。
4. 走/跑各 12 帧真实步态（SHA-256 互不相同）。
5. `tests/v4/test_character_assets.py` + 全量 V4 unittest / pytest。
6. 演示页 `presentation/v10-character-demo.html`。

数据流：

```text
Brain → AnimationAction → AnimationController → AssetManifest → FrameRenderer
```

## 资产计数

| 类别 | 数量 |
| --- | ---: |
| V10 运行时 PNG（不含 reference） | **138** |
| idle / listen / happy / walk / run / trot / sleep / get_up | 16+12+12+12+12+12+12+8 = **96** |
| base 八向 + 低头抬头歪头坐趴 | **16** |
| expressions | **12** |
| actions | **8** |
| scenes | **6** |
| reference（总图/冲突图/条带裁切） | 7 PNG + 1 说明 |
| 旧包 PNG（`assets/character/tangtang/` 非 v10，测试跳过 v10） | 170 |

Walk **真正 12 帧**：是（12 个不同 hash）。  
Run **真正 12 帧**：是（12 个不同 hash）。  
Idle **真正 16 帧**：是。

## 每动画 FPS / loop / 尺寸

| 动画 | 帧 | FPS | loop | 画布 | 透明 |
| --- | ---: | ---: | --- | --- | --- |
| idle | 16 | 12 | yes | 512×512 RGBA | 是 |
| listen | 12 | 12 | yes | 512×512 RGBA | 是 |
| happy | 12 | 16 | yes | 512×512 RGBA | 是 |
| walk | 12 | 12 | yes | 512×512 RGBA | 是 |
| run | 12 | 18 | yes | 512×512 RGBA | 是 |
| trot | 12 | 15 | yes | 512×512 RGBA | 是 |
| sleep | 12 | 8 | yes | 512×512 RGBA | 是 |
| get_up | 8 | 12 | no | 512×512 RGBA | 是 |

锚点：`{x: 0.5, y: 0.957}`（脚底贴齐，水平居中）。绿幕抠图后去底，避免白毛被误消。

## 一致性

- 配件跟**设计总图**：浅蓝领巾 `#A8D5FF` + 金骨头牌 `#F5C84B`。
- 3/4 产品渲染的**黄项圈**视为冲突，未进入运行时帧。
- 旧包 `metadata.json` 仍声明 idle=8 / run 缺 4 帧 in-between；V10 正式包补齐。既有 `test_tangtang_animation_*.py` 未削弱。

## 测试

```text
python3 tests/v4/run.py     → 227 tests OK
python3 -m pytest tests/v4  → 227 passed
```

`test_character_assets.py` 覆盖：manifest 字段、文件存在、PNG+alpha、统一尺寸、idle16 / walk12 / run12 不同 hash、控制器不抛、缺帧不打崩 Brain、TTS 失败不停动画。

## 已知问题

- 总图本身只有 1024×683，条带裁切不能当 512 运行时帧；运行时序列由总图风格生成后再抠绿幕。`reference/sheet_*` 只作出处。
- 骨头牌上的字各帧不完全统一（偶发 CITI / TANG 等），需要人类重绘铭牌。
- 绿幕边缘仍可能有少量溢色；毛发发丝级抠图未做人工精修。
- 旧包 run 仍是 8 帧（测试只要求 ≥8）；V10 包已是 12。
- 本环境无浏览器自动化，演示页未做实机投影观察。本地：`python3 -m http.server 8765` 打开 `/presentation/v10-character-demo.html`。手机/投影加 `?phone=1` / `?projection=1` 隐藏调试 HUD。

## 仍需人类出图

1. 铭牌统一刻「糖糖」+ 爪印，全帧一致。
2. 走/跑/小跑的侧向与背面循环（当前步态是 3/4 向右）。
3. 发丝级去绿边、统一阴影。
4. sit / lie / encourage / sad 的完整 8 帧过渡（现有 base/actions 静帧 + 旧包 pose still）。
5. 客厅投影实机：idle / listen / happy / walk / run / sleep，确认无盯人恐怖感、无跳帧。

## Brain

未修改 `core/memory` `core/context` `core/policy` `core/events/event_bus`。表现层失败被 `isolate`。
