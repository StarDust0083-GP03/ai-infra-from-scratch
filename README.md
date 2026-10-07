# AI Infra from Scratch

一本面向基础薄弱读者的 AI 基础设施中文电子书。从一张 GPU 和一条推理请求开始，逐步进入显存、KV Cache、连续批处理、多卡通信、分布式训练、Kubernetes GPU 调度、SLO 与故障恢复。

## 在线阅读与部署

- 阅读：<https://StarDust0083-GP03.github.io/ai-infra-from-scratch/>
- 仓库：<https://github.com/StarDust0083-GP03/ai-infra-from-scratch>

推送到 `main` 后，GitHub Actions 安装锁定依赖、构建网页、运行校验和离线实验，再将 `wiki/` 部署到 GitHub Pages。首次部署需在仓库 Pages 设置中选择 GitHub Actions。

公开仓库保留书稿、网页、示例和来源版本记录，不包含第三方源码克隆、下载的全文资料与缓存。网页构建需要 Node.js 22 和 Python 3，不需要 GPU 或这些本地源码。

## 本地阅读

统一书架：<http://localhost:7999/>

本书：<http://localhost:8004/wiki/>

- `wiki/index.html`：分章目录
- `wiki/book.html`：离线合订本
- `wiki/search.html`：全文搜索

所有本地电子书统一启动：

```bash
~/Work/ebooks-serve.sh start
```

## 内容

- 20 章正文与 2 个附录
- 连贯讲解请求路径、字节账本与等待关系，补充形状手算、调度推演和故障反例
- 15 张原创 SVG 图，支持深浅色和移动端
- 显存计算器与连续批处理玩具模拟器
- 全文搜索、字号调整、阅读进度、代码复制和章内目录

书稿源文件在 `book/chapters/`，研究结论在 `RESEARCH_NOTES.md`，章节材料映射在 `book/SUMMARY.md`。

正文沿一条请求与一次训练 step 展开，解释容量、计算、通信与调度怎样共同影响结果。公式和标准库模拟用于建立数量与调度直觉，不是目标 GPU、多节点集群或 Kubernetes 服务的实测性能。

## 本地源码

浅克隆了七个官方仓库：

- vLLM
- TorchTitan
- Megatron-LM
- NCCL
- NVIDIA Kubernetes Device Plugin
- Volcano
- KubeRay

具体 commit、URL 与代码统计见 `sources/inventory.json`。官方文档和论文归档于 `sources/web/`。

## 离线实验

```bash
python3 examples/infra_lab.py memory
python3 examples/infra_lab.py simulate
```

`memory` 估算权重、KV Cache 和训练状态的理论下界；`simulate` 展示 token budget、分页 block 和连续批处理的关系。两者不需要 GPU 或第三方依赖。

## 构建与校验

```bash
cd wiki
npm ci
npm run build
npm run verify

cd ..
python3 examples/infra_lab.py memory
python3 examples/infra_lab.py simulate
```

## 边界

- 公式用于建立量级感，不替代目标硬件压测。
- 示例不模拟真实 CUDA kernel、NVLink 或模型质量。
- 聚焦通用机制，不展开云厂商产品菜单。
- 外部源码、文档和论文用于核对事实；文字、结构、示例和图均独立创作。
