# 附录 B：源码地图、来源与版本说明

## 机制、算例与实测分别说明什么

正文依据来源解释引擎、通信和控制面的职责；手算 tensor、显存和 Roofline 使用显式假设，证明数量关系；标准库实验演示预算与请求推进。它们都不构成目标 GPU 上的性能测试，也没有验证真实多节点训练或 Kubernetes 部署。

迁移到实际模型时，应补目标精度 kernel、长度分布、通信拓扑和故障恢复实验。优先保留单卡与简单配置基线，每次只改变一项，才能判断优化结果来自哪条机制。

## 本地源码快照

快照日期：2026-09-22。

| 项目 | Commit | 重点目录 |
| --- | --- | --- |
| vLLM | `ca831d1c5571` | `vllm/v1/core`、`vllm/v1/engine`、`vllm/distributed` |
| TorchTitan | `7349a2282d9e` | `torchtitan/distributed`、`components`、`observability` |
| Megatron-LM | `c343bb6d337e` | `megatron/core/*_parallel`、`dist_checkpointing` |
| NCCL | `12df1a11afad` | `src/graph`、`transport`、`enqueue`、`ras` |
| NVIDIA Device Plugin | `3dd82d32e62c` | `internal/plugin`、`rm`、`mig` |
| Volcano | `d1fe35ed58fc` | `pkg/scheduler`、`controllers` |
| KubeRay | `e76908b64fc3` | `ray-operator`、`config/prometheus` |

完整 URL、提交、文件与代码统计在 `sources/inventory.json`。仓库均为官方 GitHub 浅克隆，遵循各自许可证。

## 官方材料

URL 索引和本地归档：

```text
sources/web/sources.tsv
sources/web/*.md
```

主要材料：

1. vLLM architecture、PagedAttention、optimization、distributed serving、parallelism。
2. PyTorch Distributed Overview、FSDP2、CUDA semantics、Distributed Checkpoint。
3. TorchTitan 官方文档与仓库 README。
4. NVIDIA GPU Performance Background、CUDA Best Practices、NCCL Overview。
5. Kubernetes Schedule GPUs 与 NVIDIA Device Plugin。
6. Volcano architecture、plugins 与 gang scheduling。
7. Ray on Kubernetes / KubeRay。
8. Hugging Face GPU memory anatomy 与单 GPU 训练性能指南。

## 论文

- Kwon et al., *Efficient Memory Management for Large Language Model Serving with PagedAttention*，arXiv:2309.06180。
- Shoeybi et al., *Megatron-LM: Training Multi-Billion Parameter Language Models Using Model Parallelism*，arXiv:1909.08053。
- Rajbhandari et al., *ZeRO: Memory Optimizations Toward Training Trillion Parameter Models*，arXiv:1910.02054。
- Dao et al., *FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness*，arXiv:2205.14135。
- Williams, Waterman, Patterson, *Roofline: An Insightful Visual Performance Model for Floating-Point Programs and Multicore Architectures*，DOI:10.2172/1407078。

论文摘要和元数据归档在 `sources/web/`。本书用它们确认设计动机，不复制论文图表。

## 建议的源码阅读顺序

### vLLM 请求执行

```text
entrypoints/openai
  -> v1/engine/llm_engine.py
  -> v1/engine/core.py
  -> v1/core/sched/scheduler.py
  -> v1/core/kv_cache_manager.py
  -> v1/worker/gpu_model_runner.py
```

先跟一次请求，不要先读所有模型实现和 kernel。

### TorchTitan 训练

```text
train.py / training_engine.py
  -> components/data
  -> distributed parallel dims
  -> model parallelize
  -> optimizer
  -> checkpointer
```

每读一层，都标记该模块在 step 的哪一段运行。

### Megatron 多维并行

```text
parallel_state.py
  -> tensor_parallel
  -> pipeline_parallel
  -> transformer/transformer_config.py
  -> distributed
```

先画 rank group，再读映射函数。

### NCCL

```text
public API
  -> enqueue
  -> graph/topology
  -> transport
  -> device code
```

底层会随硬件演进，应用开发首先理解 collective 语义和 topology 选择。

### Kubernetes GPU

```text
cmd/nvidia-device-plugin
  -> internal/plugin
  -> internal/resource manager
  -> kubelet device plugin API
```

将发现、注册、分配和调度四个阶段分开。

## 原创性与限制

本书结构、文字、示例、SVG 图和标准库模拟器均独立编写。官方仓库、文档和论文仅作为事实来源。没有复制外部博客结构或图表。

本书不构成具体硬件采购或容量承诺。公式给出量级下界，真实性能受模型、数据类型、kernel、GPU、互联、请求分布和软件版本影响。任何上线配置都应在目标环境压测。
