# 批作业调度：为什么要一起开跑

一个 32 GPU 训练作业常由 4 个 Pod 组成，每个 Pod 要 8 GPU。如果只启动其中 3 个，进程会等待第 4 个 rank，已经占用的 24 GPU 也做不了有效训练。这就是 gang scheduling 要解决的问题。

## 普通逐 Pod 调度的问题

假设集群有两个各需要 4 个 Pod 的作业，当前只有 6 个空槽。普通 scheduler 可能各放 3 个：

```text
Job A: 3 / 4 已启动，等待
Job B: 3 / 4 已启动，等待
空槽: 0
```

两个作业都无法开始，却占满资源。批调度器需要以 PodGroup 或 Job 为整体判断是否满足最小成员数。

## Gang Scheduling

只有能同时满足 `minMember` 或资源下界时才让作业进入运行，否则先排队。这避免半启动死锁，但会产生资源碎片与等待，需要队列和 backfill 策略配合。

### 一起获得资源，不等于同一瞬间开始计算

Gang 调度为作业满足协作资源下界，防止半组长期占卡；Pod 之后仍要拉镜像、准备数据和 rendezvous。某个成员启动慢，其余 rank 依旧等待。调度准入解决资源协作，训练 runtime 解决进程协作，两个阶段应分别观测。

minMember 也应符合真实角色：某些辅助任务不必和训练 worker 同时计算，不能机械把全部 Pod 数当作门槛。模板先定义哪些成员是开跑必要条件。

## Volcano 的基本对象

- Job：批作业生命周期和任务角色；
- PodGroup：一组需要协同调度的 Pod；
- Queue：组织配额、权重和优先级；
- Scheduler plugins：gang、priority、DRF、binpack 等策略；
- Controllers：把 Job 期望状态调和成 Pod 与 PodGroup。

Volcano 不替代训练框架。它决定何时、在哪里给 Pod 资源，TorchTitan/Megatron 仍负责 rank 内计算与通信。

## 队列、公平与利用率

### FIFO

容易理解，但一个超大作业可能阻塞后面能立即运行的小作业。

### Priority

高优作业先运行，需定义是否允许抢占以及被抢占作业如何恢复。

### DRF

Dominant Resource Fairness 根据用户最稀缺资源份额协调多资源公平。GPU 集群还可能区分型号和拓扑，单一计数并不够。

### Binpack

尽量把任务塞紧，空出完整节点给大 gang。它提高可调度性，但热点、功耗和故障域集中也要考虑。

## Backfill

大作业等待完整资源时，可让预计较短的小作业临时填空，但必须确保不会延误已承诺的大作业。需要运行时估计或最大时长合同，AI 训练时长往往不准，因此策略要保守。

### 公平、碎片和等待为什么不能同时简单最大化

让小作业先跑，可能提高即时利用率，却推迟需要完整节点的大作业；为大作业保留槽位，又可能出现暂时空闲。Binpack 尝试留下整节点，DRF 关注资源份额，目标不同。空闲 GPU 不必然证明调度器无效，还要看将来承诺与拓扑要求。

Backfill 依赖时长估计。小任务超出预计，就可能侵占大作业开始窗口，因此需要最大运行时或可抢占合同。不能只按用户自报“很快”判断。

## 抢占不是 kill -9 就结束

抢占前应给训练任务时间保存 checkpoint。需要协调：

1. scheduler 发出终止或驱逐；
2. 作业捕获信号并停止接收新 step；
3. 完成一致 checkpoint；
4. Pod 退出释放 GPU；
5. 重新调度后从 checkpoint 恢复。

宽限期太短会丢进度，太长会拖慢高优作业。

## 拓扑约束

多卡作业除了数量，还可能要求：

- 同一节点或同一 NVSwitch 域；
- 节点靠近同一网络 leaf；
- GPU 型号一致；
- 本地 NVMe cache 已有数据；
- 避开同一故障域或维护节点。

约束越多，调度越难。平台应提供少量经过验证的资源模板，不让每个用户手写复杂 affinity。

### 抢占回收的是资源，损失的是已做计算

宽限期应容纳一致 checkpoint，但高优作业也不能无限等待。平台先定义信号、保存时限和未完成处理，再测试训练框架是否响应。只发送终止信号不保证 optimizer、数据位置和模型状态已经落盘。

重新调度时沿用最近完整 checkpoint，并记录损失步骤与原因。这样才能比较优先级政策的真实成本，而非只统计资源多久被释放。

## 源码入口

- `volcano/pkg/scheduler/`
- `volcano/pkg/scheduler/plugins/gang/`
- `volcano/pkg/controllers/job/`
- `volcano/pkg/controllers/podgroup/`
- Volcano architecture 与 plugin 文档
