#!/usr/bin/env python3
"""Archive workload arithmetic and round-based scheduling, without GPU timing."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import math

GIB = 2**30


def positive(value: int | float, label: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be positive and finite")


def weight_bytes(parameters: int, bits_per_weight: int) -> int:
    positive(parameters, "parameter count")
    positive(bits_per_weight, "weight precision")
    return math.ceil(parameters * bits_per_weight / 8)


def kv_cache_bytes(*, layers: int, kv_heads: int, head_dim: int,
                   tokens: int, bytes_per_element: int) -> int:
    for name, number in locals().copy().items():
        positive(number, name)
    return 2 * layers * kv_heads * head_dim * tokens * bytes_per_element


def training_state_bytes(parameters: int, *, weight_bytes_per_param: int = 2,
                         gradient_bytes_per_param: int = 2,
                         optimizer_bytes_per_param: int = 12) -> int:
    for name, number in locals().copy().items():
        positive(number, name)
    return parameters * (weight_bytes_per_param + gradient_bytes_per_param
                         + optimizer_bytes_per_param)


def gib(value: int) -> float:
    return value / GIB


@dataclass
class Request:
    name: str
    arrival: int
    prompt: int
    output: int
    prefilled: int = 0
    generated: int = 0
    first_token_at: int | None = None
    finished_at: int | None = None

    @property
    def ready_to_decode(self) -> bool:
        return self.prefilled == self.prompt

    @property
    def done(self) -> bool:
        return self.generated == self.output


@dataclass
class BlockPool:
    blocks: int
    block_size: int
    used: dict[str, int]

    @classmethod
    def create(cls, blocks: int, block_size: int) -> BlockPool:
        positive(blocks, "block count")
        positive(block_size, "block size")
        return cls(blocks, block_size, {})

    @property
    def free(self) -> int:
        return self.blocks - sum(self.used.values())

    def ensure_tokens(self, request: str, tokens: int) -> bool:
        if tokens < 0:
            raise ValueError("token count cannot be negative")
        needed = (tokens + self.block_size - 1) // self.block_size
        held = self.used.get(request, 0)
        if needed - held > self.free:
            return False
        self.used[request] = max(held, needed)
        return True

    def release(self, request: str) -> None:
        self.used.pop(request, None)


def simulate(requests: list[Request], *, token_budget: int = 24,
             blocks: int = 32, block_size: int = 8,
             trace: list[dict] | None = None) -> list[Request]:
    """One decode position per ready request; prefill uses the remaining budget.

    No preemption, prefix sharing, or time model. Fragmented partial requests
    may stall: report that policy limit rather than inventing GPU performance.
    """
    positive(token_budget, "round budget")
    if len({r.name for r in requests}) != len(requests):
        raise ValueError("request names must be unique")
    for r in requests:
        if r.arrival < 0 or r.prompt <= 0 or r.output <= 0:
            raise ValueError("arrival >= 0 and positive input/output are required")
        if r.prefilled or r.generated or r.first_token_at or r.finished_at:
            raise ValueError("provide fresh requests for each run")
    pool = BlockPool.create(blocks, block_size)
    clock = 0
    while any(not r.done for r in requests):
        live = [r for r in requests if r.arrival <= clock and not r.done]
        if not live:
            clock = min(r.arrival for r in requests if not r.done)
            continue
        remaining = token_budget
        work = []
        for r in live:
            if not remaining or not r.ready_to_decode:
                continue
            if not pool.ensure_tokens(r.name, r.prompt + r.generated + 1):
                continue
            r.generated += 1
            remaining -= 1
            work.append(f"{r.name}:decode=1")
            if r.first_token_at is None:
                r.first_token_at = clock + 1
            if r.done:
                r.finished_at = clock + 1
                pool.release(r.name)
        for r in live:
            if not remaining or r.done or r.ready_to_decode:
                continue
            capacity = (pool.used.get(r.name, 0) + pool.free) * block_size
            chunk = min(remaining, r.prompt - r.prefilled, capacity - r.prefilled)
            if chunk > 0 and pool.ensure_tokens(r.name, r.prefilled + chunk):
                r.prefilled += chunk
                remaining -= chunk
                work.append(f"{r.name}:prefill={chunk}")
        if not work:
            raise RuntimeError("No progress: KV pool cannot advance the admitted set; "
                               "this toy policy has no preemption")
        assert 0 <= pool.free <= pool.blocks
        if trace is not None:
            trace.append({"round": clock + 1, "work": work,
                          "used_blocks": pool.blocks - pool.free,
                          "tokens": token_budget - remaining})
        clock += 1
    assert pool.free == pool.blocks
    return requests


def memory_report(args: argparse.Namespace) -> None:
    positive(args.parameters, "billions of parameters")
    for name in ("context", "concurrent_requests"):
        positive(getattr(args, name), name)
    count = int(args.parameters * 10**9)
    weights = weight_bytes(count, args.weight_bits)
    tokens = args.context * args.concurrent_requests
    kv = kv_cache_bytes(layers=args.layers, kv_heads=args.kv_heads,
                        head_dim=args.head_dim, tokens=tokens,
                        bytes_per_element=args.kv_bytes)
    print(f"权重内容下界：{gib(weights):.6f} GiB")
    print(f"逻辑 KV 下界：{gib(kv):.6f} GiB，保留 {tokens:,} 个位置")
    print(f"推理两项小计：{gib(weights + kv):.6f} GiB，未计块浪费与执行峰值")
    print(f"16 bytes/参数训练状态假设：{gib(training_state_bytes(count)):.6f} GiB")


def simulation_report(_: argparse.Namespace) -> None:
    requests = [Request("目录快问", 0, 11, 3), Request("日志摘录", 0, 39, 7),
                Request("长卷校对", 2, 67, 4), Request("地名核对", 4, 7, 2)]
    events: list[dict] = []
    simulate(requests, trace=events)
    for e in events:
        print(f"轮 {e['round']:2} | 位置 {e['tokens']:2} | 块 {e['used_blocks']:2} | "
              + ", ".join(e["work"]))
    print("\n请求       首字等待(轮)   完成轮")
    for r in requests:
        assert r.first_token_at is not None and r.finished_at is not None
        print(f"{r.name}       {r.first_token_at-r.arrival:3}        {r.finished_at:3}")
    print("轮次不含 GPU、网络或采样耗时，不能换算真实延迟。")


def self_test() -> None:
    assert weight_bytes(3_000_000_000, 8) == 3_000_000_000
    assert kv_cache_bytes(layers=24, kv_heads=4, head_dim=96,
                          tokens=6144 * 6, bytes_per_element=2) == 1_358_954_496
    assert training_state_bytes(3_000_000_000) == 48_000_000_000
    pool = BlockPool.create(7, 8)
    assert all(pool.ensure_tokens(n, t) for n, t in zip("xyz", [9, 14, 20]))
    assert pool.free == 0 and not pool.ensure_tokens("new", 1)
    pool.release("y")
    assert pool.free == 2
    assert pool.ensure_tokens("x", 8) and pool.used["x"] == 2
    events: list[dict] = []
    r = simulate([Request("probe", 17, 8, 2)], token_budget=8,
                 blocks=2, block_size=8, trace=events)[0]
    assert (r.first_token_at, r.finished_at) == (19, 20)
    assert all(e["tokens"] <= 8 for e in events)
    try:
        simulate([Request("oversized", 0, 9, 1)], blocks=1, block_size=8)
    except RuntimeError:
        pass
    else:
        raise AssertionError("unserviceable work must not loop forever")
    for bad in (0, -1, float("nan"), float("inf")):
        try:
            weight_bytes(3, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid precision accepted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    memory = commands.add_parser("memory")
    memory.add_argument("--parameters", type=float, default=3)
    for flag, default in (("weight-bits", 16), ("layers", 24), ("kv-heads", 4),
                          ("head-dim", 96), ("context", 6144),
                          ("concurrent-requests", 6), ("kv-bytes", 2)):
        memory.add_argument("--" + flag, type=int, default=default)
    memory.set_defaults(run=memory_report)
    commands.add_parser("simulate").set_defaults(run=simulation_report)
    commands.add_parser("check").set_defaults(run=lambda _: print("OK: offline invariants"))
    args = parser.parse_args()
    try:
        self_test()
        args.run(args)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
