# 训练循环与训练显存

夜间校对任务用人工修订的档案片段训练模型。一次参数更新要经过取样、前向计算、反向求导和优化器更新。把这些动作的边界画清楚，才能区分数据等待、激活峰值和状态占用。

下面是说明累积顺序的伪代码，不是可直接运行的训练器：

```text
清空本轮梯度
重复 K 次：取 micro-batch，计算并缩放 loss，累积梯度
按分布式策略完成需要的梯度同步
检查数值状态，执行一次参数更新
```

## 前向（Forward）

模型将输入位置转换为预测分布，并根据目标计算 loss。自动微分需要某些中间结果，因此 forward 结束后并非只留下一个 loss 数值。哪些结果保存、哪些可重算，决定后续激活内存。

样本掩码、padding 和目标移动也影响训练语义。一个更快但读错目标的 forward 不能算性能优化。

## 反向（Backward）

自动微分沿依赖关系计算梯度，读取保存结果或重新计算部分区域。分布式方案还可能在梯度就绪后逐批启动同步，而非等全部反向结束才开始通信。

观察到反向阶段很长时，要区分本地求导、重计算和同步等待。不同原因对应不同动作，不能全部归到“反向约为前向两倍”的粗略经验。

## 优化器更新（Optimizer Step）

以 AdamW 为例，更新需要参数、梯度及 moment，还可能有高精度主参数。更新边界通常也推动学习率计划和步数计数。若数值异常导致跳过更新，要明确这些计数怎样处理。

只保存模型权重可以用于某些推理场景，却不足以在同一优化状态继续训练。恢复需要的内容将在数据与检查点章节展开。

## Micro-batch、Global batch 与累积

简单同步数据并行下，一次更新的样本数等于每数据副本的 micro-batch 乘数据并行度，再乘累积次数。TP 或 PP 参与者共同处理同一份模型工作，不应再次乘入独立样本数。

累积允许每次前向使用较小输入，从而减少单次激活峰值。梯度要跨 micro-step 保留，loss 缩放和同步时机也要匹配，否则可能改变有效更新。

### 一次 optimizer step 究竟看过多少样本

设每个数据副本一次处理 3 份校对样本，共 4 个副本，累积 5 次，则更新前共处理 60 份样本。若每份恰好含 1024 个有效位置，对应 61,440 个有效 token。

每个 micro-step 都清梯度并更新，会变成五次不同更新，不再等价于这个 global batch。实际变长数据还应按有效 token 而非固定样本长度复核。

<figure class="diagram" tabindex="0" data-review-figure="infra-accumulation">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 396" role="img" aria-labelledby="infra-accumulation-title infra-accumulation-desc" style="display:block;width:100%;min-width:620px;height:auto">
<title id="infra-accumulation-title">5 次累积，只做 1 次参数更新</title>
<desc id="infra-accumulation-desc">每个 micro-step：每数据副本 3 个样本 × 4 副本 = 12；累积 5 次：12 × 5 = 60 个样本，梯度持续保留；一次 optimizer step：固定 1024 有效位置时共 61,440 token。示例为简单同步数据并行；TP、PP 不再乘入独立样本数。</desc>
<rect width="960" height="396" fill="var(--paper,#faf8f1)"/>
<g font-family="'IBM Plex Sans','Noto Sans CJK SC',system-ui,sans-serif"><text x="40" y="48" font-size="28" fill="var(--ink,#243b48)" text-anchor="start">5 次累积，只做 1 次参数更新</text><path d="M176 144 L176 164" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M171 157 L176 164 L181 157" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="40" y="88" width="272" height="56" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="56" y="123" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">每个 micro-step</text><text x="344" y="123" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">每数据副本 3 个样本 × 4 副本 = 12</text><path d="M176 224 L176 244" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M171 237 L176 244 L181 237" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="40" y="168" width="272" height="56" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="56" y="203" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">累积 5 次</text><text x="344" y="203" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">12 × 5 = 60 个样本，梯度持续保留</text><rect x="40" y="248" width="272" height="56" rx="6" fill="var(--paper-2,var(--paper-deep,#e5ede9))" stroke="var(--forest,var(--accent,#29564c))"/><text x="56" y="283" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">一次 optimizer step</text><text x="344" y="283" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">固定 1024 有效位置时共 61,440 token</text><path d="M40 332H920" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="40" y="368" font-size="18" fill="var(--muted,#536772)" text-anchor="start">示例为简单同步数据并行；TP、PP 不再乘入独立样本数。</text></g>
</svg>
<figcaption>图：示例为简单同步数据并行；TP、PP 不再乘入独立样本数。</figcaption>
</figure>

## 训练显存四大项

参数决定模型当前值，梯度记录本轮更新方向，优化器状态记录更新历史，激活支持本轮求导。前几项大体跟参数量相关，激活更直接依赖 micro-batch、序列形状及实现。

长期状态主导时考虑分片，激活主导时考虑缩小输入或重算。最好通过测量和对象清点确认主项，而不是根据模型标签预判。

## 激活重算（Activation Checkpointing）

选择边界保存少量结果，其余中间状态在反向需要时重新计算。它以额外运算换取更小保存集合，边界和分组粒度决定收益及成本。

采用后需比较峰值与完整 step 时间，还要确认随机性和数值路径按框架要求处理。某些区域计算昂贵却节省有限，不适合一概开启最大力度重算。

### 重计算省下的是激活，而不是所有训练状态

若本轮激活峰值为 8 GiB，而参数、梯度和优化器状态共 40 GiB，即使去掉大部分激活，40 GiB 仍然存在。这个教学账解释了为什么重算不能修复所有训练 OOM。

应优先分析占用大、重新生成成本相对低的中间结果。重算区域扩大后，还需复查数据供给和通信重叠是否改变了关键路径。

## 混合精度（Mixed Precision）

计算、累加、梯度和优化器可以采用不同精度。FP16 可能需要 loss scaling，BF16 具有不同指数范围和尾数精度，FP8 又依赖硬件及缩放方案。没有一条“全部转低精度”的规则适用于所有训练。

记录溢出、跳步、梯度范数和 loss，检查速度变化是否伴随训练不稳定。字节数下降只是其中一项结果。

## TorchTitan 的训练骨架

先从 `train.py` 及训练引擎追一步运行，再按职责进入 `components/data`、优化器组件、`distributed`、`components/checkpointer` 和可观测相关模块。目录组织属于版本事实，具体调用应以本地快照为准。

用一张步骤表记录何时取数、何时同步、何时更新及保存，比按目录逐文件通读更容易保留整体执行关系。

### step 变快，还要确认每步工作没有变少

把有效长度从 2048 减到 1024 会让步骤变短，但也可能把处理量减半。比较时保留 global batch、有效 token 数与训练目标，报告 tokens/s 和质量曲线，而不是仅展示 step 毫秒数。

保存间隔变化也会影响平均吞吐。只截取两次 checkpoint 之间最平稳的区间，不能代表完整作业成本。

## 训练吞吐看什么

一起记录有效 token 或样本速率、step 分解、各 rank 的尾部耗时、保存暂停和数值健康。若报告 MFU，说明运算量估算口径。吞吐数字必须能解释实际处理量，并能覆盖失败、保存和恢复的正常运维成本。
