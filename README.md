# 糖糖 AI（TangTang AI）

> 一只住在投影里的比熊小狗。

## V2 产品原则

**糖糖不是监督孩子的机器人，而是陪孩子养成习惯的小伙伴。**

核心闭环：

```text
感知 → 判断 → 选择年龄人格 → 决定是否打扰 → 文案 → 动作/视频 → 声音 → 记录结果
```

Hermes-Agent 负责理解、推理和任务规划；TangTang Core 负责身份、记忆、隐私、儿童安全和是否打扰的最终决策；表现层决定“糖糖具体怎么表现”。

## 硬件与迁移状态

- **目标主机：Mac mini M6**，作为家庭常驻运行主机；Hermes-Agent 的实机部署尚未完成。
- **旧运行环境：MacBook Air**，在新主机通过验收前保留，不直接删除旧环境。
- 大眼橙投影：显示糖糖。
- 小米蓝牙音箱：播放糖糖声音。
- HDMI/音频设备切换需要在 M6 上单独验收。

## Python 运行环境

- **V4 核心最低要求 Python 3.10；建议使用 Python 3.11。** 不要用 macOS 自带的旧版 `/usr/bin/python3` 直接启动 V4。
- 当前生产环境如果仍使用 Python 3.8，继续运行已验证的直连版；在独立 Python 3.10+ 环境安装并通过回归测试前，**不要将 V4 部署到生产目录**。
- V4 使用 `zoneinfo` 及新式类型注解。仅做 `py_compile` 或单模块测试不能证明语音全链路可用。
- 环境和部署验收步骤见 [docs/runtime-and-provisioning.md](docs/runtime-and-provisioning.md)。

## 儿童 Profile

- `play`：9岁 / 小学三年级。糖糖是玩伴、小教练、小任务搭档。
- `friend`：12岁 / 初一。糖糖是朋友、倾听者、温柔提醒者。

不得用同一套话术对待两个年龄段。

## 动画路线

主方案逐步采用短视频/WebM动作库，PNG作为静态状态与fallback。

推荐动作：`idle / walk / run / happy / curious / caring / encouraging / sleepy / sleeping / wake / welcome / sit / lie`。

视频只负责表现；Hermes-Agent 可以提出动作意图，TangTang Core 校验后选择白名单 action_id，不允许 Agent 直接操纵帧、文件路径或 shell。

## 重要边界

1. 糖糖不向孩子暴露“父母让我监督你”等内部指令。
2. 不制造“只有糖糖懂你”的依赖。
3. 不比较兄妹，不评价体重外貌，不用恐吓促成服从。
4. 儿童高风险内容必须升级给可信任成年人，不由糖糖自行处理。
5. 声纹、语音和习惯数据默认本地保存，不进入 Git，不提交真实儿童隐私数据。
6. 儿童私人记忆由 TangTang Core 管理；Hermes 内置持久记忆初期关闭，不自动保存儿童对话。
7. Hermes 工具权限初期为零工具；未通过 `/v1/toolsets` 白名单核验前，不接入家庭数据和设备操作。

## V2 改造进度

- [长期路线图](docs/HERMES-V2-ROADMAP.md)
- [目标架构](docs/HERMES-V2-TARGET-ARCHITECTURE.md)
- [代码资产与迁移风险审计](docs/HERMES-V2-ASSET-AUDIT.md)
- [Hermes 官方能力与安全配置核验](docs/HERMES-V2-HERMES-REFERENCE.md)

当前处于 Hermes API Adapter 的初步接入阶段。Hermes 仍为显式 opt-in。V4 是默认对话路径；V3 兼容回退必须同时显式设置 `TANGTANG_V4_PIPELINE=0` 和 `TANGTANG_ALLOW_LEGACY_V3=1`，避免单个旧开关意外绕过 V4 隐私链路。Mac mini M6 实机验收完成前，不宣布迁移完成。

## 项目结构

```text
tangtang/
├── README.md
├── docs/
├── core/
├── code/cat/
└── tests/
```

## 开发纪律

每次修改遵循：**先文档 → 再代码 → Mac实机测试 → 投影测试 → 记录结果 → 再提交。**

不以“代码存在”作为完成标准，以孩子看到糖糖后的自然度、稳定性和安全性作为验收标准。
