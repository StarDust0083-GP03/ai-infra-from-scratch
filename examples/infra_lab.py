#!/usr/bin/env python3
"""CPU-only AI infrastructure calculator and continuous-batching toy simulator."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass

GIB = 1024**3


def weight_bytes(parameters: int, bits_per_weight: int) -> int:
    return math.ceil(parameters * bits_per_weight / 8)


def kv_cache_bytes(
    *, layers: int, kv_heads: int, head_dim: int, tokens: int, bytes_per_element: int
) -> int:
    """K and V for every layer and token. Ignores allocator/workspace overhead."""
    return 2 * layers * kv_heads * head_dim * tokens * bytes_per_element


def training_state_bytes(
    parameters: int,
    *,
    weight_bytes_per_param: int = 2,
    gradient_bytes_per_param: int = 2,
    optimizer_bytes_per_param: int = 12,
) -> int:
    """Common mixed-precision Adam-style estimate, excluding activations/buffers."""
    return parameters * (
        weight_bytes_per_param + gradient_bytes_per_param + optimizer_bytes_per_param
    )


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
    def create(cls, blocks: int, block_size: int) -> "BlockPool":
        return cls(blocks, block_size, {})

    @property
    def free(self) -> int:
        return self.blocks - sum(self.used.values())

    def ensure_tokens(self, request: str, tokens: int) -> bool:
        need = math.ceil(tokens / self.block_size)
        current = self.used.get(request, 0)
        extra = max(0, need - current)
        if extra > self.free:
            return False
        self.used[request] = need
        return True

    def release(self, request: str) -> None:
        self.used.pop(request, None)


def simulate(
    requests: list[Request], *, token_budget: int = 12, blocks: int = 24, block_size: int = 4
) -> list[Request]:
    """Toy policy: decode ready requests first, then spend remaining budget on prefill."""
    pool = BlockPool.create(blocks, block_size)
    clock = 0
    while not all(r.done for r in requests):
        available = [r for r in requests if r.arrival <= clock and not r.done]
        budget = token_budget

        # Decode gets one token per ready sequence, approximating iteration-level batching.
        for request in available:
            if budget == 0 or not request.ready_to_decode:
                continue
            total_tokens = request.prompt + request.generated + 1
            if not pool.ensure_tokens(request.name, total_tokens):
                continue
            request.generated += 1
            budget -= 1
            if request.first_token_at is None:
                request.first_token_at = clock + 1
            if request.done:
                request.finished_at = clock + 1
                pool.release(request.name)

        # Chunked prefill uses whatever token budget remains.
        for request in available:
            if budget == 0 or request.ready_to_decode or request.done:
                continue
            chunk = min(budget, request.prompt - request.prefilled)
            if not pool.ensure_tokens(request.name, request.prefilled + chunk):
                continue
            request.prefilled += chunk
            budget -= chunk

        clock += 1
        if clock > 10_000:
            raise RuntimeError("simulation made no progress; increase KV blocks")
    return requests


def memory_report(args: argparse.Namespace) -> None:
    parameters = int(args.parameters * 1_000_000_000)
    weights = weight_bytes(parameters, args.weight_bits)
    total_tokens = args.context * args.concurrent_requests
    kv = kv_cache_bytes(
        layers=args.layers,
        kv_heads=args.kv_heads,
        head_dim=args.head_dim,
        tokens=total_tokens,
        bytes_per_element=args.kv_bytes,
    )
    training = training_state_bytes(parameters)
    print(f"权重下界: {gib(weights):.2f} GiB")
    print(f"KV Cache 下界: {gib(kv):.2f} GiB ({total_tokens:,} active tokens)")
    print(f"训练状态示例: {gib(training):.2f} GiB（不含激活、临时区和通信缓冲）")
    print(f"推理小计: {gib(weights + kv):.2f} GiB（仍需预留运行时余量）")


def simulation_report(_: argparse.Namespace) -> None:
    sample = [
        Request("short", arrival=0, prompt=6, output=4),
        Request("long", arrival=0, prompt=18, output=5),
        Request("late", arrival=2, prompt=4, output=3),
    ]
    result = simulate(sample)
    print("request  TTFT(step)  finish(step)  total tokens")
    for r in result:
        assert r.first_token_at is not None and r.finished_at is not None
        print(f"{r.name:7}  {r.first_token_at-r.arrival:10}  {r.finished_at:12}  {r.prompt+r.output:12}")


def self_test() -> None:
    assert round(gib(weight_bytes(7_000_000_000, 16)), 2) == 13.04
    assert gib(kv_cache_bytes(layers=32, kv_heads=8, head_dim=128, tokens=131_072, bytes_per_element=2)) == 16
    assert round(gib(training_state_bytes(7_000_000_000)), 2) == 104.31
    pool = BlockPool.create(3, 4)
    assert pool.ensure_tokens("a", 5) and pool.free == 1
    assert not pool.ensure_tokens("b", 8)
    pool.release("a")
    assert pool.free == 3
    result = simulate([Request("a", 0, 4, 2)], token_budget=4, blocks=4, block_size=4)
    assert result[0].first_token_at == 2 and result[0].finished_at == 3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    memory = sub.add_parser("memory", help="estimate weight, KV, and training-state memory")
    memory.add_argument("--parameters", type=float, default=7, help="billions of parameters")
    memory.add_argument("--weight-bits", type=int, default=16)
    memory.add_argument("--layers", type=int, default=32)
    memory.add_argument("--kv-heads", type=int, default=8)
    memory.add_argument("--head-dim", type=int, default=128)
    memory.add_argument("--context", type=int, default=8192)
    memory.add_argument("--concurrent-requests", type=int, default=8)
    memory.add_argument("--kv-bytes", type=int, default=2)
    memory.set_defaults(run=memory_report)
    simulation = sub.add_parser("simulate", help="run a tiny continuous-batching simulation")
    simulation.set_defaults(run=simulation_report)
    args = parser.parse_args()
    self_test()
    args.run(args)


if __name__ == "__main__":
    main()
