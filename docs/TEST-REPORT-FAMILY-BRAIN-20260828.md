# 糖糖 V3 家庭大脑测试报告

> 日期：2026-08-28 ｜ 执行人：OpenClaw ｜ 分支：`codex/v3-family-brain-integration-20260828`（HEAD `f894683` + 修复 `c366db8`）
> PR：qhkhrsq8ww-byte/tangtang#15 feat: V3 家庭成员人格与夜间静默落地

---

## 1. 测试环境

- **Mac 型号**：MacBook Air（2013 年中，i5-4250U / 4GB）
- **macOS**：11.7.11 Big Sur
- **Python**：/usr/bin/python3 3.8.9（注意：`python3` 别名指向 QClaw 损坏的 3.11，必须用系统解释器）
- **Git commit**：`f894683`（测试起点）+ `c366db8`（修复 commit）

## 2. 自动化测试

- **PASS：20**（官方 tests/test-v3-family.sh 全部通过；另补 8 项夜间边界测试全过）
- **FAIL：2**（见第 11 节：P0 隐私明文落盘、P1 权限字段未实现）
- **SKIP：4**（投影、真实声纹样本、STT、麦克风硬件）

## 3. 六人家庭人格

| 成员 | member_id | 期望人格 | 实际人格 | 结果 |
|---|---|---|---|---|
| 爷爷 | grandpa | elder | elder | ✅ |
| 奶奶 | grandma | elder | elder | ✅ |
| 爸爸 | dad | adult | adult | ✅ |
| 妈妈 | mom | adult | adult | ✅ |
| 姐姐(12) | child_12 | friend | friend | ✅ |
| 弟弟(9) | child_9 | play | play | ✅ |

- **身份识别与人格选择已解耦**（tangtang-profile.py 通过 family.json 映射，别名 外公/外婆/爸/妈/boy/girl 全部正确解析）
- **年龄变化无需改代码**：persona 由 family.json 配置驱动

## 4. 声纹

- **建档**：✅（cat-vp.py enroll 洽洽 成功，合成 PCM）
- **识别**：✅（identify 返回洽洽）
- **unknown**：✅（"unknown/访客/陌生人/张三/小明" 均不冒充成员，返回 unknown+play）

## 5. 夜间静默

| 时间 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 22:29 | 可发声 | speak | ✅ |
| 22:30 | 静默 | quiet | ✅ |
| 23:30 | 静默 | quiet | ✅ |
| 02:00 | 静默 | quiet | ✅ |
| 06:59 | 静默 | quiet | ✅ |
| 07:00 | 可发声 | speak | ✅ |
| 07:01 | 可发声 | speak | ✅ |

- **静默闸门位置正确**：cat-talk.sh 在调用 cat-brain.py **之前**检查 quiet-hours，先判断后发声 ✅
- **记录≠打扰**：静默只禁止 TTS，事件记录（cat-brain 状态）正常
- **用户主动对话绕过**：TANGTANG_INTERACTIVE=1 可绕过（cat-voice.sh 主动对话链路无静默拦截，正确）

## 6. TTS

- **结果**：✅ 回归通过
- **延迟**：约 2-3 秒（edge 合成 16KB mp3）
- **音质**：48kbps / 24kHz 单声道，2.69 秒，无截断无重复
- **fallback 链**：edge → 百度翻译 → 系统 say 完整可用

## 7. 投影

- **结果**：SKIP（投影 192.168.31.104:61949 不可达，蓝牙断开状态，无法实测）

## 8. 原有功能回归

| 功能 | 结果 | 说明 |
|---|---|---|
| 客厅小回合(energy/sentence/ledger) | ⚠️ | cat-turn.py 在当前分支**不存在**（main 缺失，未在本轮范围） |
| play/friend 人格 | ✅ | cat-chat.py 输出正常 |
| 声纹建档/识别 | ✅ | 测试通过，已清理测试样本 |
| TTS | ✅ | edge 链路完整 |
| cat-brain 状态 | ✅ | 输出正常 |
| 定时任务 | ⚠️ | crontab 12 条仍指向**旧目录**（P1） |
| 账本标签隔离 | ⚠️ | cat-turn.py 缺失无法实测，但 cat-vp.py log 有隐私问题（P0） |

## 9. 儿童隐私

- **PASS（摘要层）**：cat-chat.py 不将儿童原话写入任何 summary/today 输出
- **FAIL（存储层）**：cat-vp.py `log()` **明文存储儿童原话**到 `cat-habits.json`（BASE 固定 CAT_DIR，不受 TANGTANG_DATA_DIR 控制），且 family.json 的 `permissions.self_private/family_summary` **字段存在但代码从未读取使用**（P1）
- **git 层**：✅ 无儿童数据/敏感文件进入 git（.gitignore 覆盖 cat-habits.json 等）

## 10. 异常恢复

| 场景 | 结果 | 说明 |
|---|---|---|
| family.json 不存在 | ✅ | 降级 unknown+play，不崩溃 |
| family.json 格式错误 | ✅ | 捕获异常返回默认值 |
| LLM 网关失败 | ✅ | fallback 到 cat-brain.py 本地规则引擎，正常回复 |
| 声纹识别失败 | ✅ | WHO=unknown → play 人格继续 |
| STT 失败 | ✅ | cat-voice.sh 提示"没听清"继续 |
| 首次运行数据目录不存在 | ✅ | **已修复**（cat-chat.py makedirs） |

## 11. FAIL 清单

### FAIL-1（P0）：儿童原话明文落盘 cat-habits.json
- **问题**：cat-vp.py log() 将儿童 STT 文本明文写入 cat-habits.json（含"我今天被同学欺负了…"等私人内容），family.json 中 self_private=true 未生效
- **复现步骤**：`cat-vp.py log child_9 "我今天被同学欺负了..."` → cat-habits.json 明文存文本
- **预期**：儿童原话不落盘，或脱敏/加密
- **实际**：明文落盘 code/cat/cat-habits.json（固定 CAT_DIR 路径）
- **日志**：`"text": "我今天被同学欺负了..."`

### FAIL-2（P1）：permissions 权限字段完全未实现
- **问题**：data/family.json 定义了 self_private/family_summary 权限，但代码（cat-chat.py/cat-brain.py/cat-vp.py）**零引用**
- **复现步骤**：`grep -rn "permissions\|family_summary" code/` 无结果
- **预期**：权限字段应驱动隐私策略（如 summary 排除 child）
- **实际**：死字段，无任何逻辑消费

## 12. SKIP 清单

1. **投影回归**：投影蓝牙断开，IP 不可达（昨天已知状态）
2. **真实声纹六人样本**：无爷爷/奶奶/爸爸/妈妈真实录音，只能用合成 PCM 验证链路逻辑（身份→人格映射已实测，真实声纹→身份需部署后采集）
3. **百度 STT**：cat-stt-config.sh 存在真实 key 但未验证云端连通（且 key 明文存本地是风险）
4. **客厅小回合实机**：cat-turn.py 在本分支不存在（main 缺失的历史问题，本轮范围外）

## 13. P0（必须立即修复）

1. **cat-vp.py 儿童原话明文落盘**：需改为只存标签（时间/姓名/时长），或对文本脱敏；HABIT_FILE 应尊重 TANGTANG_DATA_DIR
2. **本地真实百度 API Key 明文**（cat-stt-config.sh 工作区明文，虽未入库，建议改用环境变量+移除真实 key）

## 14. P1（下一轮修复）

1. **permissions 字段未实现**：self_private/family_summary 需接入 summary/context 逻辑
2. **crontab 12 条指向旧目录** `/Users/lv/.qclaw/workspace/cat/`，需迁移到新仓库
3. **launchd com.tangtang.cat-server 也指向旧目录**（WorkingDirectory=/Users/lv/.qclaw/workspace/cat）
4. **cat-turn.py/tangtang_paths.py/cat-lib.sh 完整版未合并 main**（历史遗留）

## 15. P2（以后优化）

1. unknown 默认 play 人格 + "小朋友"称呼可考虑中性化
2. cat-chat.py 中 chat() 的重复请求逻辑（max_tokens 600→1000 重试）可重构
3. cat-tts-baidu-token.mjs 从配置读 key 的方式可统一为环境变量

## 16. 工程师最终判断

1. **PR #15 是否可以合并 main？** — **不建议直接合并**，建议修复 P0 后合并（见下）
2. **阻塞原因**：P0 隐私漏洞（儿童原话明文落盘）不解决不应合入；且该漏洞是本轮"家庭隐私"设计声称要解决的问题，但实际未落地
3. **当前最严重的三个问题**：
   - ① 儿童原话明文落盘（隐私核心承诺未实现）
   - ② permissions 权限字段是死代码（隐私设计悬空）
   - ③ crontab/launchd 指向旧目录（生产环境跑的是旧代码）
4. **架构问题**：**有**。家庭身份→人格的架构解耦做得好（family.json 驱动），但**隐私策略层（permissions）只画了框架没实现**，且数据落盘路径（HABIT_FILE 固定 BASE）绕过 TANGTANG_DATA_DIR 的设计，是"本地化存储"架构的漏洞
5. **儿童隐私问题**：**有，P0 级**。存储层明文
6. **人格污染问题**：**基本没有**。六人人格差异明显（elder 从容/adult 简洁/friend 尊重/play 活泼），姐姐首次回复偶发"写作业"字样，重测 3 次无复现（LLM 生成随机性，非系统性污染）
7. **旧 cat 架构残留**：**有**。crontab/launchd 指向旧目录；cat-turn 系列仍未合入 main；cat-stt-config.sh 旧明文 key

---

### 附加：本轮已修复
- **fix `c366db8`**：cat-chat.py 首次运行数据目录不存在时 FileNotFoundError（makedirs），已单独 commit

*测试分支：`codex/v3-family-brain-integration-20260828`（含测试修复 commit）*
