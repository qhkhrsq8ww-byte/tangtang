# ADR-0003: 部署管线采用单向 deploy.sh + 冒烟后置闸门

## Status: Accepted（2026-10-19）

## Context
历史遗漏根因之一：live（~/tangtang/cat）与 repo/code/cat 双拷贝各自演进，无同步机制。修复（密钥泄漏、路径）曾只落在一边。

## Decision
repo 是唯一真理源。deploy.sh 单向 rsync（repo→live），豁免密钥与运行时状态；每次部署后必跑 tests/smoke-20261019.sh（九节，含"零漂移"检查）。

## Consequences
正：消除双向漂移；豁免清单显式化；测试闸门防回归。
负：live 的临时手工修复必须回流 repo 才能存活（纪律要求）；豁免清单需随新状态文件维护。

## Alternatives Considered
- 双向同步：拒绝——正是漂移根因，冲突消解不可判定。
- git pull 式部署：拒绝——live 混有豁免文件与未入库状态，pull 语义不成立。
