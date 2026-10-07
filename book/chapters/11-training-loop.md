# 训练循环与训练显存

训练基础循环只有四步：取数据、forward、backward、optimizer step。大模型训练系统的复杂性来自每一步都可能跨多卡，并且状态大到不能完整复制。

```python
for batch in dataloader:
    optimizer.zero_grad()
    loss = model(batch)
    loss.backward()
    optimizer.step()
```

## Forward

输入 token 经过 embedding 和每层 Transformer，得到 logits 与 loss。为 backward 计算梯度，框架通常保留部分中间激活。

## Backward

自动微分按计算图反向计算参数梯度。Backward 不是 forward 的简单倒放，它可能需要读取保存激活、重算 checkpointed 区域，并在数据并行 rank 间同步梯度。

## Optimizer Step

AdamW 读取权重、梯度和两个 moment，更新参数。优化器状态体积大，且是训练 checkpoint 的主要组成部分之一。

## Micro-batch、Global batch 与累积

```text
global batch
= micro batch per GPU × data parallel degree × accumulation steps
```

梯度累积让每卡用较小 micro-batch 多跑几次 forward/backward，再做 optimizer step。它降低单次激活峰值，但增加每个 step 的串行 micro-step 数。

必须记录 batch 的口径，否则学习率和吞吐都无法比较。

### 一次 optimizer step 究竟看过多少样本

每个 DP rank 的 micro-batch 为 2，DP 度为 8，累积 4 次后更新，则 global batch 为 64。TP 或 PP rank 协同处理同一份模型工作，不能再把它们当作额外独立样本乘进去。比较吞吐和学习率时，必须使用相同 batch 口径。

累积降低单次激活峰值，但梯度要在更新前正确累计，loss 缩放与同步策略也要匹配。不能简单重复四次普通循环而每次都清梯度并 step，那会成为四次不同的优化器更新。

## 训练显存四大项

1. 模型参数；
2. 梯度；
3. 优化器状态；
4. 激活。

前 3 项主要随参数量增长，激活主要随 micro-batch、序列长度、层和实现增长。FSDP/ZeRO 主要分片前 3 项，activation checkpointing 主要减少第 4 项。

## Activation Checkpointing

普通做法保存中间激活，用空间换 backward 速度。Checkpointing 只保存选定边界，backward 时重新 forward 该段。

```text
少存激活 -> 显存下降
重新计算 -> step 时间上升
```

选择粒度太粗，重算多；太细，边界和调度开销增加。应按层或算子成本 profile。

### 重计算省下的是激活，而不是所有训练状态

forward 保存每层中间结果方便 backward，但占显存；checkpointing 只留边界，反向需要时重新算该段。参数、梯度与 optimizer moments 仍存在，所以状态主导的 OOM 不会只靠重算消失。

选择区域时看保存字节与重算成本。很便宜又很占空间的中间结果适合重算，昂贵区域则可能拖慢 step。随机操作与实现细节也需正确处理，数值训练不能只验证程序没报错。

## Mixed Precision

模型计算可用 BF16/FP16/FP8，部分归约和优化器状态保留更高精度。混合精度的目标不是“所有 tensor 都变小”，而是在数值稳定、硬件吞吐和显存间取平衡。

FP16 训练常需要 loss scaling 防止小梯度下溢。BF16 指数范围更大，但尾数精度较低。具体策略由模型、硬件和框架决定。

## TorchTitan 的训练骨架

当前源码把职责拆为：

- `train.py` / training engine：驱动 step；
- `components/data`：数据源与 dataloader；
- `components/optimizer`：优化器与 scheduler；
- `distributed`：并行维度和 mesh；
- `components/checkpointer`：保存恢复；
- `observability`：日志、metrics、profiling。

阅读时先画每 step 时间线，再进入并行模块。

### step 变快，还要确认每步工作没有变少

缩短序列或减少 global batch 会降低 step 时间，但改变了处理的数据量。tokens/s、有效样本数和 loss 曲线一起比较，才能判断优化是否保留训练语义。混合精度也要观察数值异常，速度提升不应以模型无法收敛为代价。

GPU 空隙可能来自 dataloader、通信或 checkpoint。将一次 step 拆成取数、前向、反向、更新和保存，再找最长等待段，比先替换某个 kernel 更容易解释结果。

## 训练吞吐看什么

- samples/s 或 tokens/s；
- model FLOPs utilization，但要统一计算口径；
- step time 及 data/forward/backward/optimizer/communication 分解；
- straggler rank；
- checkpoint pause；
- loss 和梯度健康度。

只追求 GPU 利用率可能把数据错误、数值发散和 checkpoint 失败藏起来。
