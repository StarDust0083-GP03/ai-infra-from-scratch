# Collective：GPU 之间怎样交换数据

多卡程序不是八个独立进程各算各的。每个 rank 只持有局部数据，需要通过 collective 形成全局结果。NCCL 提供针对 NVIDIA GPU 与互联优化的 collective 实现。

{{diagram:collectives|不同 collective 规定了每个 rank 输入和输出的数据形状。}}

## 四个最常见操作

### AllReduce

每个 rank 有一份输入，先做 sum/max 等归约，每个 rank 都得到同一结果。数据并行同步梯度常用。

### AllGather

每个 rank 持有一个 shard，交换后每个 rank 得到完整集合。FSDP 在计算某层前组装参数常用。

### ReduceScatter

先归约，再把结果分片留在各 rank。FSDP 梯度分片常用。它可避免 AllReduce 后每卡保留完整结果。

### AllToAll

每个 rank 都向所有 rank 发送不同部分。MoE token 路由常用，对网络和负载均衡敏感。

### 用两个 rank 区分归约与收集

rank 0 有 `[1,2]`，rank 1 有 `[3,4]`。sum AllReduce 后两者都拿到 `[4,6]`；AllGather 则让两者拿到各自输入组成的集合，没有做相加。ReduceScatter 在相同简化输入下先形成和，再让各 rank 留不同片段，比如分别得到 `[4]` 与 `[6]`。

AllToAll 则可让每个 rank 将输入分成给不同目标的部分，交换后每个目标得到来自各源的片段。操作名规定了数据关系，不是随意交换几个名称就能获得相同结果。

## Ring 的直觉

AllReduce 可以拆成 ReduceScatter 加 AllGather。Ring 算法让每个 rank 只和邻居交换 chunk，多轮后完成聚合与分发。它能较好利用带宽，但轮数随 rank 增加，低延迟小消息可能更适合 tree 等算法。

NCCL 会依据消息大小、拓扑和配置选择算法与 protocol。应用通常调用语义，不手写环。

## 拓扑比 GPU 数量更重要

八张卡可能是：

- 同一 NVSwitch 域；
- 分属两个 PCIe root complex；
- 跨两个节点，经 InfiniBand 或 RoCE；
- 网络路径还与其他作业共享。

同样 TP=8，在这些拓扑上的结果完全不同。部署前应查看 `nvidia-smi topo -m`、NIC 亲和和 NCCL topology log。

## 同步等待

collective 需要所有参与 rank 以兼容顺序加入。一个 rank 因数据加载、CPU 抖动或 kernel 变慢，其他 rank 会在通信点等待。表面上看是 NCCL 慢，根因可能在最慢 rank 之前。

排查 hang 时检查：

1. 所有 rank 是否调用了相同 collective；
2. tensor shape、dtype、count 是否一致；
3. 是否有 rank 更早抛异常；
4. 网络接口和权限是否正确；
5. 超时是否掩盖真实首错；
6. 日志时间线中哪个 rank 最先偏离。

### 所有进程都活着，collective 也可能永远等不到

若 rank 0 调 AllReduce，rank 1 因条件分支跳过它，其他 rank 等不到匹配操作。若它们顺序或 tensor 形状不一致，同样可能出错。这类问题与网络带宽不足不同，升级网卡无法修复。

先按统一 run ID 对齐所有 rank 的日志，找到第一次分歧。某 rank 在通信前 OOM，其他日志最后显示 NCCL 超时，首错仍是显存。通信处等待只告诉你依赖未满足，没有直接证明通信库是根因。

## 通信量如何影响并行选择

TP 往往每层通信，要求低延迟高带宽；PP 主要在 stage 边界传激活；DP/FSDP 在反向传播中同步梯度或参数 shard；EP 使用 AllToAll。

不要问“哪种 collective 最快”，要问：

- 消息多大；
- 每 step 几次；
- 能否与计算重叠；
- 走节点内还是节点间；
- 最慢 rank 是否稳定。

## Overlap 不是免费

通信与计算重叠需要二者资源相对独立，并满足依赖。通信 kernel 也会使用 GPU 资源和内存带宽。过度切小 bucket 会增加 launch 与同步开销，bucket 太大又推迟通信开始。

### 大带宽为什么救不了大量小消息

用简化模型 `时间 ≈ 固定延迟 + 字节数 / 有效带宽`。假设延迟 10 μs、带宽 100 GB/s，传 1 KB 的数据时间仅约 0.01 μs，几乎全在固定开销；传 100 MB 则数据部分约 1 ms。真实 collective 有多轮和不同链路，但这个量级说明：切小 bucket 能更早启动，却可能把固定开销重复很多次。

有效 overlap 要看仍在计算的部分是否依赖该通信结果，以及通信是否争用 GPU 和 HBM。时间轴显示并发，不代表端到端 step 一定缩短，应测最终耗时。

## 源码入口

- `nccl/src/collectives.cc` 与 `src/enqueue/`
- `nccl/src/graph/`：拓扑与 channel 规划
- `nccl/src/transport/`：共享内存、P2P、网络路径
- `nccl/src/ras/`：可靠性与诊断
- `megatron/core/tensor_parallel/mappings.py`

NCCL 源码很底层。初读先跟 API 到 enqueue，再看 topology 如何选择 transport，不要从 device kernel 顺序读起。
