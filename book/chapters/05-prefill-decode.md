# 推理的两幕：Prefill 与 Decode

自回归模型不是一次吐出整段答案。它先读取全部提示词建立内部状态，然后一轮一轮生成后续 token。这两段在 GPU 上的形状不同，指标也不同。

{{diagram:prefill-decode|Prefill 同时处理提示词，Decode 每轮推进一个生成位置。}}

## Prefill 做什么

假设 prompt 有 2000 个 token。Prefill 会让这些 token 通过模型各层，计算注意力并写入 KV cache。它能形成较大的矩阵乘，并行度较高，常更接近计算密集。

Prefill 的直接用户指标是 TTFT，也就是从请求进入系统到第一个输出 token 出现的时间。TTFT 包含的不只是 prefill：

```text
TTFT = 网关 + 排队 + tokenize + prefill + 首 token 回传
```

因此 TTFT 高时不能直接断言 prefill 慢。

## Decode 做什么

第一个 token 生成后，新 token 被追加到上下文。下一轮只新增一个位置，但它需要读取历史 KV，并经过模型所有层。过程重复到停止条件。

用户感受到的生成流畅度常用：

- TPOT：每个输出 token 的平均时间；
- ITL：相邻 token 的延迟，可看分布；
- output tokens/s：单请求或系统总生成吞吐。

如果中途某几轮突然变慢，平均 TPOT 可能掩盖卡顿，应看 ITL 分位数和时间序列。

### 读取长题目和续写长答案，是两种压力

长 prompt 的多个位置可以在 prefill 中并行处理，但生成的新位置依赖前一轮结果，单条序列不能一次并行写出全部答案。将许多序列一起 decode，能提高跨请求并行度，却没有消除每条序列内部的顺序依赖。

因此长输入短答案常把压力放在首 token 之前，短输入长答案则可能首 token 很快、后续占卡很久。总耗时相近的两种请求，对调度和产品体验要求不同。

## 为什么不能只优化一个阶段

增大 prefill chunk 可以更快吃完长 prompt，却可能让 decode 请求等待更久。优先 decode 可改善正在生成用户的流畅度，却让新请求 TTFT 上升。

调度器必须在以下目标间取舍：

- 新请求尽快拿到首 token；
- 已开始的请求稳定生成；
- GPU 保持高利用；
- KV cache 不超容量；
- 长请求不能饿死短请求，反之亦然。

## Chunked Prefill

长 prompt 不必在一个 iteration 全部处理。可以拆成 chunk，与 decode token 共享每轮 token budget。这样减少一次巨大 prefill 阻塞，但增加调度轮数和策略参数。

`max_num_batched_tokens` 一类配置本质上在控制每轮工作量。设置大通常偏吞吐，设置小可能偏交互延迟，但结果依赖模型、硬件和长度分布。

### 切小 prefill 怎样帮助正在生成的用户

假设当前有十条序列等待下一 token，新长 prompt 一次占用很大的迭代工作量，它们会等本轮结束。把 prompt 拆成 chunk，调度器可以在轮次之间给 decode 留份额，减少长输入连续阻塞。

切分也有代价：更多轮次与管理，且新请求读完整 prompt 才能生成首 token。不能同时保证所有长度的 TTFT、ITL 和最大吞吐都最优，需要按真实流量确定优先目标。

## Prefill/Decode 分离

更大规模服务可让不同 worker 分别处理 prefill 和 decode，再传输 KV。优点是两类负载可独立扩缩和调优，缺点是需要高速 KV 传输、路由和故障处理。

判断是否值得分离前先量化：

- prefill 与 decode 各自占多少 GPU 时间；
- KV 传输量和互联带宽；
- 长 prompt 是否真的干扰 decode；
- 分离后的空闲和排队是否更少。

复杂架构不能凭示意图证明更快。

## 一个简单类比

Prefill 像读完题目并做笔记，Decode 像每次只写一个字但不断翻阅笔记。题目长会推迟开写，答案长会延长逐字生成。

### 分离前先算 KV 交接的成本

Prefill worker 处理完以后，decode worker 需要历史 KV。其传输量由上下文、层数、KV heads 和精度决定，不是只发几个 token ID。长文的计算节省若被网络传输吃掉，拆开两组 worker 可能更慢。

因此先测两阶段 GPU 时间和传输量，再比较独立调度的收益。低流量下两组都可能空闲，多增加一条故障与路由链，也应计入采用成本。

## 观测建议

至少分别记录：prompt tokens、output tokens、queue time、prefill time、decode time、TTFT 和 TPOT。只记录总延迟无法解释是长输入、长输出还是排队造成。
