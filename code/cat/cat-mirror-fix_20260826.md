# 糖糖 · Mac 配置体检 & 投屏遮挡修复（2026-08-26 22:41）

## 用户问题
> 「检查一下 mac 的配置，投屏的时候会有设置弹窗出来，遮挡投屏」

## 配置体检（本机 macOS 11.7.11 Big Sur）
- 当前**已经在镜像状态**（`system_profiler` → `Mirror: On / Hardware Mirror`）。
- 投影仪 AirPlay 端口 `61949` 在线 → 投屏通道正常。
- 屏幕镜像图标已在**菜单栏**（`NSStatusItem Visible ScreenMirroring = 1`）→ 用菜单栏小下拉即可开关，不盖屏。
- 无 `displayplacer`/`cliclick`，但 **brew 可用**（Homebrew 6.0.18）。

## 遮挡根因
旧版 `cat.sh` / `start-cat.sh` 每次走投屏模式都执行 `open ".../Displays.prefPane"`，
即**每次猫说话都强行重开「系统设置-显示器」全屏窗口**，该窗口会镜像到投影仪上盖住内容。

## 修复
- 去掉强制弹 `Displays.prefPane`。
- 新增 `mirroring_on()`：检测到已在镜像 → **什么都不弹**。
- 仅当完全没连镜像时，在终端打印一句提示（不弹窗），引导用菜单栏『屏幕镜像』图标选投影。
- `start-cat.sh` 同步去掉弹窗，改为文字提示用菜单栏小窗。

## 复测结论
- `bash -n` 语法 OK。
- 投屏在线时 `./cat.sh "..."` → 走 pet 模式，**无任何 Displays 设置窗口**。
- `./cat.sh -f` 纯声音模式 → 也无弹窗。
- 投屏改用：菜单栏『屏幕镜像』图标(顶部右侧) → 选 OBE_R3Ultra 旗舰版(OBE)501（下拉小窗，不遮挡）。

## 可进阶（未做，按需）
- 装 `displayplacer` / `cliclick` 后可脚本化一键连/断镜像，做到完全无手动点击。
