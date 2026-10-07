# 读前说明：不懂 CUDA 也能开始

AI Infra 看起来像一堵缩写墙：GPU、HBM、CUDA、NCCL、TP、FSDP、KV Cache、MIG、RDMA、SLO。它们并不是二十个互不相干的知识点，而是同一条链上不同位置的问题。

这本书从两个普通问题开始：

1. 一个用户发出提示词后，数据经过哪些系统才变成下一个 token？
2. 一次训练 step 中，哪些字节留在显存，哪些字节在 GPU 之间移动？

能回答这两个问题，就已经有了 AI Infra 的骨架。

## 你不需要先会什么

不要求会写 CUDA kernel，不要求有多卡机器，也不要求先学完整 Kubernetes。书中只在真正需要时引入概念：

- 解释显存时，再讲 tensor 形状和数据类型；
- 解释推理吞吐时，再讲 prefill、decode 与 KV cache；
- 解释多卡时，再讲 collective 和网络拓扑；
- 解释集群时，再讲 Device Plugin、scheduler 和 operator。

每章都先回答“它解决什么问题”，再看公式和源码。

## 沿字节和等待连续读下去

正文反复回到一件事：一个请求当前走到哪一步，为它保存了哪些 tensor，下一步在等谁。显存公式先告诉你装不装得下，Prefill 与 Decode 告诉你计算怎样发生，调度再解释许多请求如何分享有限容量。多卡把等待扩展到 rank，集群把它扩展到作业与副本。

手算例子只使用明确的形状、精度和假设条件。看到数字时，把输入条件一起带走，不把另一个模型的 KV 大小或另一张卡的峰值当作自己的部署结论。失败情景则用于区分症状与原因：同样是慢、OOM 或超时，发生阶段不同，应该测的对象也不同。

## 本书怎么验证

项目下载了七个官方仓库的浅克隆：

| 仓库 | 本书用来理解什么 |
| --- | --- |
| vLLM | 在线推理、调度、KV cache、GPU worker |
| TorchTitan | 现代 PyTorch 大模型训练栈 |
| Megatron-LM | 多维并行与高性能训练 |
| NCCL | GPU collective 与通信拓扑 |
| NVIDIA Device Plugin | Kubernetes 如何发现和分配 GPU |
| Volcano | 队列、PodGroup 与 gang scheduling |
| KubeRay | 分布式作业和服务的 operator 模式 |

同时归档官方文档与 PagedAttention、Megatron-LM、ZeRO、FlashAttention、Roofline 等论文。来源不是为了堆链接，而是用来核对机制和边界。

## 三条阅读路线

### 第一次接触 AI Infra

按顺序读。第 1 至 8 章建立单卡推理直觉，第 9 至 13 章进入多卡训练，第 14 章之后再看集群。

### 只想部署推理服务

读第 1、3 至 10、14、16 至 19 章。训练章节仍建议看第 10 章 collective，因为张量并行也依赖通信。

### 正在做训练平台

读第 2 至 4、9 至 15、17 至 19 章。重点关注训练状态、拓扑、checkpoint 和 gang scheduling。

## 图怎么看

书中图都是概念图，不按真实物理尺寸绘制。颜色表示职责或数据类型，不表示某个产品。看到箭头时先问：

- 箭头上传的是 token、tensor、控制命令还是持久化数据？
- 这一步是否同步等待？
- 数据量随参数、batch、序列长度还是并发增长？

这三个问题比记住组件名称更有用。

## 示例的边界

`examples/infra_lab.py` 只用 Python 标准库，提供显存计算和连续批处理玩具模拟。它能验证公式和调度直觉，不能模拟真实 kernel、PCIe、NVLink 或模型质量。

```bash
python3 examples/infra_lab.py memory
python3 examples/infra_lab.py simulate
```

书中数字采用二进制 GiB，`1 GiB = 1024³ bytes`。硬件厂商标称容量有时使用十进制 GB，比较时要先统一单位。

> 目标不是让你背下整个栈，而是看到指标变化时知道数据在哪里、谁在等待、下一步该测什么。
