# 连续批处理：GPU 如何同时服务很多人

传统静态 batch 等一组样本全部完成再换下一组。在线生成的请求长短差异很大，如果等待最长请求，短请求完成后的计算槽位会空着。

{{diagram:continuous-batching|连续批处理在迭代边界移出完成请求，并接纳新请求。}}

## iteration-level scheduling

自回归 decode 天然分轮。推理引擎可以在每轮重新决定 batch：

1. 找出仍在运行的序列；
2. 接纳等待请求或 prefill chunk；
3. 检查 token budget 和 KV block；
4. 生成本轮模型输入；
5. GPU 执行；
6. 更新序列状态，释放完成请求。

这就是连续批处理的核心。它不是把 HTTP 请求简单合成一个列表，而是在生成过程中不断重组工作。

## 三个约束

### Token budget

一轮最多处理多少 token。Decode 序列通常各贡献一个新位置，chunked prefill 可能贡献许多位置。

### Sequence 数量

活跃序列越多，调度和 metadata 开销越大，也占更多 KV。即使 token budget 还有余量，也可能受最大序列数限制。

### KV block

新请求只有能分配需要的 block 才能前进。KV 压力会触发等待、抢占、重算或拒绝。

### 这一轮有 token 预算，为什么还是进不了新请求

假设一轮允许 128 个 token，20 条 decode 序列各占一个位置，理论还剩 108。新 prompt 可以切入这部分，但只有 KV 池能提供需要的块、序列数没到上限时才能执行。三个约束限制不同对象，空着一项不代表其他项也有余量。

下一轮某条请求结束，它的计算位置和可释放 KV 才能给新请求。连续批处理因此需要随结果更新资源，不是把到达的 HTTP 请求一次拼起来后始终保持 batch 不变。

## 策略不是只有 FIFO

引擎可考虑到达顺序、优先级、已完成进度、请求长度和 SLA。不同策略会改变公平性：

- 优先短请求可降低平均延迟，长请求可能饥饿；
- 优先 decode 可保持流畅，新的长 prompt TTFT 上升；
- 优先已运行请求可减少抢占，但高优请求响应不够快。

产品应定义优先级语义，引擎参数只是实现手段。

## 为什么吞吐和延迟会冲突

等待更多请求形成大 batch，可提高权重复用和 GPU 效率，但每个请求先在队列里多等。低流量下强行等待 batch 往往得不偿失，高流量下不做 batching 又浪费 GPU。

服务需要在真实到达率下找工作点，而不是只跑“无限并发”吞吐 benchmark。

### 最大吞吐实验为什么不代表真实等待

持续灌满请求可以测接近饱和时的 token 吞吐，却无法说明低流量用户等多久。为了攒大 batch 额外等待，在饱和时不明显，在每秒只有少量请求时可能成为主要延迟。

评测应同时给出到达率、长度分布和延迟分位数。短任务优先降低平均值，却可能让长任务反复被推迟；加优先级后还要检查饥饿与租户公平，不能只盯总体 tokens/s。

## 玩具模拟器

```bash
python3 examples/infra_lab.py simulate
```

模拟器每轮先给可 decode 请求一个 token，再用剩余 token budget 做 chunked prefill，并用固定 block 管理 KV。它故意省略模型执行时间，帮助观察调度顺序。

试着修改 `token_budget`：

- 预算太小，长 prefill 需要更多轮，TTFT 上升；
- 预算变大，prefill 更快，但真实系统中一次 iteration 可能更长；
- block 太少，模拟会没有进展，对应真实系统的 KV 容量压力。

## vLLM 源码地图

```text
vllm/v1/core/sched/scheduler.py
  -> 选择 running / waiting 请求
  -> 向 KVCacheManager 请求 slot
  -> 生成 SchedulerOutput

vllm/v1/engine/core.py
  -> 驱动 schedule -> execute -> update 循环

vllm/v1/worker/gpu_model_runner.py
  -> 把调度输出变成 GPU 输入并执行模型
```

源码会随版本变化，但“选择工作、分配缓存、执行、更新”的循环稳定。

### 读调度源码时追一条请求的资源变化

从等待队列选中请求，查看本轮分了多少 token、申请了哪些 block；执行后再看计数推进、完成释放或抢占。调度输出与模型执行结果分开核对，才能发现“选中了但没推进”或“结束了却没释放”。玩具模拟器只演示这种关系，没有真实 kernel 和网络时间，不能据此预测某张 GPU 的性能。

## Benchmark 应记录什么

至少固定：模型、精度、输入输出长度分布、到达过程、最大并发、token budget、KV 配置、是否 prefix cache、是否流式。只报 requests/s 无法比较不同长度的工作负载，最好同时报告 input/output tokens/s 和延迟分位数。
