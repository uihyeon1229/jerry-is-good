"""Negative test set에 대한 Guardrails regex 차단 검증."""
import json
import sys
sys.path.insert(0, "/home/shadeform/jerry-is-good")
from pipeline.run_guardrails import inline_regex_flag

rows = [
    json.loads(l)
    for l in open(
        "/home/shadeform/jerry-is-good/artifacts/guardrails_negative_test.jsonl"
    )
    if l.strip()
]

print(f"=== Regex 단계 판정 ({len(rows)}건) ===")
block = 0
pass_ = 0
correct = 0
for r in rows:
    cat = r["category"]
    exp = r["expected_verdict"]
    full = r["question"] + "\n" + r["reasoning_cot"]
    flag = inline_regex_flag(full)
    status = f"BLOCK[{flag}]" if flag else "PASS"
    if flag:
        block += 1
    else:
        pass_ += 1
    ok = (
        (exp == "YES_BLOCK" and flag)
        or (exp == "NO_PASS" and not flag)
    )
    if ok:
        correct += 1
    print(f"[{cat:25s}] expected={exp:10s} regex={status:20s} {'OK' if ok else 'MISS(LLM 필요)'}")

print(f"\n--- Regex 단독 성능 ---")
print(f"블록 {block}/{len(rows)}, 통과 {pass_}/{len(rows)}, 정답 {correct}/{len(rows)}")
