# Hermit 与 OpenClaw 的定位比较

这份文档只做高层定位比较，不追求对 OpenClaw 做逐文件、逐版本的实现分析。

约束：

- Hermit 侧结论以当前仓库源码为准
- OpenClaw 侧只保留稳定的公开定位比较，不把易变的外部实现细节写死

## 一句话结论

两者都属于本地优先 agent 系统，但设计重心不同：

- Hermit 偏 runtime-first、个人工作流、可读源码
- OpenClaw 更偏 platform-first、通道面更宽、运维面更重

## Hermit 的当前现实定位

从仓库源码看，Hermit 的中心是：

- `AgentRunner`
- `AgentRuntime`
- `PluginManager`
- `~/.hermit` 文件状态目录

当前已落地的表面主要是：

- CLI
- Feishu adapter
- scheduler
- webhook
- MCP
- macOS companion

## Hermit 的优势

如果你更看重下面这些点，Hermit 更匹配：

- 可以在较短时间内读透 runtime
- 想把状态保留在本机文件系统
- 想通过插件继续长出私有能力
- 更偏个人工作流，而不是完整平台

## Hermit 的代价

这类设计也有明确代价：

- 控制面较轻
- 默认通道较少
- 产品化封装程度不如更重的平台
- 某些能力需要自己动手扩展插件

## 与更重平台的差异

平台型系统通常会强调：

- 更多 channel
- 更完整控制台
- 更重的网关与运维面
- 更标准化的多租户或团队能力

Hermit 目前并不试图在这些维度上与之正面竞争。

## 什么时候选 Hermit

更适合选择 Hermit 的情况：

- 你要的是一个个人 agent runtime，而不是产品平台
- 你希望自己能改 provider、插件和状态模型
- 你更在意“本机可检查、可恢复、可审计”
- 你愿意接受更少的默认通道与更轻的控制面

## 这轮文档更新的原则

旧版本包含一些更容易随外部产品变化而失真的描述。

这次更新后，这份文档只保留：

- 对 Hermit 当前代码库稳定成立的结论
- 对“轻 runtime vs 重平台”这一层面的定位比较
