# 最少模型知识：token、tensor 与参数

AI Infra 不要求先会推导注意力公式，但必须能读懂数据形状。显存和通信量最终都来自“有多少个元素，每个元素几字节”。

{{diagram:tensor-shape|文字先变成 token ID，再变成带 batch、sequence 和 hidden 三个维度的 tensor。}}

## Token 不是字，也不是固定长度

Tokenizer 把文本切成词片段并映射为整数 ID。同一句中文在不同模型中可能产生不同 token 数。基础设施关心 token，因为：

- prompt token 数决定 prefill 工作量；
- 总上下文 token 数决定 KV cache；
- output token 数决定 decode 轮数；
- 计费、限流和吞吐常用 token 表示。

字符长度只能做粗略预估，真正入队前应以目标 tokenizer 计算。

## Tensor 是带形状的数字数组

常见形状记成：

```text
[B, S, H]
```

- `B`：batch 中有多少条序列；
- `S`：每条序列有多少 token；
- `H`：每个 token 的隐藏向量长度。

例如 `[8, 2048, 4096]` 的 FP16 tensor 包含 `8 × 2048 × 4096` 个元素，每个元素 2 bytes，约 128 MiB。还没算任何临时结果。

### 形状先决定元素数，精度再决定字节数

把 `[8, 2048, 4096]` 看成八份序列，每份有 2048 个位置，每个位置有 4096 个数。三个维度相乘得到 67,108,864 个元素，乘 FP16 的 2 bytes 得到 134,217,728 bytes，也就是 128 MiB。若只改为 FP32，元素不变，空间变成 256 MiB。

这是一份 tensor 的账，不是模型全部激活。每层还有其他中间结果，算子可能保留或重用内存；形状算例提供量级起点，不应把它直接乘层数当成准确峰值。

## 参数是模型长期保存的 tensor

“7B 模型”通常表示约 70 亿个参数。只看权重下界：

```text
权重字节 = 参数量 × 每参数字节
```

70 亿参数使用 FP16 或 BF16：

```text
7,000,000,000 × 2 bytes ≈ 13.04 GiB
```

这不等于一张 16 GiB 卡一定能运行，因为框架、KV cache、workspace 和临时 tensor 也要显存。

## 数据类型决定字节和数值范围

| 类型 | 常见字节 | 用途直觉 |
| --- | ---: | --- |
| FP32 | 4 | 精度高，训练部分状态常保留 |
| FP16 | 2 | 范围较窄，需要关注溢出 |
| BF16 | 2 | 指数范围接近 FP32，训练常见 |
| FP8 | 1 | 需硬件和缩放策略支持 |
| INT8 | 1 | 推理量化常见 |
| INT4 | 0.5 | 权重更小，但打包与 kernel 有要求 |

“每参数 0.5 byte”是逻辑下界。量化 scale、zero point、对齐和打包会增加元数据。

### 参数量与请求长度分别让哪部分变大

同一 7B 模型接收短句或长文，长期权重通常不变；变的是输入 tensor、计算量和历史 KV。换更大的模型会增加权重，而增加并发会增加同时存在的运行状态。于是“显存满了”要先判断到底改变了模型还是请求。

FP16 和 BF16 都占 2 bytes，却有不同数值范围与精度。字节数相同不表示训练稳定性相同；部署精度是一份数值与 kernel 合同，容量公式只解释其中的存储部分。

## 层、头和隐藏维度

对 KV cache 估算，三个结构参数很重要：

- 层数 `L`；
- KV head 数 `Hkv`；
- 每个 head 的维度 `Dhead`。

GQA 模型的 KV head 数可能小于 query head 数，因此不能总用 hidden size 直接代替。应读取模型 config。

## Batch 有两种含义

训练 batch 常指一次 optimizer step 处理的样本总数，还可能分成 micro-batch 和梯度累积。推理 batch 更动态，某一轮里活跃序列和处理 token 数都可变化。

所以“batch size 32”离开上下文没有意义。至少要说明：

- 是序列数还是 token 数；
- 是每卡还是全局；
- 是 prefill 还是 decode；
- 是否包含梯度累积。

## FLOP 与 byte 是两本账

模型执行既做计算，也搬数据。只统计 FLOP 会忽略显存和互联，只统计内存又会忽略 tensor core。后面用 Roofline 心智模型判断哪本账先成为上限。

### 在线 batch 不应被理解为整齐的矩形

八条请求可能已经分别生成 10、200 或 1000 个位置，引擎会用分页、打包和 metadata 表达变长状态。教学 `[B,S,H]` 帮助读形状，但真实引擎不一定为每条请求补齐相同最大 S。FLOP 统计问做了多少运算，byte 统计问搬了多少数据，两者必须分别估算。

## 一个练习

运行：

```bash
python3 examples/infra_lab.py memory --parameters 7 --weight-bits 16
```

再把 `--weight-bits` 改为 8。观察权重减少，但 KV cache 不变，因为它由层、KV head、head dim、活跃 token 和 KV 精度决定。
