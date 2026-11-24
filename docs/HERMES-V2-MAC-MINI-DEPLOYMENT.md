# Mac mini M6 部署设计（糖糖 V2）

> 状态：部署规划，尚未在用户设备实测。
> 资源规划暂按此前讨论的 24GB 内存 / 256GB SSD 假设；以实际购机配置和 macOS 版本复核。

## 1. 部署原则
- macOS 原生部署优先，不预设 Docker。
- Hermes 与 TangTang Core 分离运行、分离配置、分离日志。
- Python 使用独立虚拟环境；Node/其他运行时按 Hermes 官方当前版本要求锁定。
- Gateway 仅允许一个受控实例。
- 云端模型优先；本地模型不是启动前置条件。
- 不迁移旧机器的绝对路径、LaunchAgent 标签、token、缓存和用户目录配置。
- 家庭敏感数据不进入代码仓库。

## 2. 建议目录（示意）
```text
/Users/<service-user>/tangtang/
  app/                 # Git checkout / application code
  .venv/               # Python virtual environment
  config/              # local-only configuration
  data/                # family data, private memories
  assets/              # approved local media
  logs/                # TangTang logs
  backups/              # encrypted backups

/Users/<service-user>/.hermes/
  config/              # Hermes config, local-only
  logs/                # Hermes logs
  sessions/            # Agent sessions, policy controlled
```
目录最终位置需依据 macOS 账户和磁盘布局决定；示意路径不得直接复制成生产配置。

## 3. 资源与存储
- 256GB SSD 需要预留 macOS、开发工具、模型缓存和日志空间。
- 不建议把大模型权重长期堆在内置 SSD；优先云端模型。
- 日志设轮转和保留上限。
- 语音原始文件默认不长期保存；若业务需要保留，必须单独配置期限和权限。
- 备份家庭数据时加密，并定期做恢复演练。
- 监控磁盘可用空间、内存压力、CPU、进程重启次数和 Agent 调用延迟。

## 4. 服务管理
先确认实际采用的 Hermes 运行形态：CLI 单轮调用、Desktop/Backend（`hermes serve`）、消息平台 Gateway 和 API Server 是不同概念。Hermes API Server 由 `hermes gateway` 进程承载（设置 `API_SERVER_ENABLED=true` 或 `gateway.api_server.enabled: true`），不是 `hermes serve` Desktop backend，也不是 MCP Server mode。第一阶段只启用本机 API Server，不配置外部消息渠道。

如确需常驻 Backend 或消息 Gateway，再确认官方支持的 macOS 服务安装方式，并选择一个服务管理者；不得同时启用两个自启动管理器。

TangTang Core 可独立由 LaunchAgent 管理，建议：
- 独立 plist 和日志。
- KeepAlive/重启策略需避免崩溃循环。
- 标准输出/错误输出写入受限日志目录。
- 环境变量只引用本机安全配置，不写密钥常量。
- 健康检查只读，不触发设备操作。

## 5. 网络与远程维护
- Hermes Backend/Gateway 如需监听网络，默认仅 loopback；如确需局域网访问，必须启用认证并限制来源。
- 不直接将 Gateway 或家长管理页面暴露公网。
- MacBook Air 远程维护走 VPN/零信任网络，使用单独管理身份。
- 远程维护权限与孩子日常对话权限分离。
- 生产环境不开放任意 shell 工具给 Agent。
- 初始 Hermes 配置建议关闭内置持久记忆（memory.memory_enabled=false、memory.user_profile_enabled=false），并启用 skills.write_approval=true、approvals.mode=manual、cron_mode=deny、single_query_mode=deny、unattended_mode=deny；具体键名以锁定版本官方配置校验为准。
- 若采用 Hermes API Server，必须通过 `agent.disabled_toolsets` 关闭不需要的内置工具；`platform_toolsets.api_server` 仅用于筛选 MCP 服务器，不能替代内置工具禁用。启动后通过 `/v1/toolsets` 验证实际启用清单；未完成最小权限验证前不得接入真实家庭数据。
- API Server 必须绑定 127.0.0.1、设置强随机 API_SERVER_KEY、关闭不需要的 CORS；不暴露公网。
- Hermes memory/skill 写入审批不等于文件系统隔离，必须同时限制 Terminal、File Operations 和 MCP 工具集。

## 6. 部署步骤
1. 在 TangTang 仓库目录运行 `bash scripts/hermes-m6-preflight.sh`，收集系统版本、芯片架构、内存、磁盘和运行时状态；该脚本只读。
2. 根据预检结果确认 Mac mini 的实际硬件配置、macOS 版本和可用磁盘空间。
3. 安装系统更新和必要开发工具。
4. 创建项目目录和独立 Python 环境。
5. 从 GitHub 克隆当前稳定分支。
6. 安装锁定版本的 TangTang 依赖并跑离线测试。
7. 按 Hermes 官方文档安装并锁定版本。
8. 配置模型凭证，验证单轮对话。
9. 验证服务启停、重启恢复、日志和资源。
10. 完成备份后，才导入脱敏/最小化的测试数据。
11. 通过阶段验收后再接真实家庭数据和设备。

## 7. 回滚
- Hermes 与 Core 独立部署，可分别停用。
- Agent Adapter 有 feature flag；关闭后回退至现有 Core 处理路径。
- 保留旧配置只读备份，不把旧机器密钥复制到新主机。
- 切换前导出并校验 Core 数据备份。
- 回滚不得覆盖更新的家庭数据；恢复前先做快照。
