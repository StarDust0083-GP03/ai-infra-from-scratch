# Kubernetes 怎样看到 GPU

Kubernetes 默认认识 CPU、内存和普通设备，但不会自动发现 NVIDIA GPU。Device Plugin 在每个节点运行，向 kubelet 注册可用设备，并在 Pod 分配时返回设备、挂载和环境配置。

{{diagram:k8s-gpu|Device Plugin 把节点硬件转换成 Kubernetes extended resource。}}

## Extended Resource

Pod 常这样请求 GPU：

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

GPU 这类扩展资源是整数资源，通常写在 `limits`。不能像 CPU 一样请求 `0.25` 张物理 GPU。共享需要额外机制，例如 MIG、time-slicing 或 MPS，它们的隔离语义不同。

## Device Plugin 的职责

- 发现健康 GPU 或 MIG 设备；
- 向 kubelet 注册资源名与数量；
- 监控设备健康变化；
- Allocate 时返回设备节点、CDI、mount 或环境；
- 暴露配置的共享策略。

它不负责选择哪个节点。节点选择由 scheduler 根据资源和约束完成。

## Scheduler 知道多少

默认 scheduler 看到某节点有 8 个 `nvidia.com/gpu`，某 Pod 要 2 个。它不天然知道：

- 两卡是否有 NVLink；
- GPU 是哪个型号和显存；
- 当前模型是否已在本地 cache；
- 某卡上 KV cache 是否热；
- 这 8 卡是否要作为一个 gang 同时给同一作业。

型号可通过 node labels 和 affinity 表达，拓扑与 gang 常需要插件或专用 scheduler。

### 资源数字怎样一步步变成容器可访问的设备

插件发现设备并向 kubelet 报告，节点状态呈现扩展资源，scheduler 据此选择节点；到容器启动阶段，Allocate 返回访问设备需要的信息。节点选择与具体设备暴露是两段工作。Pod Pending 与容器里看不到 GPU，可能发生在不同环节。

默认资源计数只回答够不够张数，不回答这两张卡是否处于最佳互联域。型号标签、亲和与拓扑机制补这些条件，模型所需 KV 容量和热缓存则还在引擎层。

## MIG、Time-slicing 与 MPS

### MIG

把支持的 GPU 硬件切成隔离实例，拥有相对明确的计算和显存份额。适合稳定小负载，但 profile 固定，重配置有运维成本。

### Time-slicing

多个容器轮流使用同一 GPU，提高低利用任务的共享率，但通常不提供显存隔离保证。所有参与者的显存总需求仍受物理卡限制。

### MPS

允许多个 CUDA 进程更细粒度共享 GPU 执行资源，能改善并发，但隔离、兼容和故障域需要评估。

不要把三者统称“虚拟 GPU”。先写出隔离、性能和故障需求。

## DaemonSet 与节点准备

Device Plugin 通常以 DaemonSet 运行在 GPU 节点。完整节点还需要驱动、container runtime 配置、监控 exporter 和标签发现。GPU Operator 可以自动化部分生命周期，但自动化不会消除版本兼容矩阵。

应固定并验证：

- driver 与 kernel；
- CUDA runtime 与容器镜像；
- Device Plugin 配置；
- MIG 模式；
- container toolkit；
- NCCL 和网络插件。

### 共享份额不应被当成显存承诺

time-slicing 可以让更多进程轮流使用设备，但它们的显存需求仍叠加在物理卡上。两个各需要 20 GiB 的任务不能因配置了两个共享槽，就自动在 24 GiB 卡上共存。调度数字与物理隔离语义必须分别理解。

MIG 给出硬件分区，profile 限定容量与计算；MPS 改善进程并发，却有自身兼容与故障边界。选择先看稳定容量、隔离和运行模型需求，再看可声明多少逻辑资源。

## 一个 Pod 能用多卡，不等于多节点

单 Pod 请求 8 GPU 通常使用同一节点内设备。多节点训练通常是多个 Pod，每个 Pod 若干 GPU，再通过 rendezvous 组成 world。它需要 gang scheduling、稳定网络和 rank 配置。

## 排障顺序

1. `nvidia-smi` 在节点是否正常；
2. Device Plugin Pod 是否健康；
3. Node allocatable 是否出现 GPU 资源；
4. Pod request/limit 和 selector 是否正确；
5. scheduler event 为什么 Pending；
6. 容器内设备与 driver library 是否可见；
7. 应用是否选择正确 local rank。

把“Pod Pending”和“容器内 CUDA 错误”分开，它们属于调度与运行两个阶段。

### 用故障所在层选择检查命令

主机看不到设备先查硬件与驱动；主机正常但容器看不到，查 runtime 和设备分配；节点没呈现资源，查 plugin 注册和健康；Pod 有卡而模型挂起，再查 rank、通信和软件。不要从所有症状一律重启模型开始。

多节点作业还需 rendezvous 和 group 配置，每个 Pod 得到本地 GPU 后才能共同组成 world。分配成功不是训练已就绪，健康检查应覆盖这个协作层。

## 源码入口

- `k8s-device-plugin/cmd/nvidia-device-plugin/`
- `k8s-device-plugin/internal/plugin/`
- `k8s-device-plugin/internal/rm/`
- `k8s-device-plugin/internal/mig/`
- Kubernetes Schedule GPUs 文档
