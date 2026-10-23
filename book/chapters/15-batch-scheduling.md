# 批作业调度：为什么要一起开跑

夜间训练需要多个进程协作。如果只给其中部分进程设备，它们可能一直等待其他成员，已经分到的卡却无法交付任何训练结果。作业级准入要避免这种半组占用。

## 普通逐 Pod 调度的问题

考虑两个作业，各要求三个协作 Pod，而当前只能容纳四个。若各启动两个，就出现两组都缺最后成员、却没有剩余槽位的状态。单个 Pod 看起来分配成功，作业整体没有前进。

平台需要根据真实协作下界判断是否准入，再安排成员，而非仅优化每个独立 Pod 的放置成功率。

## Gang Scheduling

gang 策略将最小成员或资源需求作为启动条件。不满足时等待，满足时让必要成员获得资源。这能减少无效半启动，却可能为大组保留资源并产生暂时空闲。

准入条件应来自运行时合同，例如必须同时存在的训练 worker 数，而不是把日志收集或辅助容器也机械计入计算门槛。

### 一起获得资源，不等于同一瞬间开始计算

资源满足后，成员仍要拉取镜像、加载模型、读取数据和加入 rendezvous。某一个准备缓慢，其他 rank 仍会等它。作业监控应拆开“等待准入”和“已准入但等待协作”。

若一个辅助服务失败就应阻止开跑，也需显式写入启动条件。调度数量正确不能替代业务就绪检查。

<figure class="diagram" tabindex="0" data-review-figure="infra-gang-admission">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 396" role="img" aria-labelledby="infra-gang-admission-title infra-gang-admission-desc" style="display:block;width:100%;min-width:620px;height:auto">
<title id="infra-gang-admission-title">4 个槽位，两个各需 3 个成员的作业</title>
<desc id="infra-gang-admission-desc">逐 Pod 分配：2 + 2：两个作业都缺 1 个成员，无空槽可用；作业级准入：3 + 0：先让一个完整组获得资源，另一个等待；已分配仍需协作就绪：镜像、加载与 rendezvous 完成后再开跑。3 + 0 只是准入示例，不代表剩余 1 槽必须闲置。</desc>
<rect width="960" height="396" fill="var(--paper,#faf8f1)"/>
<g font-family="'IBM Plex Sans','Noto Sans CJK SC',system-ui,sans-serif"><text x="40" y="48" font-size="28" fill="var(--ink,#243b48)" text-anchor="start">4 个槽位，两个各需 3 个成员的作业</text><path d="M176 144 L176 164" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M171 157 L176 164 L181 157" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="40" y="88" width="272" height="56" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="56" y="123" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">逐 Pod 分配：2 + 2</text><text x="344" y="123" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">两个作业都缺 1 个成员，无空槽可用</text><path d="M176 224 L176 244" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M171 237 L176 244 L181 237" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="40" y="168" width="272" height="56" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="56" y="203" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">作业级准入：3 + 0</text><text x="344" y="203" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">先让一个完整组获得资源，另一个等待</text><rect x="40" y="248" width="272" height="56" rx="6" fill="var(--paper-2,var(--paper-deep,#e5ede9))" stroke="var(--forest,var(--accent,#29564c))"/><text x="56" y="283" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">已分配仍需协作就绪</text><text x="344" y="283" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">镜像、加载与 rendezvous 完成后再开跑</text><path d="M40 332H920" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="40" y="368" font-size="18" fill="var(--muted,#536772)" text-anchor="start">3 + 0 只是准入示例，不代表剩余 1 槽必须闲置。</text></g>
</svg>
<figcaption>图：3 + 0 只是准入示例，不代表剩余 1 槽必须闲置。</figcaption>
</figure>

## Volcano 的基本对象

Job 描述任务角色与生命周期，PodGroup 描述需要协同的成员，Queue 表达资源组织和策略范围，调度插件实现 gang、公平、优先级或装箱等规则，控制器负责把期望转换成实际对象。

这些对象管理资源进入条件，不执行模型梯度或 collective。运行时与批调度器之间要约定故障、重启和保存信号。

## 队列、公平与利用率

### FIFO

按顺序容易让用户理解等待，但队首大作业可能暂时无法运行，后面较小的作业也被挡住。若采用绕过规则，应把它说明为策略，而非暗中改变顺序。

### Priority

优先级可支持紧急校对任务，但需定义是否允许抢占、最长等待和普通任务的保障。否则高优任务持续到来时，低优队列可能长期没有进展。

### DRF

主导资源公平用于协调多资源份额，不能简单等同于平均 GPU 张数。不同卡型、显存和网络拓扑会使同一数量具有不同可用能力，资源分类仍需平台定义。

### Binpack

将兼容任务尽量集中，可以留下完整节点或互联域给大作业。集中也可能带来电力、温度或故障域风险，因此应把设备可用性与基础设施约束一起考虑。

## Backfill

大作业等待资源窗口时，可以让能在窗口前退出的小作业暂时利用空闲容量。前提是时长估计可信，或任务具有可接受的抢占和恢复合同。

训练时长受数据、保存和故障影响，用户填写“几分钟”并不是保证。可以使用明确最大运行时，超出时按约定退出，而非让临时任务无限拖延已承诺的大作业。

### 公平、碎片和等待为什么不能同时简单最大化

立刻填满所有空卡有利于短期利用率，却可能一直凑不齐大组。为大组保留资源会产生眼前空闲，却可能缩短它的整体等待。评估策略要同时看用户等待、有效计算与拓扑碎片。

公平份额和紧急优先级也可能冲突。平台应公开它选择保护的目标，并用真实或可重放作业序列检查长期饥饿。

## 抢占不是 kill -9 就结束

可恢复抢占需要一条完整协议：发出终止通知，停止开始新步骤，在规定时间内完成一致保存，退出并释放资源，后续再选择可用状态恢复。宽限期与保存能力不匹配时，会损失未提交进度。

平台要定义超时后怎样处理，也要避免同时驱逐过多作业形成 checkpoint 写入风暴。抢占延迟应包括保存与设备真正释放，而非只记录信号发送。

## 拓扑约束

协作组可能要求同一高速域、相同设备规格或特定网络亲和。数据本地性与故障域也会影响选择。每增加一种约束，调度可行空间都会缩小。

向用户提供经过验证的少量模板通常比任意 affinity 组合更可靠。模板中同时固定镜像、通信配置和恢复方式，防止资源看似满足却无法运行。

### 抢占回收的是资源，损失的是已做计算

假设最新可用保存点之后已训练 12 分钟，此时强制退出会丢掉这段工作。若愿意等 40 秒完成新保存，可以减少重算，但紧急任务也多等这 40 秒。两种成本都应记录。

真正恢复后核对选择了哪份 checkpoint、损失多少步及数据位置。只统计“几秒释放 GPU”会隐藏被抢占方的计算损失。

## 源码入口

从 `volcano/pkg/scheduler/` 追作业与队列决策，gang 条件可进入 `volcano/pkg/scheduler/plugins/gang/`。实际 Job 与 PodGroup 的生命周期分别查 `volcano/pkg/controllers/job/` 和 `volcano/pkg/controllers/podgroup/`，结合架构与插件文档核对当前快照的策略配置。
