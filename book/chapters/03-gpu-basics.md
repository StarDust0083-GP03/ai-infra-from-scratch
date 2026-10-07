# GPU 不是更快的 CPU

CPU 擅长少量复杂线程、分支和低延迟响应。GPU 用大量较简单的执行单元同时处理规则数据，擅长矩阵乘和向量操作。把串行 Python 搬到 GPU 上不会自动变快，任务要有足够并行度，数据移动成本也要值得。

## 一张卡里的四个角色

### 计算单元

CUDA cores 和 tensor cores 执行算术。厂商给出的峰值 FLOPS 依赖数据类型、稀疏条件和特定指令，不能直接当作应用速度。

### HBM 或显存

模型权重和运行 tensor 放在设备显存。容量决定能否装下，带宽决定每秒能搬多少。decode 常反复读取大量权重，因此即使算术不多，也可能被带宽卡住。

### Cache 与 shared memory

更靠近计算单元的小容量高速存储。好的 kernel 会复用数据，减少往返 HBM。FlashAttention 的核心贡献之一就是 IO-aware 分块，减少慢层级的数据移动，而不是近似注意力结果。

### 互联

PCIe、NVLink、NVSwitch、InfiniBand 或 RoCE 连接 CPU、GPU 和其他节点。多卡性能由最慢的必要通信路径约束。

## Roofline：先判断是哪种上限

{{diagram:roofline|Roofline 把性能上限分成带宽斜坡和计算平台。}}

算术强度表示每读取一个 byte 做多少计算：

```text
arithmetic intensity = operations / bytes moved
```

- 算术强度低，点落在斜坡，优先减少数据搬运或提高复用；
- 算术强度高，点接近平台，优先提高 kernel 与 tensor core 利用；
- 实际性能还会受调度、同步、分支和 launch 开销影响。

Roofline 不是精确预测器，而是阻止错误优化方向的地图。

### 用一个假设硬件手算 Roofline

假设有效显存带宽上限为 1 TB/s，目标精度计算上限为 100 TFLOP/s。算术强度为 10 FLOP/byte 的任务，带宽允许约 10 TFLOP/s，远未碰到计算平台；强度为 200 时，带宽给出 200 TFLOP/s，但计算平台只允许 100。上限取两者较小值。

这些是教学数字，不是某张卡的实测。实际 kernel 还受数据布局、并行度和同步影响。若任务在带宽斜坡，增加算术峰值未必有效；减少数据移动或提高一次读取的复用才更贴近瓶颈。

## 为什么 Decode 容易带宽受限

每个 decode step 只为每条序列生成少量新 token，却要经过模型全部层并读取权重。batch 太小时，一次读权重只服务少量 token，算术强度低。增大活跃 batch 可提高复用，但会消耗更多 KV cache，并增加排队与尾延迟。

这就是在线推理的基本矛盾：

```text
更大 batch -> 通常吞吐更高
更长等待 -> TTFT 与尾延迟可能更差
```

## CUDA 是什么层

CUDA 包含编程模型、运行时、编译工具和库。PyTorch、vLLM 等框架通过 CUDA kernel 操作 GPU。日常部署不必自己写 kernel，但要理解：

- GPU 操作通常异步提交；
- 测时前后可能需要同步，否则只测到 launch；
- 不同 stream 可以重叠，但依赖必须显式满足；
- 第一次调用可能包含编译、图捕获或 cache warmup；
- allocator 可能保留显存，所以 `nvidia-smi` 不等于活跃 tensor 总和。

### 异步提交为什么容易测出虚假的加速

CPU 发出 kernel 后可能立即返回，GPU 还在计算。只用主机时钟围住 Python 调用，可能主要测到提交开销。应使用适当 CUDA 事件或同步边界测实际 GPU 工作，并区分 warmup 与稳定运行。

同步也会改变实验环境：逐个算子强制同步可能破坏原本重叠。先明确测的是单算子还是端到端吞吐，再选计时方式，不把两者结果混在一张表里。

## 看哪些硬件指标

| 指标 | 回答的问题 |
| --- | --- |
| SM / tensor core 利用 | 计算单元是否有工作 |
| HBM 带宽利用 | 是否在大量搬显存数据 |
| 显存占用 | 容量还有多少余量 |
| PCIe / NVLink 流量 | 多卡或 CPU-GPU 搬运是否重 |
| 功耗与频率 | 是否降频或受功率限制 |
| kernel 时间与空隙 | GPU 是否在等待 CPU 或调度 |

“GPU 利用率 100%”本身不能说明效率。一个低效 kernel 也能让卡一直忙。

## 第一条性能纪律

先记录工作负载，再记录硬件：模型版本、精度、输入输出长度分布、并发、batch 策略、GPU 型号、拓扑和软件版本。没有这些上下文的性能数字无法复现。

### 卡一直忙，为什么请求还很慢

GPU utilization 高说明采样期间设备有工作，不说明每秒完成多少有用 token。反复重算、低效内存访问或通信 kernel 都可能让卡忙。结合吞吐、HBM 流量和 kernel 时间判断，再看是否存在 CPU 等待空隙。性能结论需要工作负载形状作为背景，不能只比较一条利用率曲线。

## 来源入口

- NVIDIA GPU Performance Background
- CUDA C++ Best Practices Guide
- Roofline technical report
- FlashAttention paper
- PyTorch CUDA semantics
