# 分片、重计算与并行组合

单卡显存装不下训练状态时，第一反应不应是盲目增加 GPU。先确认要切的是数据、参数、激活、序列还是模型层，因为每一种切法引入不同通信。

## 从复制到完全分片

普通数据并行在每个 rank 复制权重、梯度和优化器状态。FSDP 与 ZeRO 将这些状态按 rank 分片。

{{diagram:training-memory|完全分片减少每卡长期保存的训练状态，但计算前后需要通信。}}

### ZeRO 的教学分级

- Stage 1：分片 optimizer state；
- Stage 2：再分片 gradient；
- Stage 3：再分片 parameter。

现代框架的具体接口和内部实现不一定直接使用这些名字，但这个递进帮助理解：省得越多，按需组装与通信越多。

## FSDP2 的直觉

每个 rank 平时保存参数 shard。某层计算前 AllGather 形成需要的参数，完成后可 reshard。Backward 同样需要参数，并通过 ReduceScatter 得到分片梯度。

关键调优点：

- shard group 大小；
- 哪些 module 作为一个 FSDP unit；
- prefetch 与通信计算重叠；
- forward 后是否 reshard；
- mixed precision 和 CPU offload；
- state dict 与 checkpoint 格式。

过小的 unit 会产生大量小 collective，过大又提高峰值显存。

### 分片后的常驻显存与计算峰值不同

假设总参数 16 GiB，四个 rank 理想各常驻 4 GiB。某个 unit 大小也是 4 GiB，若计算前另分配完整参数 buffer，这一时刻就会同时存在常驻 4 GiB 和完整 buffer 4 GiB。预取下一 unit 还可能继续增加占用。这里是简化分配算例，实际生命周期依实现而异；关键是峰值不能只用总参数除以四。

FSDP unit 越大，一次组装越大；越小，collective 次数越多。粒度选择要看峰值与通信时间的共同曲线，省掉常驻状态只是优化的一部分。

## 3D 并行

大规模训练常组合 DP/FSDP、TP 和 PP：

```text
DP/FSDP：切训练样本或训练状态
TP：切每层矩阵
PP：切模型层
```

Megatron-LM 进一步支持 CP、EP 等维度。device mesh 给每个 rank 坐标，例如 `(dp, pp, tp)`，每类 collective 只在对应维度 group 内发生。

## 为什么节点内优先 TP

TP 每层通信，最需要低延迟高带宽。因此通常先把 TP group 放在同一 NVLink/NVSwitch 域，再把 PP 或 DP 扩到节点间。具体仍取决于硬件拓扑和模型形状。

如果 scheduler 把一个 TP group 的 Pod 分散到普通网络节点，程序可能能启动，但性能严重下降。

## Pipeline Bubble

PP stage 必须等待前一 stage 的激活。用多个 micro-batch 交错可填流水线，但开始和结束仍有空泡。stage 计算不均衡时，最慢 stage 决定节拍。

优化方向：

- 平衡每个 stage 的层与计算；
- 增加合理 micro-batch 数；
- 使用 1F1B 等 schedule；
- 避免某 stage 独占 embedding 或 loss 的额外开销；
- 监控每 stage 时间，而非只看全局 step。

### 流水线空泡不是 GPU 没有被分到任务

只看两个等时 stage 的 forward：一个 micro-batch 需要两段时间，各卡只忙其中一段。四个 micro-batch 流水执行，A 在第 1 至 4 段处理，B 在第 2 至 5 段处理，总共五段，每卡忙四段，理想利用率为 80%。真实训练还有反向、通信和调度依赖，不能照搬这个比例，但它说明增加 micro-batch 怎样摊薄起止空泡。

因此 PP 利用率与 micro-batch 数、stage 平衡和 schedule 相关。只看集群给齐了多少卡，无法判断流水线是否填满；还要查看每个 stage 的计算与空闲时间。

## CPU Offload 的真实代价

把参数或 optimizer state 放到 CPU 可省 GPU 显存，但通过 PCIe 搬运。若搬运不能与计算重叠，GPU 会等待。CPU 内存带宽、NUMA、pinned memory 和网络也成为系统部分。

Offload 是容量方案，不是免费扩容。

## 选型顺序

1. 用 activation checkpointing 处理激活峰值。
2. 用 FSDP/ZeRO 分片训练状态。
3. 模型单层或算子仍太大时引入 TP。
4. 整体层数继续扩展时引入 PP。
5. 长序列或 MoE 再考虑 CP/EP。
6. 每增加一维，都用 profile 确认通信与空泡。

这个顺序不是定律，但避免一开始就构造难以调试的五维并行。

### 怎样让并行选择成为可解释的实验

先确认 OOM 主项，激活大则试重算，长期训练状态大则试分片；单层仍过大再研究 TP，层数扩展再研究 PP。每次保留更简单对照，记录峰值、通信字节和 step 时间。

offload 把问题转移到 CPU 内存与 PCIe，若搬运不可重叠，节省显存的同时会增加等待。复杂 mesh 能扩大容量，但故障定位与 checkpoint reshard 也更难，应计入运维成本。

## 源码入口

- `torchtitan/distributed/`
- `torchtitan/models/*/parallelize.py`
- `megatron/core/parallel_state.py`
- `megatron/core/pipeline_parallel/`
- `megatron/core/distributed/`
