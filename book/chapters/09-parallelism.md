# 多卡不是一个开关

模型装不下一张卡，或一张卡吞吐不够时，需要切分工作。切分方向不同，省下的显存、产生的通信和适合的拓扑都不同。

{{diagram:parallelism|五种常见并行切分的是不同维度。}}

## 数据并行 DP

每组 GPU 拥有完整模型，处理不同数据。

- 推理：多个副本服务不同请求，扩大总吞吐；
- 训练：每卡处理不同 micro-batch，再同步梯度；
- 优点：概念简单，副本间热路径可相对独立；
- 约束：单副本仍要装下模型，训练还要同步梯度。

在线服务的“4 个副本”通常属于 DP 思路，不代表一次请求使用 4 卡。

## 张量并行 TP

把一层里的大矩阵按行或列切到多卡。每层都可能需要 AllReduce 或 AllGather。

- 解决单卡装不下或单卡计算不足；
- 通信频繁，适合节点内高速 NVLink/NVSwitch；
- TP 度过大时，每卡矩阵变小，通信与 launch 开销占比上升；
- head 数、hidden size 等通常要能被 TP 度整除。

### 两卡切矩阵，与两卡各跑请求有什么不同

假设矩阵 W 按输出列切成 W1、W2，两卡读取同一输入，得到不同输出片段，再按后续计算要求拼接或通信。一次请求需要两卡配合，这是 TP。两卡各持完整 W，分别接不同用户，则是副本式 DP，不需要把一次结果拼起来。

因此增加副本主要扩大总吞吐，TP 主要改变单副本容量与执行路径。把已有四卡服务改成四个副本，前提是每张卡都能容纳完整模型与运行状态。

## 流水线并行 PP

把不同层放到不同 stage，激活沿 stage 传递。

- 每卡只保存部分层；
- 通信频率比层内 TP 低，但存在 pipeline bubble；
- 推理单请求要依次经过所有 stage，延迟增加；
- micro-batch 和 stage 平衡决定利用率。

节点间互联较慢时，PP 有时比跨节点 TP 更合适，因为传输的是 stage 边界激活，而不是每层 collective。

## 上下文并行 CP

把长序列维度分到多卡，解决单卡 attention 激活或 KV 压力。它需要处理 attention 的跨卡信息交换，适合超长上下文训练和特定推理场景。

## 专家并行 EP

MoE 模型只激活部分 experts。EP 把专家分到不同卡，token 通过 AllToAll 路由到目标专家。

性能依赖 token 分布是否均衡。某些专家过热会让其他 GPU 等待，所以 router load balance 是基础设施问题，也是模型问题。

## 并行可以组合

一个大训练任务可能写成：

```text
world_size = DP × TP × PP × CP × EP
```

并非所有维度都独立，实际框架会构造多维 device mesh。选择顺序通常先考虑：

1. 单卡能否装下；
2. 节点内有哪些高速互联；
3. 节点间带宽和延迟；
4. 模型结构是否 MoE、是否长上下文；
5. batch 是否足够填满 pipeline 和 DP。

### device mesh 的坐标决定谁和谁通信

以 DP=2、PP=2、TP=2 的简化八卡布局为例，每个 rank 有三个坐标。TP 通信发生在同一 DP、PP 坐标内，PP 传输连接相邻 stage，DP 同步连接对应模型部分。编号相邻不必然表示物理互联最好，还要映射真实拓扑。

CP 与 EP 的组合在不同框架中可能共享或依赖其他维度，不能无条件将五个参数相乘当作 GPU 数。先理解每个 group 的成员与数据归属，再核对框架的 mesh 规则。

## 一个 8 卡例子

如果 70B 权重 FP16 约 130 GiB，单张 80 GiB 卡放不下。可在一个 8 卡节点使用 TP=2 或 TP=4，让每卡只保存部分权重，再视吞吐需要复制 DP 组。

但不能只做除法。还要给 KV、workspace 和通信 buffer 留空间，并检查每层 collective 是否被互联支持。

## 推理与训练的同名差异

TP、PP 在两者中概念相近，但调度目标不同：

- 训练追求稳定大 batch 吞吐，通信形状规律；
- 在线推理 batch 动态、序列长度不同，还要管理 KV；
- 训练 PP 用 micro-batch 填流水线，推理 PP 要考虑逐 token latency。

不要把训练 benchmark 的并行配置直接复制到在线服务。

### 只做权重除法会漏掉通信和峰值

130 GiB 权重切到两卡，理想每卡约 65 GiB，还要留 KV、workspace 与通信 buffer。TP 也不是保证每个 tensor 都严格均分，一些状态可能复制。模型能加载只证明容量第一关通过，接下来应测长上下文和多请求峰值。

多卡变慢时分别看每卡计算是否太小、每层通信是否昂贵以及 stage 是否空闲，避免再增加卡数放大同一瓶颈。

## 源码入口

- `megatron/core/parallel_state.py`
- `megatron/core/tensor_parallel/`
- `megatron/core/pipeline_parallel/`
- `torchtitan/distributed/parallel_dims.py`
- `vllm/distributed/`
