# KV Cache：上下文为什么越来越贵

注意力层生成新 token 时需要参考之前位置的 key 和 value。重复计算全部历史很浪费，所以推理引擎把每层历史 K/V 保存下来。这就是 KV cache。

## 先记公式

对常见 Transformer，单个 token 的 KV 下界约为：

```text
KV bytes/token
= 2 × layers × kv_heads × head_dim × bytes_per_element
```

前面的 2 表示 K 和 V。全部活跃序列：

```text
total KV ≈ bytes/token × active tokens
```

例：32 层、8 个 KV heads、head dim 128、BF16：

```text
2 × 32 × 8 × 128 × 2 = 131,072 bytes/token
```

也就是每 token 128 KiB。总共 131,072 个活跃 token 时，理论 KV 正好约 16 GiB。

## Active tokens 是什么

它是当前仍在服务中的所有序列已缓存 token 总和，不等于每秒输入 token，也不等于配置的最大上下文。一个完成的请求释放 KV 后，block 可给新请求复用。

容量规划应关注分布：

- 同时活跃多少请求；
- 每条请求当时已经走到多长；
- prefix cache 是否共享前缀 block；
- speculative decoding 是否增加临时状态；
- KV 使用什么精度。

### 容量统计是一张随时间变化的照片

一条请求读完 2000 token、又生成 100 token，缓存覆盖约 2100 个位置；另一条只到 500。即使二者最大上下文都设置 8192，当前有效 KV 不是两个最大值相加。请求完成后释放或进入受管理缓存，后续占用又会变化。

按本章 128 KiB/token 的例子，一条 8192 token 序列理论约 1 GiB，八条都走到该长度约 8 GiB。这个算例说明为什么上下文和并发要一起看，不能把最大值乘平均并发当成可靠峰值。

## 连续大块为什么浪费

如果为每条请求预留最大上下文的连续区域，短请求会留下大量内部浪费，不同长度释放后还可能形成外部碎片。请求长度不可预测，使传统连续分配很难保持高利用。

{{diagram:kv-pages|PagedAttention 把逻辑 KV 序列映射到固定大小的物理 block。}}

PagedAttention 借鉴虚拟内存分页：逻辑上连续的 KV 可以放在不连续物理 block，block table 负责映射。请求增长时按需增加 block，结束后归还。

它减少碎片和预留，不改变每个有效 token 必须保存 KV 的事实。

## Block 大小的权衡

- block 大：表更小、管理开销低，但最后一个 block 浪费更多；
- block 小：碎片少，但元数据、分配和 kernel 处理更复杂。

实际引擎还要考虑对齐、kernel 支持和 prefix cache，因此不是越小越好。

## 手算分页的最后一块

假设每块容纳 16 个 token，三条互不共享前缀的活跃序列分别缓存 17、31、32 个 token。它们各需 2、2、2 块，共分配 96 个 token 槽位，实际写入 80 个，末块空余 16 个槽位：

{{diagram:kv-block-budget|三个请求都需要两块，但末块的空槽随长度不同而变化。}}

这里的空槽是分页内部碎片，不是额外的有效 KV token。按本章 128 KiB/token 的理论值计算，已写入 KV 约 10 MiB，若物理块在分配时完整占用，96 个槽位对应约 12 MiB 的块容量。实际预留和统计还取决于引擎的块分配、对齐、缓存复用及其他显存开销。不要把“节省最大上下文预留”误写成“没有碎片”。

### block table 怎样保持逻辑连续

请求的第 0、1、2 个逻辑块可以对应物理池中的不同位置，attention kernel 根据映射访问，而不是要求显存连续。请求增长时只补下一块，其他请求释放的块可以重新利用。这减少因最大长度预留和不连续空洞造成的浪费。

最后一块仍可能未填满，metadata 与访问也有成本。分页优化的是分配组织，没有让同一个有效位置的 K/V 凭空变小；KV 精度和头数才影响公式里的单位大小。

## Prefix caching

很多请求共享相同 system prompt 或文档前缀。若 token 与模型配置完全匹配，可复用已有 KV block，减少重复 prefill。

它不是普通文本 cache：chat template、token IDs、模型版本、LoRA、位置和多模态输入都可能影响可复用性。cache key 不完整会得到错误结果。

## 抢占与重计算

KV 不足时，引擎可能暂停低优先级序列，释放或换出其 cache，之后重算或恢复。这样能避免立即拒绝请求，但会增加延迟和重复计算。监控 preemption 数量比只看 OOM 更早发现容量压力。

### 前缀共享与最终答案缓存的差别

相同 token 前缀能复用对应计算，后续问题不同仍要继续 prefill 或 decode。模型版本、位置处理或 adapter 变化后，即使文字相同也不一定可复用。命中率高只说明复用机会多，最终答案质量与输出速度还受剩余计算影响。

抢占后重算又可能重复读取同一段历史，提升可用性却降低有效吞吐。观察 block 使用率、抢占和重复计算，才能知道服务是否接近容量压力，而不必等到 OOM。

## 源码阅读路线

vLLM 快照中的关键入口：

```text
vllm/v1/core/kv_cache_manager.py
vllm/v1/core/kv_cache_utils.py
vllm/v1/core/block_pool.py
vllm/v1/attention/
```

阅读时追三个问题：谁请求 block、block 如何映射到请求、请求结束或抢占时谁释放。

## 常见误区

- 最大上下文从 32K 改到 128K，不代表必须立即预留四倍 KV，但允许单请求增长到更大上限。
- 量化权重到 INT4，不会自动量化 KV。
- GPU 显存还有空间，不代表 block 配置允许继续调度。
- KV cache 命中不是最终答案 cache，仍要执行后续 decode。
