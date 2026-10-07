# 显存账本：模型到底占多少

显存不足不是一个原因，而是一张账单的总和。先把账分栏，再决定量化、分片、减 batch 还是缩短上下文。

{{diagram:memory-ledger|推理和训练使用不同的显存账本。}}

## 推理账本

### 权重

```text
weights ≈ parameters × bits / 8
```

这是最稳定的一项。量化能降低它，但 scale、打包和某些层保持高精度会产生额外开销。

### KV Cache

它随活跃 token 数增长，而不是只由模型大小决定。相同模型在并发 1 和并发 100 下，KV 需求可能差两个数量级。

### 激活与 workspace

一次 forward 的中间 tensor、attention workspace、采样和通信 buffer。它们随 batch、token 数、kernel 和并行策略变化。

### 运行时保留

CUDA context、allocator cache、CUDA graph 内存池、编译产物和碎片。服务通常不能把权重加 KV 算到显存容量的 100%。

## 训练账本

训练需要：

- 权重；
- 梯度；
- 优化器状态，例如 Adam 的一阶和二阶矩；
- 混合精度下可能存在 FP32 master weights；
- forward 激活，供 backward 使用；
- 通信 bucket、临时 tensor 和 allocator 余量。

一个常见教学估算是混合精度 Adam 每参数约 16 bytes：2 bytes 权重、2 bytes 梯度、4 bytes master weight、8 bytes 两个 FP32 moment。实现不同，不能把 16 当作定律。

70 亿参数按 16 bytes 估算，训练状态约 104.31 GiB，还没算激活。这解释了为什么单卡能推理的模型，训练可能需要多卡分片。

### 权重放得下，不代表服务容量足够

以一张假设 24 GiB 卡为例，7B 的 16 位权重下界约 13.04 GiB。扣除权重后的十余 GiB，还要给 KV、激活、workspace 和运行时留位置。若只按权重判断可接多少请求，就忽略了随上下文和并发增长的主项。

训练还需梯度与优化器状态，因此同一模型从推理切到训练，账本发生结构变化。降低请求并发能减少推理 KV，却不能消除 Adam moments；选择措施前先确定要减少哪一栏。

## 激活为什么难用一个倍数表达

激活取决于 batch、序列长度、隐藏维度、层数、attention 实现和哪些 tensor 被保存。它与参数量不总是线性同倍增长。长序列训练中，激活可能成为主项。

Activation checkpointing 只保存部分边界，backward 时重算中间结果，以计算换显存。它不会减少权重或优化器状态。

## 已分配、已保留与可用

PyTorch caching allocator 会保留释放后的块供后续复用：

- allocated：活跃 tensor 实际占用；
- reserved：allocator 向 CUDA 申请并保留；
- free：设备报告未被当前进程保留的部分。

看到 OOM 时，要同时看峰值 allocated、reserved、碎片和失败分配大小。只在 OOM 后调用清 cache，通常治不了仍被活跃 tensor 占用的问题。

### 释放 tensor 后，reserved 为什么没有立刻下降

Python 不再持有一个 tensor，allocator 可以把其块留给后续分配，而不立即还给驱动。因此 allocated 降了、reserved 没降，可能是正常缓存。仍被引用的 tensor 则不能靠 empty_cache 消失。

加载即 OOM 多半先查权重与加载峰值；长请求运行后 OOM 再查 KV 与临时空间；长时间逐步增长则查引用与释放路径。三种症状都叫 OOM，减少同一个参数未必解决。

## OOM 排查顺序

1. 记录失败时的 batch、序列长度和并发。
2. 区分加载时 OOM、首次 forward OOM、稳定运行后 OOM。
3. 查看权重、KV、激活或临时 workspace 哪项随负载增长。
4. 检查是否有 tensor 引用泄漏或请求未释放。
5. 再选择量化、减 token budget、分片、checkpointing 或扩卡。

随机调 `gpu_memory_utilization` 只是在移动边界，不说明哪项失控。

## 用计算器建立量级感

```bash
python3 examples/infra_lab.py memory \
  --parameters 7 \
  --weight-bits 16 \
  --layers 32 \
  --kv-heads 8 \
  --head-dim 128 \
  --context 8192 \
  --concurrent-requests 8
```

默认输出的 8 GiB KV 是“每条请求都用满 8192 token”的上界场景。真实容量规划应使用长度分布和峰值并发，而不是把最大上下文乘平均并发。

### 预算要留给峰值，而不只是平均

平均上下文很短，少量长输入也可能在同一时刻占据大量块。容量估算应设代表性长度分布，再压测突发与极端组合。分页减少预留浪费，没有消除有效 token 和 workspace 的实际空间。

计算器输出是理论量级，未模拟 allocator、kernel 临时结果和所有并行 buffer。预测接近容量上限时，应更谨慎地增加余量，而不是把公式多保留几位小数当成精度保证。

## 一条安全规则

容量估算必须留下余量，并在目标软件版本上压测。公式决定是否值得尝试，实测决定是否上线。
