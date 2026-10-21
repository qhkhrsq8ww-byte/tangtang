# 糖糖家庭路由器设备管控（MiWiFi / R3D）

## 当前实现范围

- 适配器只访问家庭 LAN 内配置的私有 IPv4 地址，默认 `http://192.168.31.1`。
- 设备清单使用 MiWiFi `/api/misystem/devicelist`；网络访问开关使用 `/api/xqsystem/set_mac_filter`。这些接口来自社区整理的 MiWiFi API 参考，必须以本机 R3D 固件实测为准。
- 设备清单为只读操作。修改联网权限默认关闭，必须同时满足：本地环境变量 `TANGTANG_ROUTER_CONTROL_ENABLED=1`、调用者明确传入家长批准、输入二次确认 MAC；还可配置受保护 MAC 清单。
- 本版本不自动登录、不保存路由器密码、不把 token 写入代码/日志，也不从孩子的自然语言请求推导家长批准。
- 当前尚未接入糖糖语音主链路；先通过本机 CLI/测试验证路由器能力，再接入家长授权交互。

## 本机配置

1. 在路由器管理界面登录，确认本机固件与管理地址。
2. 在本机安全的运行环境中设置短期 `MIWIFI_STOK`（登录 token），不要写进 Git、日志或聊天记录。token 可能过期，需要重新从管理界面登录获取。
3. 确认路由器 LAN 地址（默认 `192.168.31.1`），必要时设置 `MIWIFI_ROUTER_URL`。
4. 首轮只读检查，不设置 `TANGTANG_ROUTER_CONTROL_ENABLED`。
5. 只有经过家长审查和设备保护清单配置后，才可在本机启用管控。

## 本机 CLI 示例

只读查看设备：

```bash
python3 code/cat/cat-router.py devices
```

管控命令必须在本机管理员终端显式开启，并输入两次完全一致的目标 MAC：

```bash
export TANGTANG_ROUTER_CONTROL_ENABLED=1
export MIWIFI_ROUTER_MAC='路由器本机MAC'
export TANGTANG_ROUTER_PROTECTED_MACS='Mac的MAC,NAS的MAC,投影的MAC,糖糖主机的MAC'
python3 code/cat/cat-router.py block '目标设备MAC' --confirm-mac '目标设备MAC' --parent-approved
```

以上占位内容必须替换成真实 MAC；不要把这些值写入仓库。执行 `unblock` 可恢复联网。`limit` 同样要求家长确认，并只接受 1–1000 Mbps 的速度值。

## Python 调用示例

```python
from core.integrations.miwifi_router import MiWiFiClient

router = MiWiFiClient()
for device in router.list_devices():
    print(device["name"], device["mac"], device["online"], device["ips"])
```

需要调整联网权限时，调用方必须先完成独立的家长授权流程，再传入 `parent_approved=True` 和用户手动复核的 `confirmed_mac`。不要把这两个参数绑定到孩子的语音命令或 LLM 输出。

## 安全约束

- 只允许 HTTP 端口 80 上的私有 LAN IPv4，拒绝公网域名/IP、回环地址、IPv6 和 URL 内嵌凭据，防止 SSRF。
- 请求超时限制 1–8 秒，响应体限制 1 MiB，只开放两个固定 API 路径。
- 绝不暴露路由器重启、恢复出厂设置、Wi-Fi 密码变更等高影响操作。
- 必须将 Mac、路由器、NAS、投影和糖糖服务所在设备加入受保护清单；当前由本机管理员通过 `MIWIFI_ROUTER_MAC` 与 `TANGTANG_ROUTER_PROTECTED_MACS` 配置，不能猜测 MAC。
- 设备清单包含家庭网络元数据，默认不写入记忆、不上传云端、不提交 Git。

## 测试与验收

CI 自动化覆盖私网地址限制、设备列表解析、无 token/错误响应、控制默认关闭、家长确认和受保护设备拒绝。CI 不能验证真实 R3D 固件是否支持这些端点；接入前需在家庭 LAN 只读实测，并用一台非关键测试设备验证断网/恢复。