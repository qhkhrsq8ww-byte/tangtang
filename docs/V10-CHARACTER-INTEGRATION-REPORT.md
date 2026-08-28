# 糖糖 V10 角色形象接入报告

**Branch:** `feature/v4-character-assets-v10`  
**Base:** `cursor/v4-five-rounds-449b`  
**Not merged to main.** V4 Brain (`core/` EventBus, Memory, Privacy, Policy, Context, Response orchestrator) unchanged.  
`data/family.json` not overwritten. `code/cat/cat-vp.py` / `cat-chat.py` not deleted.

视觉基准：当前 V10 角色设计总图（浅蓝色领巾 + 金色骨头吊牌，奶油白比熊）。

---

## 使用了哪些素材

根目录：`assets/character/tangtang/`

| 路径 | 内容 |
| --- | --- |
| `TangTang-V10-character-design-sheet.png` | 设计总图（视觉基准） |
| `metadata.json` | animation name / frame count / fps / loop / anchor / preferred state / fallback |
| `base/` + `angles/` | 五角度：正面、3/4 左、左侧、背面、3/4 右；512 / 256 / 128 |
| `expressions/` | 默认、开心、眨眼、歪头、鼓励、期盼、难过、睡眼 |
| `idle/` `blink/` `listen/` `tilt/` `happy/` `encourage/` `sad/` `sit/` `lie/` `sleep/` | 各状态 pose still（编号 `00.png`） |
| `walk/` | **12 帧**侧视连续走循环（非两帧来回切） |
| `run/` | **8 帧**侧视连续跑循环（规格要 12，缺 4 帧） |
| `interactive/` | 转向声音、等待、摇尾、张望 |
| `effects/` | 爪印、心、星、骨头 |
| `backgrounds/living_room_cream.png` | 16:9 客厅底 |

**正式 pack PNG 数：170**（不含工作区里可能出现的未入库 `v10/` 沙箱）。  
**规格目标：368。** 未用随机像素凑数。

仓库里没有现成 368 张 PNG / zip / LFS；`feature/v4-character-assets` 远程也不存在完整序列。总图 819×546，无法裁出 512 运行时帧。本轮按总图生成并 chroma-key 为透明 PNG。

旧 `code/cat/assets/tangtang-*.png`（黄项圈）**没有**当作 V10 主素材。

---

## 已接入动画

| 动画 | 规格帧数 | fps | loop | 本轮落地 512 文件 | 连续？ |
| --- | ---: | ---: | --- | ---: | --- |
| idle | 8 | 8 | yes | 1 | pose still；播放时按序 hold，不跳帧 |
| blink | 6 | 10 | no | 1 | still |
| listen / tilt | 8 | 8 | no | 1 | still（先转头再行动） |
| happy | 8 | 10 | no | 1 | still；夜间降为 idle |
| encourage | 8 | 8 | no | 1 | still |
| sad | 8 | 6 | no | 1 | still |
| walk | 12 | 12 | yes | **12** | **连续侧视循环** |
| run | 12 | 12 | yes | **8** | 连续；缺 4 帧 in-between |
| sit | 8 | 8 | no | 1 | still |
| lie | 8 | 8 | no | 1 | still |
| sleep | 8 | **4** | yes | 1 | 低 fps，不闪烁 |

状态机：`IDLE LISTEN HAPPY ENCOURAGE SAD WALK RUN SIT LIE SLEEP`  
支持 interrupt / priority / loop / transition / fallback。  
`SLEEP` 时普通高频动作（blink / listen / happy / walk…）不能打断；需 `force` 或 priority ≥ 9。  
夜间 22:30–07:00：walk/run → sit，happy → idle。  
Idle 默认 3/4 左，避免持续正面盯人。投影画布 **1920×1080**，角色 **512×512**，scale **1.0**，锚点底部中心。

---

## AnimationController 修改点

此分支原先 **没有** AnimationController（不在 `core/`）。本轮只加在表现层：

- `presentation/animation_controller.py` — 播片、缺帧 fallback idle、`play_safe` / `project_safe` 隔离
- `presentation/state_machine.py` — 状态 + sleep lock
- `presentation/mapping.py` — Event + PresentationAction → AnimationAction（观察→转头→判断→动作）
- `presentation/registry.py` — 读 `metadata.json`
- `presentation/animation_lab.html` — 16:9 实验室 / 投影预览
- `presentation/tools/pack_v10_frames.py` — chroma-key / 切片工具

数据流：

```text
Event → Brain → Response → PresentationAction → AnimationController → PNG
```

Brain 不引用图片路径。投影失败不丢 Event、不崩 Brain。

---

## V4 Brain 是否保持不变

**是。** `git diff origin/cursor/v4-five-rounds-449b -- core` 为空。  
未改 EventBus / Memory / PrivacyPolicy / Context / InterruptPolicy / ResponseOrchestrator。

---

## 测试

命令：`python3 -m unittest discover -s tests/v4 -t . -v`

| 结果 | 数量 |
| --- | ---: |
| PASS | **215** |
| FAIL | **0** |
| SKIP | **0** |

其中 V10 新增：

- `tests/v4/test_tangtang_animation_controller.py`
- `tests/v4/test_tangtang_animation_assets.py`
- `tests/v4/test_tangtang_presentation.py`

覆盖：声明帧数、PNG 可读、512/256/128 尺寸、锚点、loop、walk/run 连续且非两帧 ping-pong、idle 不跳帧、sleep 不闪烁、缺素材 fallback、投影失败隔离、Brain 不依赖 PNG。

---

## 真实设备

**SKIP** — 当前是 Linux Cloud Agent，没有 Mac Air + 投影。未在客厅实机看 idle/listen/happy/walk/run/sleep。  
可用：`python3 -m http.server 8765` 后打开 `/presentation/animation_lab.html`。

---

## 仍存在的问题（P1）

1. **368 − 170 = 198 张未到。** 缺的主要是 idle/blink/listen/happy/encourage/sad/sit/lie/sleep 的 8 帧呼吸/过渡 in-between，以及 run 的第 9–12 帧；再乘 256/128。
2. Walk 从 12 格横条切片，重叠处个别帧可能裁切不完整。
3. 未做 Mac 投影实机观感（盯人 / 跳动 / 像不像真小狗）。
4. 工作区可能出现未入库的 `assets/character/tangtang/v10/` 沙箱（黑斑/斑点狗），**未采用**，以免覆盖总图白比熊。

不启动 V5，不改 main。
