# 《AI Infra from Scratch：从一张 GPU 到生产集群》

## 第一部分：先看全景

1. [读前说明：不懂 CUDA 也能开始](chapters/00-preface.md)  
   来源：研究范围、源码快照、术语依赖
2. [一条请求穿过哪些系统](chapters/01-request-journey.md)  
   来源：vLLM 架构、Kubernetes、KubeRay、NVIDIA Device Plugin
3. [最少模型知识：token、tensor 与参数](chapters/02-model-basics.md)  
   来源：Hugging Face memory anatomy、Transformer 执行路径

## 第二部分：单卡与显存

4. [GPU 不是更快的 CPU](chapters/03-gpu-basics.md)  
   来源：NVIDIA GPU Background、CUDA Best Practices、Roofline
5. [显存账本：模型到底占多少](chapters/04-memory-accounting.md)  
   来源：PyTorch CUDA semantics、HF memory anatomy、ZeRO
6. [推理的两幕：Prefill 与 Decode](chapters/05-prefill-decode.md)  
   来源：vLLM 文档、PagedAttention、FlashAttention
7. [KV Cache：上下文为什么越来越贵](chapters/06-kv-cache.md)  
   来源：PagedAttention 论文、vLLM KV cache manager
8. [连续批处理：GPU 如何同时服务很多人](chapters/07-continuous-batching.md)  
   来源：vLLM scheduler、EngineCore、optimization 文档
9. [模型加载、精度与量化](chapters/08-loading-quantization.md)  
   来源：vLLM model loader、TorchTitan quantization、CUDA 精度语义

## 第三部分：多卡训练与推理

10. [多卡不是一个开关](chapters/09-parallelism.md)  
    来源：Megatron-LM、TorchTitan、vLLM parallelism
11. [Collective：GPU 之间怎样交换数据](chapters/10-collectives.md)  
    来源：NCCL overview 与源码、Megatron parallel state
12. [训练循环与训练显存](chapters/11-training-loop.md)  
    来源：TorchTitan training engine、HF performance、ZeRO
13. [分片、重计算与并行组合](chapters/12-distributed-training.md)  
    来源：FSDP2、TorchTitan、Megatron-LM、ZeRO
14. [数据管道与 Checkpoint](chapters/13-data-checkpoint.md)  
    来源：TorchTitan data/checkpointer、PyTorch distributed checkpoint、Megatron dist checkpoint

## 第四部分：集群与生产

15. [Kubernetes 怎样看到 GPU](chapters/14-kubernetes-gpu.md)  
    来源：Kubernetes GPU scheduling、NVIDIA Device Plugin
16. [批作业调度：为什么要一起开跑](chapters/15-batch-scheduling.md)  
    来源：Volcano 架构、PodGroup、gang scheduling
17. [在线服务：网关、队列、副本与扩缩容](chapters/16-serving-cluster.md)  
    来源：vLLM distributed serving、KubeRay、Kubernetes
18. [可观测性、SLO 与成本](chapters/17-observability.md)  
    来源：vLLM metrics、TorchTitan observability、CUDA/NCCL 诊断
19. [故障恢复：把失败当作正常路径](chapters/18-failure-recovery.md)  
    来源：checkpoint、NCCL RAS、operator reconciliation、源码测试
20. [端到端：设计一个小型 AI 平台](chapters/19-platform-design.md)  
    来源：全书模型、本书 `examples/infra_lab.py`

## 附录

- [术语、公式与命令速查](chapters/appendix-glossary.md)
- [源码地图、来源与版本说明](chapters/appendix-sources.md)
