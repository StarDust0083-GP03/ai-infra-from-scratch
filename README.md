# AI Infra from Scratch

面向初学者的中文教材，以档案馆白天问答、夜间校对训练为虚构背景，解释容量、执行、通信、调度和恢复。本次保留章节结构，重新编写全部正文、图解、手算与配套程序。

## 在线阅读与部署

- 页面：<https://StarDust0083-GP03.github.io/ai-infra-from-scratch/>
- 代码：<https://github.com/StarDust0083-GP03/ai-infra-from-scratch>

现有 Actions 配置负责在推送至 `main` 后构建、验证和发布 `wiki/`。本次没有执行 Git 提交或远端发布。首次启用 Pages 时，发布来源需选择 GitHub Actions。

构建使用 Node.js 22、Python 3 与锁定的 npm 依赖，不要求 GPU 或本地第三方源码。研究克隆、下载材料和缓存不属于发布产物。

## 本地阅读

书架入口为 <http://localhost:7999/>，本书入口为 <http://localhost:8004/wiki/>。统一管理脚本可在需要时启动本地服务器：

```bash
~/Work/ebooks-serve.sh start
```

`wiki/index.html` 提供目录，`wiki/book.html` 汇集正文，`wiki/search.html` 用于检索。前两个端口仅在对应服务已经启动时可用。

## 内容

全书含 20 章与 2 个附录，19 幅 SVG 图解（15 份生成图与 4 幅正文内嵌示例图），另有显存计算器和按轮调度实验。图解使用位置格、输入输出关系、阶段时间和故障分类等不同表达，避免把所有机制都画成相同流程。

源稿在 `book/chapters/`，顺序见 `book/SUMMARY.md`。`RESEARCH_NOTES.md` 保留原资料研究背景，来源快照未因这次重写自动更新。

阅读器继续提供字号、主题、搜索、阅读进度、章内导航和代码复制。教学数字用于明确条件下的复算，不代表档案馆真实部署或目标 GPU 性能。

## 本地源码

事实核对使用 vLLM、TorchTitan、Megatron-LM、NCCL、NVIDIA Device Plugin、Volcano 与 KubeRay 七个官方仓库。完整地址和提交在 `sources/inventory.json`，文档与论文归档在 `sources/web/`。

## 离线实验

```bash
python3 examples/infra_lab.py memory
python3 examples/infra_lab.py simulate
python3 examples/infra_lab.py check
```

`memory` 分列权重、逻辑 KV 与训练状态假设；`simulate` 打印新档案请求的逐轮工作和块占用；`check` 验证公式、分页、释放、未来到达和无进展条件。轮次没有真实时间含义，程序不调用设备或外部服务。

## 构建与校验

```bash
npm ci --prefix wiki
node wiki/build.mjs
python3 wiki/verify.py
python3 examples/infra_lab.py check
```

构建会先运行 `wiki/render-diagrams.py`，再生成章节、合订本和搜索索引。图生成器只用标准库，并检查 15 份 SVG 都能被 XML 解析。`wiki/verify.py` 另行检查 4 幅正文内嵌示例图、无障碍标签和合订本唯一锚点。

## 边界

容量核算不包含全部运行时和执行峰值，模拟器不实现真实 kernel、采样、通信或抢占。采购和上线前应使用目标模型、精度、长度分布与拓扑验证，并演练失败恢复。来源材料提供事实依据，不能替代这些运行证据。
