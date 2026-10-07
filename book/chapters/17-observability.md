# 可观测性、SLO 与成本

可观测性的目标不是把每个 exporter 指标搬进 Dashboard，而是能从用户问题一路定位到队列、引擎、GPU、网络或存储。

{{diagram:latency-waterfall|端到端延迟必须拆成等待、Prefill 与 Decode。}}

## 用户层指标

### TTFT

首 token 延迟，受网关、排队、tokenize 和 prefill 共同影响。交互式应用通常对它最敏感。

### TPOT / ITL

生成阶段每 token 时间或 token 间隔。看 p50、p95、p99 和时间序列，避免平均值掩盖卡顿。

### E2E latency

从请求开始到完成。它强烈受输出长度影响，应按输入输出 token 分桶。

### 成功率与取消率

区分限流、队列超时、客户端取消、引擎错误、OOM 和内容策略拒绝。把所有非 200 合并会失去行动方向。

## 引擎层指标

- waiting/running/preempted requests；
- input/output tokens/s；
- KV cache utilization 与 block 分配失败；
- prefix cache hit；
- iteration time；
- prefill/decode token 数；
- scheduler time、model execution time、sampling time。

当 TTFT 上升时，先看 queue time 还是 prefill time。若 queue 上升但 GPU tokens/s 没变，容量已饱和；若 GPU 有大量空隙，瓶颈可能在 CPU 或通信。

### 同样 TTFT 上升，可能需要完全不同的行动

队列时间升高、引擎吞吐稳定，可能已到容量上限，需扩容或限制输入；prefill 时间随长文变大，可能需要分桶或调 chunk；GPU 有空隙而 tokenizer 繁忙，则要修 CPU 路径。总延迟只显示症状，分段指标才提供行动依据。

ITL 也要按请求观察。系统平均输出速率很好，一部分长请求仍可能频繁被抢占，用户感到停顿。吞吐指标与体验指标分别保留，不用总体平均值替代所有租户的尾延迟。

## GPU 与系统指标

- SM、tensor core、HBM 带宽；
- 显存 allocated/reserved；
- NVLink/PCIe/NIC 流量和错误；
- 功耗、温度、频率、ECC/Xid；
- CPU、NUMA、pinned memory；
- 磁盘与对象存储吞吐；
- Pod restart 和节点压力。

指标要与 run/request trace 关联，否则只能看到“卡忙”，不知道服务了哪种请求。

## Little's Law

稳定系统中：

```text
L = λ × W
```

- `L`：系统内平均请求数；
- `λ`：平均到达率；
- `W`：平均停留时间。

它帮助做量级检查：每秒到达 10 请求，平均停留 2 秒，系统内约有 20 个请求。若实际队列持续增长，输入率已超过完成率，扩容、限流或降级必须发生。

### Little's Law 的时间范围要对应同一个系统

若 L 统计引擎内活跃与等待请求，W 也应统计进入引擎到离开的时间，而不能拿完整网络耗时代入。到达率和平均值也需来自相近稳定窗口；队列持续增长时，不能用短时数据假装系统已有稳定工作点。

它适合量级核对，不自动给出所需 GPU 数。知道平均同时有二十条请求，还要了解它们的长度、prefill 与 decode 组成以及每副本可服务能力。

## SLO 不能只有一个数字

一个可操作的 SLO 示例：

- 对 prompt 低于 2K、输出低于 512 的交互请求；
- 月度 99.9% 成功；
- p95 TTFT 小于 1.5 秒；
- p95 TPOT 小于 60 ms；
- 排除用户主动取消，但不排除服务端过载拒绝。

先定义流量类别和测量窗口，再谈目标。超长上下文应有独立 SLO 或异步产品形态。

## 成本指标

只看每 GPU 小时价格无法比较系统。更有用：

```text
cost per 1M input tokens
cost per 1M output tokens
cost per successful request class
```

还要计入闲置、冷启动、重复计算、模型下载、存储和跨区流量。低利用率副本可能是为了低 TTFT 保留的必要容量，不应简单视为浪费。

### 成本分母也应该代表有用结果

过载重试与抢占重算都消耗 GPU，却没有增加同等数量的成功请求。只按总处理 token 计算成本，可能把重复工作当高效率。可以同时统计计费量、有效输出和成功请求类别，解释成本变化来自量化、利用率还是失败减少。

低流量保留预热副本会提高每 token 成本，却可能是低 TTFT 的必要代价。比较政策时固定 SLO 与流量，而不是让较慢系统凭关闭全部备用容量获得便宜结论。

## Cardinality 警告

不要把 request ID、完整 prompt、用户 ID 或任意模型参数放进 metrics label。高基数会拖垮监控系统，也可能泄露敏感数据。细粒度信息进入受控 trace/log，指标保留有限维度。

## 一张最小 Dashboard

1. 到达率、完成率、拒绝率；
2. TTFT/TPOT/E2E 分位数；
3. waiting/running 与 KV 使用；
4. input/output tokens/s；
5. GPU compute/memory/bandwidth；
6. 错误按阶段分类；
7. 副本数、冷启动和版本；
8. 每百万 token 成本。

先保证每个图能回答一个运维问题，再增加面板。
