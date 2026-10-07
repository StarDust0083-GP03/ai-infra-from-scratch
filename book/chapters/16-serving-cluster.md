# 在线服务：网关、队列、副本与扩缩容

把模型进程放进 Deployment 只是起点。在线推理要同时处理流量波动、长短请求、模型版本、冷启动和 GPU 成本。

{{diagram:serving-cluster|数据面处理请求，控制面维持副本、版本与容量。}}

## 数据面组件

### Gateway

负责认证、租户配额、输入限制、模型路由和协议。超长 prompt 应尽早拒绝，避免进入昂贵 GPU 队列后才失败。

### Replica

接收请求、tokenize、维护连接并和引擎通信。一个 replica 可能绑定一个 GPU worker group，不一定是一 Pod 一 GPU。

### GPU Worker Group

TP 或 PP 场景中，多进程共同服务一次请求。健康检查要关注整个 group，不能只看 API 进程端口存活。

### Queue

队列吸收短时突发，也制造等待。必须有长度、超时、优先级和拒绝策略。无限队列只会把过载伪装成高延迟。

## 路由的三个层次

1. 模型路由：请求需要哪个模型或 adapter；
2. 副本路由：哪个副本有容量、cache 或匹配硬件；
3. 引擎调度：本轮执行哪些序列和 token。

简单 round-robin 不知道各副本队列和请求长度。更智能路由可看正在运行 token、KV 压力或 prefix locality，但状态采集过慢也会误导。

### 两个副本排队条数相同，剩余工作也可能不同

副本 A 等五个短 prompt，副本 B 等五篇长文，request count 相同却不是同样工作量。再看正在 decode 的输出长度和 KV 压力，才能估计接入新请求的代价。缓存亲和可能省 prefill，但把全部同前缀请求送到一个副本又会制造热点。

路由需要同时考虑可用容量与局部复用。采集状态有延迟，多个路由器也可能同时选择“最空”副本，应测试突发，不只测试稳定平均流量。

## Autoscaling 看什么

CPU Web 服务常按 CPU utilization 扩容，GPU 推理更适合组合：

- waiting requests 或 queued tokens；
- TTFT 分位数；
- active sequences 与 KV utilization；
- GPU memory/compute 指标；
- 到达率和输出 token 速率；
- 冷启动时间与最小副本。

GPU 利用率低可能是请求少，也可能是 CPU tokenizer、网络或同步瓶颈。单指标扩缩容容易振荡。

## 冷启动决定提前量

新副本可能要下载几十到数百 GiB 权重、加载到 GPU、编译 kernel 和 warmup。若冷启动 8 分钟，等 SLO 已经崩了再扩容毫无帮助。

可采用：

- 节点本地模型 cache；
- 预热池或最小副本；
- 分阶段 readiness；
- 按流量周期预扩容；
- 限制同时冷启数量，保护存储；
- 小流量 canary 完成后再全量。

### 扩容来不及的时候，队列必须有上限

新副本预热需要数分钟，当前过载请求不会因创建 Pod 立即得到服务。网关应按时限拒绝或降级，不能无限排队直至用户都超时。扩容依据到达率、排队 token 和冷启动趋势提前触发，最小副本承担低流量响应。

同时启动太多副本可能压垮模型存储，把八分钟冷启动变得更长。预热缓存与限并发下载属于扩容链的一部分，不能只看 replicas 数增加了多少。

## KubeRay 与 Operator 模式

KubeRay 用 CRD 表达 RayCluster、RayJob 和 RayService，operator 持续调和期望状态。它适合需要 Ray 分布式运行时的训练、数据或服务任务，但不是所有 vLLM 部署都必须引入 Ray。

选 operator 的理由应是生命周期和拓扑管理，而不是“AI 项目都应该上 Ray”。单节点模型服务用普通 Deployment 可能更简单。

## 滚动升级的 drain

长生成请求不适合被立即杀掉。升级流程应：

1. 新副本加载和 warmup；
2. readiness 后接少量流量；
3. 旧副本停止接新请求；
4. 等活跃请求结束或达到 drain deadline；
5. 保存必要状态并退出；
6. 保留快速回滚能力。

需要明确客户端重试是否会重复计费或重复业务副作用。

## 容量规划的单位

用 token 而不是 request 作为主要工作量单位。100 个“你好”与 100 个 100K prompt 完全不同。至少按 prompt/output 长度分桶，分别测 TTFT、TPOT 和 tokens/s。

### 缩容为什么要先停止接新请求

若直接删除正在生成的副本，客户端会得到部分答案并可能重试。drain 先将它移出接入集合，等待活跃任务完成或达到 deadline，再释放 group。长请求仍需要明确最大等待和失败语义，不能让一条生成永久阻塞升级。

Worker group 多卡协作时，健康与 drain 应按整组判断。API 端口还活着不代表每个 rank 可计算，单个坏 rank 也可能拖住全部请求。

## 源码入口

- `vllm/entrypoints/openai/`
- `vllm/v1/engine/`
- `vllm/distributed/`
- `kuberay/ray-operator/`
- `kuberay/config/prometheus/`
