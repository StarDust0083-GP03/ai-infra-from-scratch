# 模型加载、精度与量化

档案问答的进程已经启动，却还不能接待读者。模型文件必须被识别、读取、转换并放到正确设备，执行路径还要完成预热。服务发布需要测量这一整段准备时间，不能只测容器启动。

## 冷启动发生了什么

配置首先决定模型结构和加载方式，随后读取权重分片，建立参数映射，将内容送入设备，并准备缓存与工作区。某些运行方式还会编译 kernel、捕获图或执行预热。不同阶段可能重叠，也可能产生暂时同时存在的副本。

把存储来源写入启动日志。远端对象、本地 SSD 和操作系统页缓存的表现不同；第二次启动较快可能只是缓存命中。扩容设计应包含真正冷启动，而非只复用一台已热的节点。

## 权重格式

加载器需要知道每个 tensor 属于哪个参数，哪些权重共享，以及当前 rank 应拿到哪个切片。可分片和可映射的格式有利于控制读取量，但格式支持并不保证框架采用最省内存的路径。

模型仓库中的自定义代码还构成执行边界。进入生产前固定版本，核查需要运行的代码及文件来源。权重下载成功不能替代供应链检查。

## 量化到底减少什么

以 30 亿参数计算，16 位内容约 5.59 GiB，8 位约 2.79 GiB，4 位约 1.40 GiB。这些只是理想权重内容，实际还需 scale、打包信息和未量化层。

若原工作受权重搬运限制，减少读取字节可能加快生成；若省下的空间用作 KV，也可能增加可服务的并发。两种收益要分别验证，不能从文件缩小直接推出速度按比例提高。

### 权重压缩以后，剩下的空间去哪里

假设从 16 位切到 8 位，理论节省约 2.79 GiB。可以将一部分留作工作峰值余量，另一部分扩大缓存池，但 KV 精度若不变，每个历史位置仍需原来的字节。

加载过程中还可能先建立高精度副本再转换。因此磁盘文件尺寸、稳定驻留尺寸和转换峰值应单列测量。若只看量化文件大小，就可能在首次启动时遇到意外 OOM。

<figure class="diagram" tabindex="0" data-review-figure="infra-quantization">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 488" role="img" aria-labelledby="infra-quantization-title infra-quantization-desc" style="display:block;width:100%;min-width:620px;height:auto">
<title id="infra-quantization-title">30 亿参数：位宽减半，理想权重内容减半</title>
<desc id="infra-quantization-desc">30亿参数的16位、8位、4位理想权重内容分别约5.59、2.79、1.40 GiB；未计算额外状态，不能推断实际速度。</desc>
<rect width="960" height="488" fill="var(--paper,#faf8f1)"/>
<g font-family="'IBM Plex Sans','Noto Sans CJK SC',system-ui,sans-serif"><text x="40" y="48" font-size="28" fill="var(--ink,#243b48)" text-anchor="start">30 亿参数：位宽减半，理想权重内容减半</text><text x="40" y="96" font-size="18" fill="var(--muted,#536772)" text-anchor="start">理想权重内容 / GiB</text><path d="M240 120V372" stroke="var(--line,var(--rule,#d9ded8))"/><text x="240" y="404" font-size="18" fill="var(--muted,#536772)" text-anchor="middle">0</text><path d="M336 120V372" stroke="var(--line,var(--rule,#d9ded8))"/><text x="336" y="404" font-size="18" fill="var(--muted,#536772)" text-anchor="middle">1</text><path d="M432 120V372" stroke="var(--line,var(--rule,#d9ded8))"/><text x="432" y="404" font-size="18" fill="var(--muted,#536772)" text-anchor="middle">2</text><path d="M528 120V372" stroke="var(--line,var(--rule,#d9ded8))"/><text x="528" y="404" font-size="18" fill="var(--muted,#536772)" text-anchor="middle">3</text><path d="M624 120V372" stroke="var(--line,var(--rule,#d9ded8))"/><text x="624" y="404" font-size="18" fill="var(--muted,#536772)" text-anchor="middle">4</text><path d="M720 120V372" stroke="var(--line,var(--rule,#d9ded8))"/><text x="720" y="404" font-size="18" fill="var(--muted,#536772)" text-anchor="middle">5</text><path d="M816 120V372" stroke="var(--line,var(--rule,#d9ded8))"/><text x="816" y="404" font-size="18" fill="var(--muted,#536772)" text-anchor="middle">6</text><text x="40" y="176" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">16 位</text><rect x="240" y="144" width="536.4418029785156" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#e7edf2))" stroke="var(--muted,#536772)"/><text x="792.4418029785156" y="175" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">5.59 GiB</text><text x="40" y="256" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">8 位</text><rect x="240" y="224" width="268.2209014892578" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#e7edf2))" stroke="var(--muted,#536772)"/><text x="524.2209014892578" y="255" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">2.79 GiB</text><text x="40" y="336" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">4 位</text><rect x="240" y="304" width="134.1104507446289" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#e5ede9))" stroke="var(--muted,#536772)"/><text x="390.1104507446289" y="335" font-size="20" fill="var(--ink,#243b48)" text-anchor="start">1.40 GiB</text><text x="40" y="456" font-size="18" fill="var(--muted,#536772)" text-anchor="start">不含 scale、未量化层、KV、工作区和转换峰值；不表示速度比例。</text></g>
</svg>
<figcaption>图：同一零起点和 GiB 刻度；条长按 parameters × bits / 8 换算。</figcaption>
</figure>

## 为什么更小不一定更快

低比特内容需要匹配的打包布局与高效 kernel，某些路径还会做反量化。若目标设备不支持高效实现，或算子回退、频繁转换，节省的读取可能被额外工作抵消。

还要先确认瓶颈位置。排队或 CPU 分词主导的短请求，不会因权重读取改善而同比加速；输入阶段与生成阶段也可能对同一种量化有不同收益。

## 精度是系统合同

一份可复现配置应说明权重表示、量化方法与分组方式、激活和 KV 精度、累加精度，以及目标 kernel 和设备支持。只写“低比特模型”无法判断它减少哪类占用。

质量检查与速度检查都需基线。档案中的日期、数字、少见地名和引用可能对精度变化敏感，不能只用几个日常问候验证可用性。

### 精度合同要覆盖输入到 kernel 的整条路

例如权重按组保存 scale，加载器必须以相同分组解释内容，kernel 又需对应布局。错配可能直接报错，也可能悄悄走不同执行路径。确认配置被接受后，还要检查实际选择的实现。

对代表性任务比较输出错误与异常数值，同时用相同长度和到达过程比较延迟。一个速度改善结论不能顺带证明任务质量未变。

## 模型加载的分布式问题

各 rank 独立读取分片会把压力放到存储，集中读取再分发则把压力转到网络和分发者。是否值得预先切片，还取决于权重布局是否与实际 TP、PP 配置匹配。

同时启动很多工作组时，本地每组的加载很快也可能形成远端读取风暴。应限制准备并发、观察存储吞吐，并把失败重试的放大量计入容量。

## 热更新与滚动发布

新版本必须完成加载、执行检查和必要预热后才进入就绪集合。旧版本停止接新请求，再为仍在生成的请求留出排空窗口。模型、tokenizer、聊天模板和 adapter 应作为一致版本组合交付。

更新计划也应保留旧镜像、权重与配置。仅修改服务标签而旧文件已经删除，并不具备真正可执行的回滚路径。

### 滚动更新为什么需要额外容量

两个旧副本各自占卡，新副本预热时还需要自己的设备。如果没有额外容量，就必须接受分批减少在线能力或预先调整发布方案。`maxSurge` 之类参数不会凭空生成 GPU。

多 rank 副本要整组准备和切换。不能把一组中的部分 rank 升级后，仍让它们共同处理请求；版本一致性必须覆盖组内所有参与者。

## 源码入口

从 `vllm/model_executor/model_loader/` 检查配置怎样选择读取与映射路径，再到 `vllm/model_executor/layers/quantization/` 核对量化表示与执行条件。训练相关可查 `torchtitan/quantization/` 及 `torchtitan/models/`。先找实际被选中的实现，再阅读底层细节，避免分析一条根本没启用的优化路径。
