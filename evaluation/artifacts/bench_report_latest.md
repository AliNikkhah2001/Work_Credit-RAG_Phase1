# Work Credit RAG — Benchmark Report

> Generated 2026-10-12 08:49 UTC · model: ics-helper-agent · total turns 41 · conversations 12 · avg latency 9079 ms · error rate 0.0% · judge gemma-4-31b

Artifacts: `bench_results_latest.json` + `ragas_results_latest.json` → `bench_report_latest.html` / `.md`

## 1. Overall Metrics (0–1, higher is better; hallucination inverted)

| Metric | Score |
|---|---:|
| faithfulness | 0.644 |
| answer_relevancy | 0.212 |
| context_relevancy | 0.078 |
| context_recall | 0.113 |
| hallucination (inverted = 1 − hallucination 0.195) | 0.805 |
| ambiguity_resolution | 0.854 |
| sticky_persistence | 0.610 |
| retrieval_hit | 0.537 |

## 2. Per-Subspace Comparison

> Columns: count, faithfulness, answer_relevancy, context_relevancy, hallucination (inv), ambiguity, sticky, retrieval_hit, p50 latency

| Subspace | count | faith | ans_rel | ctx_rel | hall_inv | amb | sticky | hit | p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| cheque | 9 | 0.556 | 0.000 | 0.111 | 0.667 | 1.000 | 0.444 | 0.111 | 10741 ms |
| facilities_person | 6 | 0.833 | 0.000 | 0.100 | 0.500 | 1.000 | 0.500 | 0.167 | 7130 ms |
| facilities_legal | 3 | 0.933 | 0.233 | 0.067 | 0.667 | 1.000 | 0.667 | 0.333 | 11150 ms |
| general | 10 | 0.660 | 0.200 | 0.140 | 0.900 | 1.000 | 0.300 | 0.600 | 8006 ms |
| **overall** | 41 | 0.644 | 0.212 | 0.078 | 0.805 | 0.854 | 0.610 | 0.537 | 8006 ms |

## 3. Per-Conversation Drill-Down

### conv_cheque_01 — greeting -> cheque granular -> cheque sticky follow-up [cheque]

elapsed 36879 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سلام | greeting → stop ✓ | — → ∅ — | 11426 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 2 | چک برگشتی چیست و چگونه رفع سوء اثر می‌شود؟ | stop → stop ✓ | cheque → ∅ ✗ | 9244 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |
| 3 | اگر چکم بدون موجودی باشد چه کار کنم؟ | stop → stop ✓ | cheque → ∅ ✗ | 15374 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |

### conv_cheque_02 — scattered clarify -> cheque spec -> cheque sticky granular [cheque]

elapsed 31923 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | وضعیت اعتباری چطور است | clarify → stop ✗ | — → ∅ — | 11071 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |
| 2 | چک | stop → stop ✓ | cheque → cheque ✓ | 2357 ms | 0.000 | حوزه «گزارش اعتباری چک» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |
| 3 | تاثیر چک برگشتی بر امتیاز اعتباری چقدر است؟ | stop → stop ✓ | cheque → ∅ ✗ | 17525 ms | 0.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 5 chunks: سوال: اگر چک تضمین‌شده (ضمانت) داشته باشم و برگشت بخورد، آیا |

### conv_facilities_person_01 — clarify -> facilities_person -> sticky -> cheque re-spec [facilities_person]

elapsed 36969 ms · turns 4

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | وضعیت اعتباری چطور است | clarify → stop ✗ | — → ∅ — | 7736 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |
| 2 | تسهیلات اشخاص حقیقی | stop → stop ✓ | facilities_person → facilities_person ✓ | 7130 ms | 1.000 | حوزه «تسهیلات اشخاص حقیقی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |
| 3 | آیا میزان درآمد یا گردش حساب من هم در بهبود رتبه ا | stop → stop ✓ | facilities_person → ∅ ✗ | 19447 ms | 0.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 5 chunks: سوال: من درآمدم بالا هستش (n تومنه) چرا رتبه‌م B2 (یا هر رتب |
| 4 | چک | stop → stop ✓ | cheque → cheque ✓ | 1458 ms | 0.000 | حوزه «گزارش اعتباری چک» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |

### conv_facilities_person_02 — greeting -> scattered -> facilities_person granular [facilities_person]

elapsed 17379 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سلام خوبی؟ | greeting → stop ✓ | — → ∅ — | 5685 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 2 | بدهکار شدم چیکار کنم | clarify → stop ✗ | — → ∅ — | 8998 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |
| 3 | اعتبارسنجی تسهیلات برای اشخاص حقیقی | stop → stop ✓ | facilities_person → facilities_person ✓ | 1785 ms | 1.000 | حوزه «تسهیلات اشخاص حقیقی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |

### conv_facilities_legal_01 — facilities_legal granular -> board-role re-spec to general [facilities_legal]

elapsed 29535 ms · turns 2

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | محدودیت‌های تسهیلات برای اشخاص حقوقی چیست؟ | stop → stop ✓ | facilities_legal → facilities_legal ✓ | 11150 ms | 0.800 | سلام، من دستیار هوشمند شرکت اعتبارسنجی ایران هستم و می‌توانم در زمینه‌های گزارش  | 5 chunks: سوابق تسهیلاتی، چک و مالیاتی شرکت‌ها تا ۵ سال در پایگاه داده |
| 2 | هیات مدیره چه نقشی دارد؟ | stop → stop ✓ | general → ∅ ✗ | 17738 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 5 chunks: کد دلیل: DCB3-3 متن دلیل: تسهیلات ضمانت شده توسط فرد در 3 ما |

### conv_facilities_legal_02 — greeting -> facilities_legal short spec [facilities_legal]

elapsed 8559 ms · turns 2

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سلام | greeting → stop ✓ | — → ∅ — | 1776 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 2 | تسهیلات اشخاص حقوقی | stop → stop ✓ | facilities_legal → facilities_legal ✓ | 6139 ms | 1.000 | حوزه «تسهیلات اشخاص حقوقی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |

### conv_general_01 — general entity -> general intro -> cheque re-spec [general]

elapsed 29885 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | قاسم بور کیه | stop → stop ✓ | general → ∅ ✗ | 12204 ms | 0.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 5 chunks: Key: رضا قاسم‌پور / Value: مدیرعامل و عضو هیئت مدیره / رضا ق |
| 2 | معرفی شرکت اعتبارسنجی ایران | stop → stop ✓ | general → general ✓ | 1631 ms | 0.000 | حوزه «پایگاه دانش عمومی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |
| 3 | چک برگشتی چیست | stop → stop ✓ | cheque → cheque ✓ | 15193 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |

### conv_general_02 — clarify -> general rejection with manager query [general]

elapsed 28758 ms · turns 2

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | وضعیت اعتباری چطور است | clarify → stop ✗ | — → ∅ — | 20353 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |
| 2 | هیچکدوم موارد بالا نیست، مدیر عامل شرکت کیه؟ | stop → stop ✓ | general → general ✓ | 8006 ms | 1.000 | مدیرعامل فعلی شرکت اعتبارسنجی ایران دکتر رضا قاسم‌پور است. ایشان علاوه بر مدیریت | 5 chunks: دکتر رضا قاسم‌پور در حال حاضر مدیرعامل شرکت اعتبارسنجی ایران |

### conv_mixed_01 — cheque -> facilities_person re-spec [mixed]

elapsed 2916 ms · turns 2

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | چک | stop → stop ✓ | cheque → cheque ✓ | 1244 ms | 0.000 | حوزه «گزارش اعتباری چک» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |
| 2 | حالا درباره تسهیلات اشخاص حقیقی بگو | stop → stop ✓ | facilities_person → facilities_person ✓ | 1241 ms | 1.000 | حوزه «تسهیلات اشخاص حقیقی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |

### conv_greeting_01 — greeting x2 -> scattered clarify [greeting]

elapsed 22732 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سلام | greeting → stop ✓ | — → ∅ — | 7059 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 2 | سلام علیکم | greeting → stop ✓ | — → ∅ — | 1928 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 3 | اعتبارسنجی چیست | clarify → stop ✗ | — → ∅ — | 13141 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |

### conv_hallucination_01 — hallucination guard: fake G5 grade must not be hallucinated [general]

elapsed 14023 ms · turns 1

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | نمره اعتباری من G5 است چه امتیازی میگیرم | stop → stop ✓ | — → ∅ — | 13828 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |

### conv_supplement_01 — supplemental entity list: shareholders [general]

elapsed 9472 ms · turns 1

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سهامداران شرکت اعتبارسنجی ایران چه کسانی هستند | stop → stop ✓ | general → ∅ ✗ | 9251 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |

### Single-Turn Baselines

| ID | Query | Expected → Actual | Latency | Faith | Retrieved |
|---|---|---|---|---|---|
| single_cheque_granular | چک برگشتی چیست و چگونه رفع اثر می‌شود؟ | stop → stop | 10741 ms | 1.000 | 0 |
| single_facilities_person_granular | امتیاز اعتباری اشخاص حقیقی چگونه محاسبه می‌شود؟ | stop → stop | 8797 ms | 1.000 | 0 |
| single_facilities_legal_granular | الزامات وثایق برای اشخاص حقوقی چیست؟ | stop → stop | 25304 ms | 1.000 | 0 |
| single_general_granular | تاریخچه شرکت اعتبارسنجی ایران را بگو | stop → stop | 17268 ms | 0.600 | 10 |
| single_cheque_bounce_effect | تاثیر چک برگشتی بر امتیاز اعتباری چقدر است؟ | stop → stop | 11793 ms | 1.000 | 0 |
| single_facilities_person_income | آیا میزان درآمد یا گردش حساب در رتبه اعتباری تاثیر | stop → stop | 6215 ms | 1.000 | 0 |
| single_facilities_legal_board | هیات مدیره شرکت اعتبارسنجی ایران چه کسانی هستند؟ | stop → stop | 4501 ms | 1.000 | 10 |
| single_general_shareholders | سهامداران شرکت اعتبارسنجی ایران چه کسانی هستند؟ | stop → stop | 5677 ms | 1.000 | 0 |
| single_greeting | سلام | greeting → stop | 1275 ms | 0.000 | 0 |
| single_scattered | وضعیت اعتباری چطور است | clarify → stop | 6835 ms | 1.000 | 0 |
| single_hallucination_probe | نمره اعتباری من G5 است چه امتیازی میگیرم | stop → stop | 6782 ms | 1.000 | 0 |
| single_qasem_bour | قاسم بور کیه | stop → stop | 5920 ms | 0.000 | 10 |

## 4. Hallucination Details — G5 Guard

> G5 is a non-existent grade. Correct response must contain `پاسخی یافت نشد` or `وجود ندارد / یافت نشد / نامعتبر` and must NOT invent a G5 tier/score. Hallucination 1.0 = hallucinated (bad).

- **conv_hallucination_01 T1:** query `نمره اعتباری من G5 است چه امتیازی میگیرم` · hallucination 0.000 · refusal `پاسخی یافت نشد` ✗ · response: `بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد.`
- **single_hallucination_probe:** query `نمره اعتباری من G5 است چه امتیازی میگیرم` · hallucination 0.000 · refusal ✗ · response: `بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد.`

## 5. Ambiguity Resolution Scatter

| Conv / Turn | Query | Expected | Actual | Score | Result |
|---|---|---|---|---|---|
| conv_cheque_02 T1 | وضعیت اعتباری چطور است | clarify | stop | 0.000 | ✗ not clarified |
| conv_facilities_person_01 T1 | وضعیت اعتباری چطور است | clarify | stop | 0.000 | ✗ not clarified |
| conv_facilities_person_02 T2 | بدهکار شدم چیکار کنم | clarify | stop | 0.000 | ✗ not clarified |
| conv_general_02 T1 | وضعیت اعتباری چطور است | clarify | stop | 0.000 | ✗ not clarified |
| conv_greeting_01 T3 | اعتبارسنجی چیست | clarify | stop | 0.000 | ✗ not clarified |
| single_scattered | وضعیت اعتباری چطور است | clarify | stop | 0.000 | ✗ not clarified |

## 6. Sticky Persistence Timeline

### conv_cheque_01 — greeting -> cheque granular -> cheque sticky follow-up

- **applied_subspace:** T1:∅ → T2:∅ → T3:∅
- **expected_subspace:** T1:— → T2:cheque → T3:cheque
  - T1 `سلام` sticky 1.000 
  - T2 `چک برگشتی چیست و چگونه رفع سوء اثر می‌شو` sticky 0.000 ✗
  - T3 `اگر چکم بدون موجودی باشد چه کار کنم؟` sticky 0.000 ✗

### conv_cheque_02 — scattered clarify -> cheque spec -> cheque sticky granular

- **applied_subspace:** T1:∅ → T2:cheque → T3:∅
- **expected_subspace:** T1:— → T2:cheque → T3:cheque
  - T1 `وضعیت اعتباری چطور است` sticky 1.000 
  - T2 `چک` sticky 1.000 ✓
  - T3 `تاثیر چک برگشتی بر امتیاز اعتباری چقدر ا` sticky 0.000 ✗

### conv_facilities_person_01 — clarify -> facilities_person -> sticky -> cheque re-spec

- **applied_subspace:** T1:∅ → T2:facilities_person → T3:∅ → T4:cheque
- **expected_subspace:** T1:— → T2:facilities_person → T3:facilities_person → T4:cheque
  - T1 `وضعیت اعتباری چطور است` sticky 1.000 
  - T2 `تسهیلات اشخاص حقیقی` sticky 1.000 ✓
  - T3 `آیا میزان درآمد یا گردش حساب من هم در به` sticky 0.000 ✗
  - T4 `چک` sticky 1.000 ✓

### conv_facilities_person_02 — greeting -> scattered -> facilities_person granular

- **applied_subspace:** T1:∅ → T2:∅ → T3:facilities_person
- **expected_subspace:** T1:— → T2:— → T3:facilities_person
  - T1 `سلام خوبی؟` sticky 1.000 
  - T2 `بدهکار شدم چیکار کنم` sticky 1.000 
  - T3 `اعتبارسنجی تسهیلات برای اشخاص حقیقی` sticky 1.000 ✓

### conv_facilities_legal_01 — facilities_legal granular -> board-role re-spec to general

- **applied_subspace:** T1:facilities_legal → T2:∅
- **expected_subspace:** T1:facilities_legal → T2:general
  - T1 `محدودیت‌های تسهیلات برای اشخاص حقوقی چیس` sticky 1.000 ✓
  - T2 `هیات مدیره چه نقشی دارد؟` sticky 0.000 ✗

### conv_facilities_legal_02 — greeting -> facilities_legal short spec

- **applied_subspace:** T1:∅ → T2:facilities_legal
- **expected_subspace:** T1:— → T2:facilities_legal
  - T1 `سلام` sticky 1.000 
  - T2 `تسهیلات اشخاص حقوقی` sticky 1.000 ✓

### conv_general_01 — general entity -> general intro -> cheque re-spec

- **applied_subspace:** T1:∅ → T2:general → T3:cheque
- **expected_subspace:** T1:general → T2:general → T3:cheque
  - T1 `قاسم بور کیه` sticky 0.000 ✗
  - T2 `معرفی شرکت اعتبارسنجی ایران` sticky 1.000 ✓
  - T3 `چک برگشتی چیست` sticky 1.000 ✓

### conv_general_02 — clarify -> general rejection with manager query

- **applied_subspace:** T1:∅ → T2:general
- **expected_subspace:** T1:— → T2:general
  - T1 `وضعیت اعتباری چطور است` sticky 1.000 
  - T2 `هیچکدوم موارد بالا نیست، مدیر عامل شرکت ` sticky 1.000 ✓

### conv_mixed_01 — cheque -> facilities_person re-spec

- **applied_subspace:** T1:cheque → T2:facilities_person
- **expected_subspace:** T1:cheque → T2:facilities_person
  - T1 `چک` sticky 1.000 ✓
  - T2 `حالا درباره تسهیلات اشخاص حقیقی بگو` sticky 1.000 ✓

### conv_greeting_01 — greeting x2 -> scattered clarify

- **applied_subspace:** T1:∅ → T2:∅ → T3:∅
- **expected_subspace:** T1:— → T2:— → T3:—
  - T1 `سلام` sticky 1.000 
  - T2 `سلام علیکم` sticky 1.000 
  - T3 `اعتبارسنجی چیست` sticky 1.000 

## 7. Direct Retrieval Probe (with vs without filter)

12 probes (top1 with vs without filter_path)

| ID | Subspace | Query | no_filter score | has_results | with_filter score | has_results | filter improves |
|---|---|---|---|---|---|---|---|
| single_cheque_granular | گزارش اعتباری چک | چک برگشتی چیست و چگونه رفع اثر می‌شود؟ | 0.028 | ✓ | — | ✗ | None |
| single_facilities_person_granular | اشخاص حقیقی/اعتبارسنجی تسهیلات | امتیاز اعتباری اشخاص حقیقی چگونه محاسبه  | 0.032 | ✓ | 0.033 | ✓ | True |
| single_facilities_legal_granular | اشخاص حقوقی/اعتبارسنجی تسهیلات | الزامات وثایق برای اشخاص حقوقی چیست؟ | 0.023 | ✓ | 0.029 | ✓ | True |
| single_general_granular | پایگاه دانش عمومی | تاریخچه شرکت اعتبارسنجی ایران را بگو | 0.033 | ✓ | 0.033 | ✓ | True |
| single_cheque_bounce_effect | گزارش اعتباری چک | تاثیر چک برگشتی بر امتیاز اعتباری چقدر ا | 0.032 | ✓ | — | ✗ | None |
| single_facilities_person_income | اشخاص حقیقی/اعتبارسنجی تسهیلات | آیا میزان درآمد یا گردش حساب در رتبه اعت | 0.031 | ✓ | 0.031 | ✓ | True |
| single_facilities_legal_board | پایگاه دانش عمومی | هیات مدیره شرکت اعتبارسنجی ایران چه کسان | 0.033 | ✓ | 0.033 | ✓ | True |
| single_general_shareholders | پایگاه دانش عمومی | سهامداران شرکت اعتبارسنجی ایران چه کسانی | 0.033 | ✓ | 0.033 | ✓ | True |
| single_greeting | ∅ | سلام | 0.500 | ✓ | 0.500 | ✓ | True |
| single_scattered | ∅ | وضعیت اعتباری چطور است | 0.020 | ✓ | 0.020 | ✓ | True |
| single_hallucination_probe | ∅ | نمره اعتباری من G5 است چه امتیازی میگیرم | 0.027 | ✓ | 0.027 | ✓ | True |
| single_qasem_bour | پایگاه دانش عمومی | قاسم بور کیه | 0.032 | ✓ | 0.032 | ✓ | True |

---
_Generated 2026-10-12 08:49 UTC · bench 2026-10-12T08:49:11.920129+00:00 · judge gemma-4-31b · error_rate 0.0%_