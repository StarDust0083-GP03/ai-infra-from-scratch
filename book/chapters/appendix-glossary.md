# 附录 A：术语、公式与命令速查

这页用于回查正文里的账本与数据关系。记住 AllGather 的名字，还要能指出各 rank 原有什么、操作后拿到什么；记住 KV 公式，还要知道它只覆盖缓存，而非全部推理显存。公式的每个乘数都是一个实际维度，不能脱离模型结构套用。

命令输出也按层解读：设备可见不代表模型已加载，Pod Running 不代表 rank group 就绪。回到具体请求或训练 step，沿数据和等待路径定位，速查才会成为理解的辅助。

## 基础术语

| 术语 | 一句话解释 |
| --- | --- |
| Token | 模型处理文本的离散 ID 单元 |
| Tensor | 带 shape 和 dtype 的多维数字数组 |
| Parameter | 训练得到并长期保存的模型 tensor |
| Activation | forward 中产生、供后续层或 backward 使用的中间结果 |
| Gradient | loss 对参数的导数 |
| Optimizer state | Adam moment 等用于更新参数的状态 |
| HBM | GPU 高带宽显存 |
| Kernel | 在 GPU 上执行的计算程序 |
| Stream | CUDA 异步操作的有序队列 |
| Rank | 分布式进程的编号 |
| World size | 一次分布式作业中的 rank 总数 |
| Collective | 多个 rank 共同参与的通信操作 |

## 推理术语

| 术语 | 一句话解释 |
| --- | --- |
| Prefill | 处理 prompt 并建立 KV cache |
| Decode | 逐轮生成后续 token |
| KV Cache | 保存历史 key/value，避免重复计算 |
| PagedAttention | 用固定 block 管理逻辑连续 KV |
| Continuous batching | 每轮动态移出完成请求、接纳新请求 |
| TTFT | 请求到第一个输出 token 的时间 |
| TPOT | 平均每个输出 token 的时间 |
| ITL | 相邻输出 token 的延迟 |
| Prefix cache | 复用完全匹配前缀的 KV block |
| Preemption | KV 压力或优先级导致序列暂停/重算 |

## 并行术语

| 缩写 | 切分方向 | 主要通信 |
| --- | --- | --- |
| DP | batch / 请求 | 训练常 AllReduce 梯度 |
| TP | 单层 tensor | 每层 AllReduce/AllGather 等 |
| PP | 模型层 | stage 间激活 |
| CP | 序列 | attention 所需跨卡数据 |
| EP | MoE expert | AllToAll token 路由 |
| FSDP | 参数、梯度、优化器 | AllGather + ReduceScatter |

## 显存公式

### 权重

```text
weight bytes ≈ parameters × bits_per_weight / 8
```

### KV Cache

```text
KV bytes
≈ 2 × layers × kv_heads × head_dim
  × active_tokens × bytes_per_element
```

### 常见混合精度 Adam 教学估算

```text
training state ≈ parameters × 16 bytes
```

这项不含激活、通信 buffer、临时 tensor 和 allocator 余量，具体实现必须实测。

### Global batch

```text
global batch
= micro batch per GPU × data parallel degree × accumulation steps
```

### Little's Law

```text
average in-flight requests = arrival rate × average time in system
L = λW
```

## 常用检查

### GPU 与拓扑

```bash
nvidia-smi
nvidia-smi topo -m
nvidia-smi -q
```

### Kubernetes

```bash
kubectl describe node <node>
kubectl get pods -A -o wide
kubectl describe pod <pod>
kubectl get events --sort-by=.lastTimestamp
```

### 本书离线实验

```bash
python3 examples/infra_lab.py memory
python3 examples/infra_lab.py simulate
```

## 症状速查

| 症状 | 先查什么 |
| --- | --- |
| 加载时 OOM | 权重精度、分片、runtime 余量 |
| 运行一段时间 OOM | KV 增长、请求释放、allocator 峰值 |
| TTFT 高 | 网关/引擎排队、prompt 长度、prefill |
| TPOT 高 | decode batch、权重带宽、TP 通信 |
| GPU 利用率低 | CPU tokenizer、数据、同步、queue |
| 多卡比单卡慢 | 消息大小、拓扑、collective、每卡工作量 |
| 训练卡在 NCCL | 其他 rank 首错、调用顺序、网络 |
| Pod 一直 Pending | GPU allocatable、队列、affinity、gang |
| 冷启动很慢 | 权重存储、并发下载、load、compile、warmup |
| checkpoint 无法恢复 | 完成标记、版本、world size、reshard、数据状态 |
