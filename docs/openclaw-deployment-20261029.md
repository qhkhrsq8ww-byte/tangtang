# 本机 OpenClaw 智能体部署报告（2026-10-29）

## 结论

**生产实例 = AutoClaw 内嵌网关（OpenClaw 2026.6.8，127.0.0.1:18789）**——低功耗持续运行已就绪（AutoClaw 托管、随 App 自启）。独立网关部署经三轮实测在 2014 硬件上不可行（启动卡死），已停用留档；独立 CLI 2026.6.35 保留为命令行工具。

## 三层格局（最终态）

| 层 | 版本 | 形态 | 状态 |
|---|---|---|---|
| 生产网关 | OpenClaw 2026.6.8 | AutoClaw 内嵌（18789，loopback） | ✅ 常驻运行（Control UI 200） |
| 命令行工具 | OpenClaw 2026.6.35 | ~/.openclaw-cli（346MB） | ✅ 可用（本机 Node 22 天花板版本） |
| 独立网关 | 2026.6.35 | 计划 LaunchAgent 常驻（18790） | ⛔ 兼容性卡死，已停用留档 |

## 独立网关部署尝试记录（三轮诊断）

1. 配置就绪：~/.openclaw/openclaw.json（gateway.mode=local、port 18790、loopback、token 认证、GLM bigmodel 直连 providers）
2. PATH 修复：launchd 环境 node 缺失 → 已指向内嵌 runtime node
3. **最终卡点**：进程存活（RSS 107MB）但 15+ 分钟不监听 18790——macOS sample 采样显示卡在文件扫描循环（openclaw.sqlite 初始化阶段）。2026.6.35 独立网关与 2014 硬件/Big Sur 组合不兼容。
4. 清理残留的操作触发 AutoClaw Safety Guard 拦截（含文件删除类命令），需人工执行（命令见下）。

## 人工清理命令（如需彻底移除独立网关残留）

```bash
launchctl bootout gui/501/com.openclaw.gateway
kill 60866
rm -f ~/Library/LaunchAgents/com.openclaw.gateway.plist
```
（保留 ~/.openclaw/openclaw.json 与 ~/.openclaw-cli——未来新硬件可直接启用）

## 糖糖与 OpenClaw 的关系（不受影响）

- 糖糖云脑走智谱直连（cat-chat.py），不依赖独立网关
- 糖糖四代理（cat-server/proactive/usage/schedule）+ 周末三代理正常运行
- 设备管控、统计、唤醒链路全部独立于本次部署尝试

## 版本天花板（持续有效）

npm latest 2026.10.8 需 Node ≥24.22.1（本机 Node 22.22.3，Node 24 在 Big Sur 崩溃）；2026.6.35（Node ≥22.19）= 本机可运行上限。升级路径：换新硬件/VPS。
