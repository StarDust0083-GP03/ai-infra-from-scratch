# 数据管道与 Checkpoint

昂贵 GPU 等数据，是最容易被误认为“模型慢”的问题之一。训练系统还必须定期保存足够状态，以便故障后恢复，而不是从第 0 步重来。

## 数据路径

```text
对象存储 / 文件系统
  -> shard 列表
  -> worker 读取与解码
  -> tokenize / pack
  -> host memory
  -> H2D copy
  -> GPU batch
```

每一段都可能产生背压。GPU 空闲时先看 dataloader queue 和 copy 时间，不要立即改模型 kernel。

## Sharding 与顺序

数据并行 rank 应读取不同样本，又要保证：

- epoch 覆盖正确；
- shuffle 可复现；
- resume 后不大量重复或漏数据；
- worker 数变化时语义明确；
- 不同长度样本 packing 策略一致。

只保存 global step 不一定能恢复数据位置。dataloader 或 sampler state 也是 checkpoint 的一部分。

### 从同一 step 恢复，为什么还可能读到不同数据

global step 只表示完成了多少更新，不完整描述哪个 shard、sample 或随机排列已被消费。恢复时若 sampler 从头开始，程序能继续，却可能重复大量样本；改变 worker 数也可能改变切分。等价恢复需要数据位置和随机状态与模型状态一起对应。

输入 packing 还影响有效 token 数。相同样本数若使用不同长度合并规则，batch 形状和训练吞吐都会变化。数据版本与读取策略属于运行合同，不应只记录模型 commit。

## Checkpoint 保存什么

一次可恢复训练通常需要：

- 模型参数；
- optimizer state；
- learning-rate scheduler；
- 当前 step；
- RNG state；
- data loader/sampler state；
- loss scaler 或其他数值状态；
- 并行与模型配置；
- 代码和数据版本引用。

漏掉 RNG 与数据位置，程序仍能继续跑，但不再是等价恢复。

## 分布式 Checkpoint

大状态不应由 rank 0 收集后写一个巨型文件，这会造成内存峰值和单点瓶颈。分布式 checkpoint 让各 rank 写 shard，并保存可描述全局 tensor 的 metadata。

恢复到不同 world size 时，需要 reshard。格式应表达全局 shape 和 shard placement，而不是把当前 rank 编号写死成长期合同。

## 一致性与原子提交

一个可用 checkpoint 应满足“要么完整可见，要么不可见”。常见过程：

1. 各 rank 写临时 shard；
2. 校验完成和大小；
3. 写 metadata；
4. 最后提交完成标记或原子重命名；
5. 更新 latest 指针。

若只看目录存在就恢复，可能读到一半成功的 checkpoint。

### 完成标记为什么要最后写

四个 rank 只有三个 shard 写完，目录已经存在但 checkpoint 不完整。恢复端应读取已提交 metadata 与完成状态，而非猜目录里有哪些文件。临时对象可保留用于诊断，但不能更新 latest 指针让新任务误用。

异步保存也需要稳定快照：训练继续修改 GPU 参数时，后台应写已 stage 的一致数据，不能拿变化中的 tensor 引用边读边存。CPU 内存和拷贝时间是缩短 GPU 暂停所付出的代价。

## 同步与异步保存

同步 checkpoint 停止训练直到写完，简单但产生 pause。异步方案先把 GPU 状态 stage 到 CPU，再后台写存储，缩短 GPU 停顿。

代价是额外 CPU 内存、拷贝带宽和并发控制。训练继续修改参数时，后台必须写稳定快照，不能引用正在变化的 tensor。

## 保存频率怎么算

checkpoint 间隔是成本权衡：

```text
期望丢失工作 ≈ checkpoint interval / 2
```

间隔越短，存储和 pause 越多；越长，故障重算越多。还要考虑故障率、恢复时间、作业价值和存储带宽。

## 推理也需要持久化吗

模型权重是推理的主要持久状态，在线请求通常不靠 GPU checkpoint 恢复。长时异步任务可在应用层保存输入、已生成位置、随机状态或业务进度，但跨引擎恢复 KV cache 更复杂，未必值得。

### 保存频率在正常开销与失败损失之间取舍

每分钟都存可以减少故障回退，却可能让存储和 CPU staging 长期繁忙；每几小时存一次，正常更快，失败时损失更多计算。先测一次保存成本、故障频率和可接受回退，再设间隔，不照搬另一个集群的默认值。

恢复到不同 world size 还要求格式描述全局 tensor 与 shard 位置。实际演练加载、恢复数据位置并做小步验证，比“文件大小正确”更能证明备份可用。

## 源码入口

- `torchtitan/components/data/`
- `torchtitan/components/checkpointer/`
- `megatron/core/dist_checkpointing/`
- PyTorch Distributed Checkpoint 文档

先看 state dict 如何声明，再看 planner、storage writer 和 reshard，不要只看最终文件名。
