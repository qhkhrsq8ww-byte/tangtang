# 糖糖 V3.1 · 隐私与路径回归测试报告

- **日期**：2026-08-28
- **分支**：`fix/v3.1-privacy-paths-20260828`（基于 `codex/v3-family-brain-integration-20260828` @ `05b7b9e`）
- **目标**：P0 隐私修复验证 + crontab/launchd 路径迁移 + 运行时回归
- **结果**：**28 PASS / 0 FAIL / 0 SKIP**

---

## 一、测试范围与结果

| 类别 | 测试项 | 结果 |
|---|---|---|
| 语法 | Python（tangtang-privacy/profile/cat-vp/cat-chat） | ✅ PASS |
| 语法 | Shell（全部 .sh） | ✅ PASS |
| 语法 | JSON（family.json） | ✅ PASS |
| 人格 | grandpa/grandma/dad/mom/child_12/child_9/unknown 解析 | ✅ 7/7 PASS |
| 权限 | PRIVATE 儿童原话不得落盘（「我今天被同学欺负了…」→ 拦截） | ✅ PASS |
| 权限 | FAMILY 成人原话可进存储（「晚上加班到九点」→ 保留） | ✅ PASS |
| 权限 | storage 级别：child_9=PRIVATE / dad=FAMILY / unknown=PUBLIC | ✅ 3/3 PASS |
| 声纹 | enroll 建档 + identify 识别（440Hz 正弦波模拟） | ✅ 2/2 PASS |
| 静默 | 22:30 含入 / 23:00 / 06:59 静默，07:00 释放 | ✅ 4/4 PASS |
| TTS | edge 链路（cat-tts-edge.py 生成 mp3） | ✅ PASS |
| 投影 | 192.168.31.104:61949 连通 | ✅ PASS |
| 回归 | cat-brain status / cat-lib.sh 加载 | ✅ 2/2 PASS |
| 路径 | migrate-paths.sh 语法 | ✅ PASS |
| 安全 | 真实百度 Key 不在 git 跟踪文件 | ✅ PASS |
| launchd | daemon plist 模板合法（plutil） | ✅ PASS |

## 二、本次修复提交

| Commit | 内容 |
|---|---|
| `47ab11b` | **P0-1 儿童隐私**：新建 `tangtang-privacy.py` 存储策略层，`cat-vp.py` log() 拦截儿童原话（text 置空）；顺带修复 save_json 目录不存在 |
| `a2bca47` | **P0-2 真实 Key**：新建 `.env.example`，`.gitignore` 补 `.env`；确认真实 Key 从未进 git 历史 |
| `8ffc653` | **P1-1 permissions 接入运行时**：`tangtang-profile.py` 复用 resolve_member，`cat-chat.py` build_persona 按 storage 隔离 |
| `158f4a1` | **P1-4 crontab/launchd 迁移**：`config/migrate-paths.sh` 一键迁移脚本（备份→替换→标记废弃），crontab 备份到 `config/backups/crontab-20260828.bak` |
| `a351364` | **回归套件**：`tests/test-v3.1-privacy.sh`（28 项），`tangtang-quiet-hours.py` 增加 `--test-time` |

## 二·B、隐私最终回归（真实场景验证）

输入 `cat-vp.py log child_9 "我今天被同学欺负了，好难过"` 后，扫描整个 data 目录：

| 检查点 | 结果 |
|---|---|
| cat-habits.json 中 child_9 的 text | `""`（空，原话被拦截） |
| 结构化信息（时间/活跃时段/次数/星期） | ✅ 完整保留 |
| 全文搜索「被同学欺负」 | **0 命中** |
| family summary 中儿童原话 | 无（只显示「1 次互动 + 活跃时段」） |
| dad（FAMILY）原话 | ✅ 保留「今晚加班到九点」，可进家庭摘要 |
| unknown（PUBLIC）原话 | ✅ 保留「今天下雨了」，进普通事件流 |

**结论：儿童原话已在存储层完全拦截，无法以任何形式落盘。**

## 三、路径迁移说明

### crontab（12 条任务 + 2 条废弃）
- 全部从 `/Users/lv/.qclaw/workspace/cat/` → `/Users/lv/.qclaw/workspace/tangtang/code/cat/`
- 2026-08-28 一次性唤醒任务（已执行完）标记 `[DEPRECATED-20260828]`，保留注释待审计
- **⚠️ 沙箱限制**：当前执行环境 `crontab` 写命令被 SIGTERM 拦截（读正常），**需用户手动运行迁移脚本生效**：
  ```bash
  cd /Users/lv/.qclaw/workspace/tangtang
  bash config/migrate-paths.sh --apply
  ```

### launchd（生产 plist）
- `/Users/lv/Library/LaunchAgents/com.tangtang.cat-server.plist` 仍指向旧目录
- 仓库模板 `config/com.tangtang.daemon.plist.example` 用 `__TANGTANG_HOME__` 占位符
- 迁移脚本支持替换，**不直接覆盖生产**，用户确认后 `--apply` 并重载：
  ```bash
  launchctl unload ~/Library/LaunchAgents/com.tangtang.cat-server.plist
  launchctl load ~/Library/LaunchAgents/com.tangtang.cat-server.plist
  ```

## 四、遗留问题

1. **`cat-turn.py` 缺失**：main 和当前分支都没有（历史分支 02903e0 有 225 行），客厅小回合/energy/sentence/ledger 功能待评估是否合并
2. **`cat-lib.sh` 功能缺口**：main 只有 65 行 vs 历史 456 行，turn/作息闸门函数（`tangtang_turn_who` 等约 10 个）未合并
3. **STT 未配置**：百度 key 在本地 `cat-stt-config.sh`（未跟踪），`TANGTANG_STT_API_KEY` 未配置，语音转文字不可用
4. **pmset 缺口**：sleep=1 / autopoweroff=1（72h 深度待机断电风险），建议 `sudo pmset -a sleep 0 disksleep 0 autopoweroff 0 standby 0`
5. **投影蓝牙断开**：需手动重连（OBE_R3Ultra 192.168.31.104）

## 五、下一步

- [ ] 用户运行 `migrate-paths.sh --apply` 完成生产迁移
- [ ] 合并 `cat-turn.py` / `cat-lib.sh` 历史功能（评估 T50-T65）
- [ ] 配置百度 STT key 开通语音输入
- [ ] push 分支 + 创建 PR（目标 `codex/v3-family-brain-integration-20260828`）
