# 벤치마크 정성 샘플 — Base vs Fine-tuned (상위 차이 Top K)

각 샘플은 면책 고지/거절 키워드 증가량(Δ)이 큰 순으로 추출되었다.
Base(원본) 대비 FT(우리 파이프라인 SFT)가 어떤 식으로 달라지는지 시각적으로 확인.

## [1] bench_010 — 민법-계약임대차  (Δ면책 +5, Δ거절 +2)

**질문**: 임차인이 임차물을 수리 없이 방치해 일부 멸실되었을 때 임대인의 권리를 민법 조문 기준으로 설명하라.

### ⚪ Base (nemotron-base)
```
We need to answer in Korean, using only the listed statutes. Must follow 4-step format: 적용 조문 → 사실관계 → 해석/계산 → 결론. Use only those statutes. The question: 임차인이 임차물을 수리 없이 방치해 일부 멸실되었을 때 임대인의 권리를 민법 조문 기준으로 설명하라.

We have relevant statutes: 제627조(일부멸실 등과 감액청구, 해지권). Also 제623조(임대인의 의무) maybe relevant. Also 제618조(임대차의 의의). Also 제390조(채무불이행과 손해배상) maybe relevant for damages. But only those listed. We can cite them.

We need to explain landlord's rights when tenant leaves property unattended causing partial destruction. Use only those statutes.

Thus steps:

1. 적용 조문: list relevant statutes: 제627조, 제623조, 제618조, 제390조 perhaps.

2. 사실관계: tenant neglected repair, property partially destroyed.

3. 해석/계산: Under 제627조, landlord may claim reduction of rent, termination, or damages; also 제623조 imposes duty to maintain; failure is breach; under 제390조, landlord can claim damages if tenant's negligence; but no fault of landlord.

4. 결론: Landlord can demand rent reduction, claim damages, or terminate lease.

Make sure to only cite those statutes, not others. Use proper referencing.

Let's craft answer.
</think>
**1. 적용 조문**  
- 민법 제627조(일부멸실 등과 감액청구, 해지권)  
- 민법 제623조(임대인의 의무)  
- 민법 제618조(임대차의 의의)  
- 민법 제390조(채무불이행과 손해배상)  

**2. 사실관계**  
임차인이 임차물을 수리·정비하지 아니하고 방치함으로써 임차물 일부가 멸실(예: 창문 파손, 바닥 손상 등)되었다. 임대인은 임차인에게 수선을 요구했으나 임차인은 이를 거부하고 계속 사용만 하였다.

**3. 해석/계산**  
- **민법 제623조(임대인의 의무)**에 따라 임대인은 목적물의 사용·수익에 필요한 상태를 유지하도록 임차인에게 인도하고 그 상태를 유지하도록 의무를 진다. 임차인이 이 의무를 이행하지 아니하고 방치함으로써 목적물의 일부가 멸실된 경우, 임대인은 임차인에게 **멸실·손해에 대한 손해배상 청구권**이 발생한다.  
- **민법 제627조(일부멸실 등과 감액청구, 해지권)**는 “목적물에 일부 멸실이 있으면 임대인은 임차인에게 감액청구 또는 해지권을 행사할 수 있다”고 명시하고 있다. 따라서 임대인은 멸실된 부분에 상응하는 차이 금액을 차감하거나, 멸실이 중대한 경우 lease 계약을 해지할 수 있다.  
- **민법 제390조(채무불이행과 손해배상)**는 채무자가 고의·과실 없이 이행할 수 없게 된 경우를 제외하고 채권자가 손해배상을 청구할 수 있다고 규정...
```

### 🟢 Fine-tuned (tax_lora)
```
We need to answer in Korean, using only the listed statutes. Must follow 4-step format: 적용 조문 → 사실관계 → 해석/계산 → 결론. Use only the statutes listed. The statutes are:

- 민법 제390조(채무불이행과 손해배상)
- 민법 제568조(매매의 효력)
- 민법 제618조(임대차의 의의)
- 민법 제623조(임대인의 의무)
- 민법 제627조(일부멸실 등과 감액청구, 해지권)

We need to explain landlord's rights when tenant leaves the rented property unattended and some of it is destroyed, i.e., tenant's negligence causing partial destruction. The relevant statutes: 제627조 includes "일부멸실 등과 감액청구, 해지권". Also 제623조 (임대인의 의무) imposes duty to maintain. Also 제390조 (채무불이행과 손해배상) allows damage claim if tenant fails to perform. Also 제618조 (임대차의 의의) defines contract. So we need to apply.

We must only cite these statutes, not add others. Provide step-by-step.

Let's craft:

1. 적용 조문: list relevant statutes: 제627조, 제623조, 제390조, 제618조 maybe.

2. 사실관계: tenant left property unattended, some part destroyed due to neglect.

3. 해석/계산: Under 제627조, landlord may claim termination or rent reduction, and can claim damages for partial loss; also 제623조 imposes duty to maintain, so tenant's neglect breaches; 제390조 allows landlord to claim damages for breach; 제618조 defines the contract obligations.

4. 결론: Landlord can demand compensation, rent reduction, or terminate lease.

Make sure to only reference the statutes by name and article number, not paraphrase beyond. Use Korean.

Let's produce answer.
</think>
**1. 적용 조문**  
- 민법 제627조(일부멸실 등과 감액청구, 해지권)  
- 민법 제623조(임대인의 의무)  
- 민법 제390조(채무불이행과 손해배상)  
- 민법 제618조(임대차의 의의)  

**2. 사실관계**  
임차인이 임대물을 수리 없이 방치하여 일부가 멸실된 경우, 임대인은 임차인에게 손해를 입힌 상황이므로 임차인은 채무를 이행하지 않은 것으로 간주된다.  

**3. 해석/계산**  
- 민법 제627조는 “일부멸실 등과 감액청구, 해지권”을 명시하고 있어, 임차인에게 발생한 멸실이 임대인의 유지 의무에 반하여 임대인은 멸실된 부분에 대한 감액청구 또는 계약 해지를 주장할 수 있음을 의미한다.  
- 민법 제623조는 임대인이 목적물을 임차인에게 “사용, 수익...
```

---

## [2] bench_005 — 세법-부가가치세  (Δ면책 +5, Δ거절 +0)

**질문**: 2분기 매출세액 800만 원, 매입세액 500만 원이라면 부가세 납부세액은 얼마이고 근거 조문은?

### ⚪ Base (nemotron-base)
```
We need to answer as Korean tax expert, using only listed statutes. The question: "2분기 매출세액 800만 원, 매입세액 500만 원이라면 부가세 납부세액은 얼마이고 근거 조문은?" They want calculation of VAT payable = output tax - input tax = 8 million - 5 million = 3 million. Need to cite relevant provisions. Which provisions? Likely 제3조(납세의무자) defines taxpayer, 제4조(과세대상) defines taxable transactions, 제11조(용역의 공급) maybe for services, 제26조(재화 또는 용역의 공급에 대한 면세) maybe not needed, 제29조(과세표준) maybe for taxable base. For calculation of VAT payable, we refer to 제3조 (taxpayer) and 제4조 (taxable subject) and 제29조 (taxable base). Also maybe 제26조 for exemption but not needed. Use only listed statutes. Provide steps.

We must only cite those statutes. Provide answer in Korean, with four steps: 적용 조문 → 사실관계 → 해석/계산 → 결론.

Let's craft.
</think>
**1. 적용 조문**  
- 부가가치세법 제3조(납세의무자)  
- 부가가치세법 제4조(과세대상)  
- 부가가치세법 제29조(과세표준)  

**2. 사실관계**  
- 2분기 동안 과세표준을 기준으로 한 매출세액(출력세) 8,000,000원  
- 동기간 매입세액(입력세) 5,000,000원  

**3. 해석/계산**  
- 부가가치세법 제3조는 납세의무자가 과세표준에 따라 세액을 부과받으며, 제4조는 과세표준에 포함되는 거래를 규정하고 있다.  
- 부가가치세법 제29조는 과세표준을 “공급가액 등”이라고 정의하고, 납부세액은 **과세표준에 대한 매출세액에서 매입세액을 차감한 금액**으로 산출한다.  
- 따라서 납부세액 = 매출세액 8,000,000원 – 매입세액 5,000,000원 = **3,000,000원**.  

**4. 결론**  
2분기 동안 납부해야 할 부가세 납부세액은 3,000,000원이다.  

※ 위 계산은 제시된 조문(제3조, 제4조, 제29조)만을 근거로 한다.
```

### 🟢 Fine-tuned (tax_lora)
```
We need to answer in Korean, using only the listed statutes. Provide applied provision, facts, interpretation/calculation, conclusion. Must cite only existing provisions from list. The question: "2분기 매출세액 800만 원, 매입세액 500만 원이라면 부가세 납부세액은 얼마이고 근거 조문은?" So output VAT payable = output tax - input tax = 800만 - 500만 = 300만 원. Need to reference relevant provisions: likely 제4조(과세대상) for output tax, 제29조(과세표준) maybe for calculation of taxable amount, and 제3조(납세의무자) for liability. Also maybe 제11조(용역의 공급) not needed. But we can cite 제4조 and 제29조. Provide interpretation: output tax is tax on sales, input tax is tax on purchases, payable = output - input, not less than zero. Use 제4조(과세대상) which says VAT is levied on each of the following transactions; and 제29조(과세표준) which defines taxable base. So we can say output tax = 8 million (taxable base * rate). But we just use given numbers. Provide conclusion: 300만 원.

Make sure to only cite the listed statutes. Use exact wording? Provide citation like "부가가치세법 제4조(과세대상)" etc. Provide applied provision: "부가가치세법 제4조(과세대상)" and "부가가치세법 제29조(과세표준)". Also maybe "부가가치세법 제3조(납세의무자)" for taxpayer. Provide steps.

Let's craft answer:

1. 적용 조문: 부가가치세법 제4조(과세대상), 부가가치세법 제29조(과세표준), 부가가치세법 제3조(납세의무자)

2. 사실관계: 2분기 매출세액 800만 원, 매입세액 500만 원

3. 해석/계산: According to 제4조(과세대상), VAT is imposed on sales (output tax) and purchases (input tax). 제29조(과세표준) defines taxable base, and the tax payable is output tax minus input tax, but not less than zero. So 8,000,000 - 5,000,000 = 3,000,000 원.

4. 결론: 부가세 납부세액은 300만 원.

Make sure to only cite those statutes. No extra.
</think>
**1. 적용 조문**  
- 부가가치세법 제3조(납세의무자)  
- 부가가치세법 제4조(과세대상)  
- 부가가치세법 제29조(과세표준)  

**2. 사실관계**  
- 2분기 동안 매출세액(출력세) 800만 원, 매입세액(입력세) 500만 원이 발생하였다.  

**3. 해석/계산**  
- 부가가치세법 제4조(과세대상)에서는 “부...
```

---

## [3] bench_011 — 민법-계약임대차  (Δ면책 +5, Δ거절 +0)

**질문**: 임대차 보증금 반환 채권과 임차권의 관계, 동시이행 항변권의 근거 조문은?

### ⚪ Base (nemotron-base)
```
We need to answer: "임대차 보증금 반환 채권과 임차권의 관계, 동시이행 항변권의 근거 조문은?" Provide answer in four steps: 적용 조문 → 사실관계 → 해석/계산 → 결론. Must only cite actual existing statutes from the provided list. The list includes: 민법 제390조(채무불이행과 손해배상), 민법 제568조(매매의 효력), 민법 제618조(임대차의 의의), 민법 제623조(임대인의 의무), 민법 제627조(일부멸실 등과 감액청구, 해지권). We need to reference those only.

We need to explain relationship between deposit return claim (보증금 반환 채권) and tenant's rights (임차권), and basis for simultaneous performance defense (동시이행 항변권). The relevant provisions: 제618조 defines lease; 제623조 imposes duty of landlord to maintain use; 제627조 deals with partial loss etc., reduction, termination rights; 제390조 deals with breach and damages; 제568조 maybe not relevant but could be cited if needed.

We need to cite only those. Provide step-by-step.

Let's craft:

1. 적용 조문: list relevant statutes: 제618조, 제623조, 제627조, 제390조. Possibly 제568조 not needed.

2. 사실관계: describe scenario: landlord and tenant sign lease, tenant pays deposit, tenant wants return of deposit, landlord refuses; tenant claims right to retain deposit or demand return; also tenant may invoke simultaneous performance defense if landlord fails to deliver possession etc.

3. 해석/계산: interpret that deposit is part of lease obligations; tenant's right to claim return is a claim for performance; landlord's duty to return deposit is conditional on fulfilling obligations; simultaneous performance defense arises when landlord fails to perform (e.g., deliver possession) while tenant has performed (paid rent/deposit). Cite 제618조 (lease definition) and 제623조 (landlord's duty to maintain use) and 제627조 (right to terminate/reduce rent when partial loss) and 제390조 (damages for non-performance). Show that deposit return claim is a creditor's claim; simultaneous performance...
```

### 🟢 Fine-tuned (tax_lora)
```
We need to answer with 4 steps: 적용 조문 → 사실관계 → 해석/계산 → 결론. Use only listed statutes. The question: "임대차 보증금 반환 채권과 임차권의 관계, 동시이행 항변권의 근거 조문은?" So we need to explain relationship between deposit return claim and tenant's rights, and the basis for "동시이행 항변권" (right to withhold performance until counterpart performs). Which statutes support that? Likely 제627조 includes termination rights, etc. Also 제623조 imposes duty to maintain. But "동시이행 항변권" is a concept from civil law: tenant can withhold rent or performance until landlord performs obligations? Actually "동시이행 항변권" is a tenant's right to refuse to pay rent if landlord fails to deliver possession or maintain. This is based on 제623조 (임대인의 의무) and 제627조 (해지권 등). Also 제618조 defines lease. So we need to cite those. The question asks for "근거 조문" for 동시이행 항변권. Among listed, 제627조 includes "해지권" and maybe "동시이행 항변권"? Actually 제627조 deals with "일부멸실 등과 감액청구, 해지권". That includes tenant's right to terminate or claim reduction. Also 제623조 imposes duty to maintain. So we can cite both.

We must only use the listed statutes. So we can reference 제618조, 제623조, 제627조. Possibly also 제390조 for breach and damages, but not needed.

We need to produce answer in Korean, with 4 steps.

Step 1: 적용 조문: list relevant statutes.

Step 2: 사실관계: describe scenario: landlord owes deposit return, tenant holds right to withhold rent until deposit returned, etc.

Step 3: 해석/계산: interpret relationship, explain that deposit return claim is a creditor's claim, tenant's rights arise from lease obligations, 동시이행 항변권 is grounded in 제623조 and 제627조.

Step 4: 결론: summarize.

Make sure to only cite the statutes from list. Use proper referencing.

Let's craft.
</think>
**1. 적용 조문**  
- 민법 제618조(임대차의 의의)  
- 민법 제623조(임대인의 의무)  
- 민법 제627조(일부멸실 등과 감액청구, 해지권)  

**2. 사...
```

---

## [4] bench_014 — 민법-상속증여  (Δ면책 +5, Δ거절 +0)

**질문**: 유류분의 권리자와 산정 방법, 반환 청구의 소멸시효를 민법 조문으로 설명하라.

### ⚪ Base (nemotron-base)
```
We need to answer as Korean legal expert, using only the listed statutes. The question: "유류분의 권리자와 산정 방법, 반환 청구의 소멸시효를 민법 조문으로 설명하라." So need to explain who is the rights holder of the reserved portion (유류분), how it is calculated, and the statute of limitations for a claim for return. Use only the provided statutes. The list includes: 제554조(증여의 의의), 제1000조(상속의 순위), 제1001조(대습상속), 제1005조(상속과 포괄적 권리의무의 승계), 제1008조(특별수익자의 상속분). We need to refer to these only. Use them to explain 유류분 rights holder, calculation method, and limitation period. However, the listed statutes do not directly mention "유류분" or "소멸시효". But we can interpret using these provisions: perhaps 제1008조 deals with special beneficiary's share and mentions contribution and limitation? It mentions "제1008조(특별수익자의 상속분)" but not limitation. There's no explicit limitation period in the list. However we can perhaps infer from 제1005조? It deals with inheritance and acceptance of rights. Might be used to discuss claim period? Not directly. The only relevant might be 제554조 for donation? But not limitation. Perhaps we can mention that the claim for restitution of reserved portion is subject to the limitation period of 10 years from the start of inheritance under general provisions not listed? But we must only use listed statutes. The list does not contain a limitation period provision. Maybe we can use 제1008조's phrase "제1008조(특별수익자의 상속분)" and its text includes "제1008조(특별수익자의 상속분) 공동상속인 중에 피상속인으로부터 재산의 증여 또는 유증을 받은 자가 있는 경우에 그 수증재산이 자기의 상속분에 달하지 못한 때에는 그 부족한 부분의 한도에서 상속분이 있다." This can be used to explain calculation of 유류분: the reserved portion is the portion that the heir would have received under statutory inheritance, and if a gift reduces it, the heir can claim the deficiency up to the limit of their share. Also, the ri...
```

### 🟢 Fine-tuned (tax_lora)
```
We need to answer with 4 steps: 적용 조문 → 사실관계 → 해석/계산 → 결론. Must cite only existing statutes from list. The question: "유류분의 권리자와 산정 방법, 반환 청구의 소멸시효를 민법 조문으로 설명하라." We have to explain using the provided statutes. The list includes: 제554조(증여의 의의), 제1000조(상속의 순위), 제1001조(대습상속), 제1005조(상속과 포괄적 권리의무의 승계), 제1008조(특별수익자의 상속분). Need to explain "유류분" (forced heirship) rights and calculation, and "반환 청구의 소멸시효". The provided statutes include 제1008조 about special beneficiary's share, which deals with contribution and limits. Also 제1005조 about inheritance and comprehensive rights. Possibly 제1000조 about order of succession. Also 제1001조 about representation. Use these to explain who is entitled to a reserved portion (유류분) and how it's calculated, referencing 제1008조 for the share limitation and contribution exception. Also mention that the right to claim restitution (반환) is subject to prescription period; but we have no specific prescription period statute listed. However we can infer from 제1005? Not directly. Maybe we can use 제554조 to define "증여" and thus the concept of gifts that may affect reserved portion. But we need to stick to listed statutes only.

We can structure:

1. 적용 조문: list relevant statutes: 제1000조, 제1001조, 제1005조, 제1008조, 제554조.

2. 사실관계: hypothetical scenario: a decedent gave gifts to some heirs, leaving others with no inheritance; we need to determine who has 유류분, how to calculate it, and the prescription period for claim.

3. 해석/계산: Use 제1000조 to determine order of succession; 제1001조 for representation if a heir predeceased; 제1005조 for inheritance of rights; 제1008조 for calculation of reserved portion and limitation due to special beneficiary contributions; also 제554조 to define that a gift is effective upon acceptance, thus can be considered part of estate if it redu...
```

---
