# 附录 B：源码地图、来源与版本说明

## 机制、算例与实测分别说明什么

阅读代码可以核对职责与可达路径，论文可解释设计与复杂度，手算可发现数量和单位错误，离线程序可检验它明确实现的规则。它们不能替代目标 GPU、互联和线上流量的实测。

新版正文采用档案馆问答与校对训练作为虚构背景。模型尺寸、时间线和硬件上限均为教学假设；未声称这些配置在真实平台达到相应服务目标。迁移时应重新验证精度、执行实现、负载和恢复条件。

## 本地源码快照

本书沿用已归档的 2026-09-22 快照作为事实依据，重写日期不意味着第三方源码已更新。

| 项目与短提交 | 用它核对的对象 |
| --- | --- |
| vLLM `ca831d1c5571` | 引擎循环、调度输出、缓存块生命周期 |
| TorchTitan `7349a2282d9e` | 训练步骤、并行组和保存状态 |
| Megatron-LM `c343bb6d337e` | 层内与层间切分、全局状态布局 |
| NCCL `12df1a11afad` | 通信入队、拓扑与传输实现 |
| NVIDIA Device Plugin `3dd82d32e62c` | 设备发现、健康与容器分配 |
| Volcano `d1fe35ed58fc` | 作业准入、队列与插件策略 |
| KubeRay `e76908b64fc3` | 分布式资源生命周期和调和 |

完整定位信息保存在 `sources/inventory.json`。本地副本用于溯源，第三方许可证及版权仍归各项目；正文重写不改变这些事实材料。

## 官方材料

` sources/web/sources.tsv ` 记录归档 URL，`sources/web/` 中的 Markdown 保存当时材料。核对在线文档时注意它可能已经超出本书版本。

推理部分主要借助 vLLM 的架构、分页、调优及分布式服务说明；训练与设备行为结合 PyTorch 的分布式、CUDA、FSDP2 和检查点文档，以及 TorchTitan 官方资料。硬件与通信参考 NVIDIA 的性能、CUDA 最佳实践和 NCCL 文档。

集群部分使用 Kubernetes GPU 调度、NVIDIA 插件、Volcano 和 KubeRay 官方说明。Hugging Face 的内存与训练性能资料作为补充解释，具体实现仍回到目标框架核对。

## 论文

下列文献标识保留为可核对的来源，正文图解全部重新设计，不复刻其原始图表：

| 文献标识 | 阅读目的 |
| --- | --- |
| Kwon et al., arXiv:2309.06180 | PagedAttention 的分配与共享动机 |
| Shoeybi et al., arXiv:1909.08053 | Megatron-LM 的模型切分组织 |
| Rajbhandari et al., arXiv:1910.02054 | ZeRO 对训练状态的分片递进 |
| Dao et al., arXiv:2205.14135 | FlashAttention 对显存 IO 的组织 |
| Williams, Waterman, Patterson, DOI:10.2172/1407078 | Roofline 的计算与带宽上界 |

实验图中的设备、模型和测量环境属于对应论文，不应移作本书虚构配置的性能证据。

## 建议的源码阅读顺序

### vLLM 请求执行

从 `entrypoints/openai` 找请求如何成为引擎输入，沿 `v1/engine/llm_engine.py`、`v1/engine/core.py` 到调度器。随后检查 `v1/core/kv_cache_manager.py` 的资源行为，以及 `v1/worker/gpu_model_runner.py` 怎样消费调度结果。

带一条会等待、推进并最终取消的请求，记录它跨边界时哪些字段发生变化，再深入模型实现。

### TorchTitan 训练

以 `train.py` 或对应训练引擎定位更新边界，接着查数据组件、并行维度、模型 parallelize、优化器和 checkpointer。每个模块都标注在当前步骤的什么时候运行，哪些状态会跨步延续。

### Megatron 多维并行

先画 `parallel_state.py` 形成的组，再读 `tensor_parallel` 和 `pipeline_parallel` 的数据映射。模型配置可在 `transformer/transformer_config.py` 核对，分布式状态相关实现再进入 `distributed`。

### NCCL（集合通信库）

先理解公共操作的输入输出合同，再跟随 enqueue、拓扑规划和 transport。只有需要分析具体设备执行时才深入 device 代码，否则容易丢掉“谁需要从谁得到什么”的原始问题。

### Kubernetes 的 GPU 接入

沿 `cmd/nvidia-device-plugin` 到 `internal/plugin` 与资源发现模块，区分发现、注册和 Allocate。另用 kubelet 与调度器职责补全节点选择过程，避免把插件误读为集群调度器。

## 原创性与限制

本次保留章与节的结构，重新撰写说明、手算、教学代码和图形表达。真实 API、路径、论文标识和提交值作为事实引用保留，未修改归档第三方源码。

容量公式刻画明确假设下的下界或量级；离线模拟没有真实 kernel、采样质量或网络时间。上线和采购都需要目标环境的正确性、峰值、性能与故障恢复证据，不能将这份教材当作配置保证书。
