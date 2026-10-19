# 糖糖测试与规整报告（2026-10-19）

> 执行：AutoClaw/OpenClaw · 触发：完成全部 P1 后全面测试 + 根因分析 + 规整
> 运行环境：MacBook Air (Early 2014) · macOS 11.7.11 · Node 22.22.3 · Python 3.8.9/3.11.15

## 一、结论

- **P1 三项全部完成**：对话驱动层（全语音环）、记忆注入人设、主动性恢复（launchd）
- **规整后全面测试：全项 PASS，0 FAIL**（tests/smoke-20261019.sh，九大节）
- **"一直有遗漏"的根因确认**：既有部署位置问题，也有冗余凌乱，两者叠加（详见第二节），已建立机制性修复

## 二、根因分析：为什么一直有遗漏

| # | 根因 | 本次实例 | 机制修复 |
|---|---|---|---|
| 1 | **双拷贝无部署管线**：live（~/tangtang/cat）与 repo/code/cat 各自演进，改哪边全凭记忆 | 密钥泄漏修复最初只落在 live；repo 侧不知情 | deploy.sh（repo→live 单向，密钥/运行时豁免）+ 冒烟套件第 9 节"零漂移"检查 |
| 2 | **路径时代残留**：项目经历 ~/.qclaw/workspace/cat → ~/tangtang/cat 迁移，老脚本硬编码旧路径 | cat-patrol.sh 指向已清空的 ~/.qclaw（本次已修）；~/.qclaw 空目录残留（已入废纸篓） | 冒烟套件语法检查 + 后续新脚本统一用 $HOME/tangtang |
| 3 | **同名覆盖**：不同用途的脚本共用一个名字，后写覆盖先写 | 语音环曾以 cat-talk.sh 之名覆盖"事件发声器"（本次实际发生、当轮测试抓到），已改名 cat-voice-chat.sh 并恢复原 cat-talk.sh | 脚本清单入报告 + 冒烟套件"关键文件就位"逐个验证 |
| 4 | **依赖链未随部署走**：cat-remind.sh 调 cat-talk.sh，但 live 从未部署 cat-talk.sh 及其依赖（tangtang-quiet-hours.py、cat-lib 的 tts_lock） | 主动性停摆的真正断点（不是 Hermes 移除才断，此前就缺文件） | 依赖文件补齐部署 + LaunchAgent 化 |

## 三、P1 完成记录

| 任务 | 实现 | 实测证据 |
|---|---|---|
| 对话驱动层（全语音） | cat-voice-chat.sh：listen 6s → 百度 STT → glm-4-flash → 晓晓 TTS；静音 2 轮/说"到此为止"退出；儿童语音即用即删 | 三段分别实测：STT 转写 ✓ / LLM 生成 ✓ / TTS 播放 ✓ |
| 记忆注入人设 | cat-chat.py build_persona() 注入 cat-memory.json（昵称/年龄/年级/生日）+ cat-state.json（心情数值） | 问"你知道我叫什么吗" → "航航是小主人嘛"（之前答不上） |
| 主动性恢复 | com.tangtang.proactive LaunchAgent 每 30 分钟 → cat-proactive-bridge.sh 按小时挑事件 → cat-remind.sh（冷却在 cat-brain） | TANGTANG_INTERACTIVE=1 实测 water 事件："来喝水啦，咕嘟咕嘟，身体棒棒～" |

## 四、测试矩阵（规整后第二轮，全 PASS）

```
1. 脚本语法        bash -n 全部 .sh          PASS ×N
2. Python 语法     py_compile 全部 .py        PASS（含新部署的 V2 模块）
3. 密钥防护        .llm_key 600 / stt-config 600 / gitignore 覆盖 / check-ignore×3 / 暂存区无密钥   PASS ×5
4. HTTP 安全       隐藏文件 404 / 正常文件 200  PASS ×2
5. 人设记忆注入    build_persona 含记忆字段     PASS
6. 静音闸          整窗→quiet / INTERACTIVE→可发声 PASS ×2
7. LaunchAgent     cat-server / proactive 加载   PASS ×2
8. 关键文件就位    cat-talk/voice-chat/stt/bridge/serve/deploy/quiet-hours 可执行 PASS ×7
9. 零漂移          repo vs live .py/.sh/.mjs 一致 PASS
```

复跑方式：`bash tests/smoke-20261019.sh`（离线、确定性，约 10 秒）

## 五、安全修复存档（同日早些时候）

- cat-serve.py 曾将 .llm_key/.baidu_token 以 HTTP 200 提供下载（127.0.0.1:8080）→ 已加 "/." 路径拦截，实测 404
- cat-patrol.sh 曾指向已清空的 ~/.qclaw 旧路径且兜底服务器绑 0.0.0.0 → 已改 ~/tangtang/cat + 127.0.0.1

## 六、团队升级指南

1. **改代码**：只改本仓库 `code/cat/`（唯一真理源）
2. **部署**：`cd code/cat && ./deploy.sh`（repo → ~/tangtang/cat，密钥与运行时数据自动豁免）
3. **测试**：`bash tests/smoke-20261019.sh`（九大节，部署后必跑）
4. **语音对话**：运行目录 `./cat-voice-chat.sh [轮数]`；主动提醒由 `com.tangtang.proactive` LaunchAgent 每 30 分钟自动驱动
5. **事件发声**：`./cat-talk.sh <事件>`（greet/meal/water/rest/sleep…，夜间 22:30-07:00 由 quiet-hours 静音）

## 七、遗留与建议

- 媒体资产变更（assets/video ~100MB+）未随本次推送，建议 Git LFS 或网络良好时单独提交
- repo 中尚有未部署的 V2 实验模块（cat-turn.py、cat-memory.py 等），deploy.sh 本次已一并部署到 live，但它们与 live 演进版的关系需团队评审
- 睡觉文案中"洽洽"与配置"航航"并存，请家庭确认统一
- 智谱 API key 曾在即时对话出现，建议控制台轮换（.llm_key 一换即生效）
