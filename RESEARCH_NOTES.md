# AI Infra from Scratch：研究笔记

## 面向谁

读者会写一点 Python，听过大模型和 GPU，但对 CUDA、显存、分布式训练、推理引擎和 Kubernetes 缺少整体认识。本书从一条请求和一张 GPU 卡开始，每章只引入解决当前问题所需的新概念。

快照日期：2026-09-22。源码提交见 `sources/inventory.json`。

## 范围

AI Infra 在本书中指支撑模型训练和在线推理的工程系统，包括：

- GPU 的计算、显存与互联；
- 模型权重、激活、梯度、优化器状态与 KV cache；
- 单卡推理、动态批处理、分页 KV 管理与量化；
- 数据、张量、流水线、上下文和专家并行；
- 集体通信与拓扑；
- checkpoint、对象存储与故障恢复；
- Kubernetes GPU 暴露、批作业调度、在线服务扩缩容；
- 延迟、吞吐、利用率、成本与 SLO。

不深入讲模型算法推导、CUDA kernel 编程细节、网络交换机配置或任一云厂商产品菜单。

## 一手材料

### 本地官方源码

1. vLLM：请求调度、KV cache、GPU worker、模型执行与分布式服务。
2. TorchTitan：训练循环、并行维度、FSDP、checkpoint、数据与可观测性。
3. Megatron-LM：张量、流水线、上下文、专家并行和分布式 checkpoint。
4. NCCL：collective、拓扑、transport、调度和 RAS。
5. NVIDIA Kubernetes Device Plugin：GPU 发现、资源注册、MIG、MPS 与 time-slicing。
6. Volcano：队列、PodGroup、gang scheduling 与批作业插件。
7. KubeRay：RayCluster、RayJob、RayService 与 Kubernetes operator。

### 官方文档与论文

归档在 `sources/web/`，URL 索引见 `sources/web/sources.tsv`。关键论文包括 PagedAttention、Megatron-LM、ZeRO、FlashAttention 和 Roofline。官方文档来自 NVIDIA、PyTorch、vLLM、Kubernetes、Volcano、Ray 与 Hugging Face。

## 核心心智模型

### 1. AI Infra 首先是数据移动系统

GPU 峰值 FLOPS 只有在数据及时送到计算单元时才有意义。很多推理解码步骤受显存带宽限制，跨 GPU 并行又受互联带宽与同步延迟限制。优化前要先判断瓶颈属于计算、显存、通信、存储还是排队。

### 2. 容量规划的第一步是字节账本

- 权重内存约为参数量乘以每参数字节数。
- 训练还需要梯度、优化器状态和激活，具体倍数随精度和实现变化。
- 推理还要为每个活跃 token 保留 KV cache。
- allocator、CUDA graph、通信 buffer 和临时 workspace 也占显存。

公式给下界，实测决定可用容量。

### 3. 训练和推理是两种不同负载

训练重复执行 forward、backward 和 optimizer step，目标通常是高吞吐与稳定 checkpoint。在线推理同时面对长短不一的请求，目标是 TTFT、TPOT、尾延迟、吞吐与成本之间的平衡。

### 4. Prefill 与 Decode 也不是同一种负载

Prefill 一次处理提示词中的多个 token，并行度高，通常更偏计算密集。Decode 每步为每条序列生成少量 token，要反复读取权重和 KV，常更偏带宽与调度。两者混批、分离或分配不同资源，会产生不同权衡。

### 5. 并行不是“多卡自动变快”

- DP 复制模型，扩大样本或请求吞吐。
- TP 切算子，需要频繁 collective。
- PP 切层，存在流水线气泡。
- CP 切序列，服务长上下文。
- EP 切专家，依赖 all-to-all 和负载均衡。
- FSDP/ZeRO 切训练状态，节省显存但增加通信与组装。

选错并行维度会把显存问题变成通信问题。

### 6. Kubernetes 只看到资源合同

Device Plugin 将 GPU 注册成扩展资源，例如 `nvidia.com/gpu`。默认调度器主要按可分配数量放置 Pod，不理解模型大小、NVLink 域、作业 gang 或 KV cache 热度。Device Plugin、标签、调度器、operator 和应用运行时各负责不同层。

### 7. 两个调度器同时存在

集群调度器决定工作负载落在哪些节点和 GPU；推理引擎调度器决定每个迭代处理哪些请求与 token。前者以 Pod 和资源为单位，后者以序列、token budget 和 KV block 为单位。线上性能问题可能发生在任一层。

## 易混淆边界

- GPU utilization 高不等于有效 token 吞吐高。
- 显存已分配不等于模型实际使用，缓存分配器会保留内存。
- PagedAttention 减少碎片和复制，不会让 KV cache 免费。
- 量化减少权重字节，不保证所有硬件与 batch 下都更快。
- AllReduce 不是“把所有数据发送给所有人”的唯一实现，它可由 ring、tree 等算法完成。
- GPU request 在 Kubernetes 中通常写在 limit，扩展资源不能像 CPU 一样小数超卖。
- 平均延迟不能描述尾部体验，应查看分位数和排队时间。

## 写作顺序

不按项目 README 顺序平铺，而按读者建立系统模型的依赖关系组织：

1. 请求路径和最少数学词汇。
2. GPU 与显存字节账本。
3. 单卡推理和 KV 管理。
4. 多卡推理与训练。
5. 集群资源暴露和调度。
6. 服务、扩缩容、观测和故障。
7. 用标准库模拟器与端到端设计收束。

## 不作出的承诺

- 不把示例估算当作特定 GPU 或模型的 benchmark。
- 不宣称一个并行策略适用于所有拓扑。
- 不把 Kubernetes、Volcano 或 KubeRay 当作必须组合。
- 不覆盖云厂商托管服务的全部差异。
- 不用仓库文件数量声称逐行覆盖。
