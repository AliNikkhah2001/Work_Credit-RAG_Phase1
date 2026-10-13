# Work Credit RAG — Benchmark Report

> Generated 2026-10-13 11:00 UTC · model: ics-helper-agent · total turns 41 · conversations 12 · avg latency 6439 ms · error rate 0.0% · judge gemma-4-31b

Artifacts: `bench_results_latest.json` + `ragas_results_latest.json` → `bench_report_latest.html` / `.md`

## 1. Overall Metrics (0–1, higher is better; hallucination inverted)

| Metric | Score |
|---|---:|
| faithfulness | 0.522 |
| answer_relevancy | 0.558 |
| context_relevancy | 0.127 |
| context_recall | 0.320 |
| hallucination (inverted = 1 − hallucination 0.244) | 0.756 |
| ambiguity_resolution | 1.000 |
| sticky_persistence | 0.683 |
| retrieval_hit | 0.732 |

## 2. Per-Subspace Comparison

> Columns: count, faithfulness, answer_relevancy, context_relevancy, hallucination (inv), ambiguity, sticky, retrieval_hit, p50 latency

| Subspace | count | faith | ans_rel | ctx_rel | hall_inv | amb | sticky | hit | p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| cheque | 9 | 0.433 | 0.556 | 0.222 | 0.667 | 1.000 | 0.556 | 0.556 | 10638 ms |
| facilities_person | 6 | 0.867 | 0.500 | 0.333 | 0.500 | 1.000 | 0.667 | 0.500 | 9364 ms |
| facilities_legal | 3 | 0.867 | 0.200 | 0.067 | 0.667 | 1.000 | 0.333 | 0.667 | 9225 ms |
| general | 10 | 0.820 | 0.490 | 0.080 | 0.800 | 1.000 | 0.500 | 0.700 | 10106 ms |
| **overall** | 41 | 0.522 | 0.558 | 0.127 | 0.756 | 1.000 | 0.683 | 0.732 | 6282 ms |

## 3. Per-Conversation Drill-Down

### conv_cheque_01 — greeting -> cheque granular -> cheque sticky follow-up [cheque]

elapsed 27027 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سلام | greeting → stop ✓ | — → ∅ — | 1373 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 2 | چک برگشتی چیست و چگونه رفع سوء اثر می‌شود؟ | stop → stop ✓ | cheque → ∅ ✗ | 12564 ms | 0.800 | چک برگشتی زمانی رخ می‌دهد که در هنگام ارائه چک به بانک، موجودی حساب شخص کافی نبا | 5 chunks: کد دلیل: DCH3-6 متن دلیل: فرد در یک ماه گذشته سابقه رفع سوء  |
| 3 | اگر چکم بدون موجودی باشد چه کار کنم؟ | stop → stop ✓ | cheque → ∅ ✗ | 12089 ms | 0.200 | در صورتی که چکی به دلیل عدم موجودی برگشت خورده است، اولین و حیاتی‌ترین اقدام برا | 5 chunks: سوال: آیا چک‌هایی که در سامانه صیاد ثبت نشده‌اند، در اعتبارس |

### conv_cheque_02 — scattered clarify -> cheque spec -> cheque sticky granular [cheque]

elapsed 21592 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | وضعیت اعتباری چطور است | clarify → clarify ✓ | — → ∅ — | 5188 ms | 0.000 | برای راهنمایی دقیق‌تر، لطفاً بفرمایید منظور شما بررسی وضعیت اعتباری برای اشخاص ح | 5 chunks: سوال: آیا سابقه اعتباری فقط مختص افراد حقیقی است یا اشخاص حق |
| 2 | چک | stop → stop ✓ | cheque → cheque ✓ | 1378 ms | 0.000 | حوزه «گزارش اعتباری چک» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |
| 3 | تاثیر چک برگشتی بر امتیاز اعتباری چقدر است؟ | stop → stop ✓ | cheque → cheque ✓ | 14107 ms | 0.700 | سابقه برگشت خوردن هر نوع چکی یکی از عوامل کلیدی در ارزیابی‌های اعتباری است و به  | 5 chunks: سوال: آیا چک‌هایی که در سامانه صیاد ثبت نشده‌اند، در اعتبارس |

### conv_facilities_person_01 — clarify -> facilities_person -> sticky -> cheque re-spec [facilities_person]

elapsed 16141 ms · turns 4

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | وضعیت اعتباری چطور است | clarify → clarify ✓ | — → ∅ — | 2627 ms | 0.000 | برای راهنمایی دقیق‌تر، لطفاً بفرمایید منظورتان بررسی وضعیت اعتباری برای اشخاص حق | 5 chunks: سوال: آیا سابقه اعتباری فقط مختص افراد حقیقی است یا اشخاص حق |
| 2 | تسهیلات اشخاص حقیقی | stop → stop ✓ | facilities_person → facilities_person ✓ | 1368 ms | 1.000 | حوزه «تسهیلات اشخاص حقیقی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |
| 3 | آیا میزان درآمد یا گردش حساب من هم در بهبود رتبه ا | stop → stop ✓ | facilities_person → facilities_person ✓ | 9392 ms | 0.700 | در نسخه فعلی مدل امتیاز اعتبارسنجی تسهیلات، میزان درآمد یا گردش حساب شما هیچ تاث | 5 chunks: سوال: من درآمدم بالا هستش (n تومنه) چرا رتبه‌م B2 (یا هر رتب |
| 4 | چک | stop → stop ✓ | cheque → cheque ✓ | 1378 ms | 0.000 | حوزه «گزارش اعتباری چک» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |

### conv_facilities_person_02 — greeting -> scattered -> facilities_person granular [facilities_person]

elapsed 7744 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سلام خوبی؟ | greeting → stop ✓ | — → ∅ — | 1422 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 2 | بدهکار شدم چیکار کنم | clarify → clarify ✓ | — → ∅ — | 3912 ms | 0.000 | برای راهنمایی دقیق‌تر، ممکن است بفرمایید منظور شما بدهی مربوط به تسهیلات (شخصی ی | 5 chunks: سوال: شرکت اعتبارسنجی ایران یعنی چی؟ پاسخ کوتاه: شرکت اعتبار |
| 3 | اعتبارسنجی تسهیلات برای اشخاص حقیقی | stop → stop ✓ | facilities_person → facilities_person ✓ | 1421 ms | 1.000 | حوزه «تسهیلات اشخاص حقیقی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |

### conv_facilities_legal_01 — facilities_legal granular -> board-role re-spec to general [facilities_legal]

elapsed 24439 ms · turns 2

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | محدودیت‌های تسهیلات برای اشخاص حقوقی چیست؟ | stop → stop ✓ | facilities_legal → ∅ ✗ | 9225 ms | 0.600 | سلام. من دستیار هوشمند شرکت اعتبارسنجی ایران هستم و می‌توانم در زمینه‌های گزارش  | 5 chunks: سوابق تسهیلاتی، چک و مالیاتی شرکت‌ها تا ۵ سال در پایگاه داده |
| 2 | هیات مدیره چه نقشی دارد؟ | stop → stop ✓ | general → general ✓ | 14533 ms | 0.600 | در فرآیند ثبت شرکت‌ها و تاسیس کسب‌وکارها، اعتبارسنجی اعضای هیئت مدیره به عنوان ی | 5 chunks: سوال: آیا سابقه بازپرداخت اقساط وام از تمامی وام دهندگان رسم |

### conv_facilities_legal_02 — greeting -> facilities_legal short spec [facilities_legal]

elapsed 3394 ms · turns 2

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سلام | greeting → stop ✓ | — → ∅ — | 1308 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 2 | تسهیلات اشخاص حقوقی | stop → stop ✓ | facilities_legal → facilities_legal ✓ | 1400 ms | 1.000 | حوزه «تسهیلات اشخاص حقوقی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |

### conv_general_01 — general entity -> general intro -> cheque re-spec [general]

elapsed 19308 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | قاسم بور کیه | stop → stop ✓ | general → general ✓ | 9770 ms | 1.000 | سلام، من دستیار هوشمند شرکت اعتبارسنجی ایران هستم و می‌توانم در زمینه‌های گزارش  | 5 chunks: Key: رضا قاسم‌پور / Value: مدیرعامل و عضو هیئت مدیره / رضا ق |
| 2 | معرفی شرکت اعتبارسنجی ایران | stop → stop ✓ | general → general ✓ | 1416 ms | 0.000 | حوزه «پایگاه دانش عمومی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |
| 3 | چک برگشتی چیست | stop → stop ✓ | cheque → cheque ✓ | 7255 ms | 1.000 | بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد. | 0 |

### conv_general_02 — clarify -> general rejection with manager query [general]

elapsed 9819 ms · turns 2

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | وضعیت اعتباری چطور است | clarify → clarify ✓ | — → ∅ — | 2975 ms | 0.000 | برای راهنمایی دقیق‌تر، لطفاً بفرمایید منظور شما بررسی وضعیت اعتباری برای اشخاص ح | 5 chunks: سوال: آیا سابقه اعتباری فقط مختص افراد حقیقی است یا اشخاص حق |
| 2 | هیچکدوم موارد بالا نیست، مدیر عامل شرکت کیه؟ | stop → stop ✓ | general → ∅ ✗ | 6282 ms | 1.000 | مدیرعامل فعلی شرکت اعتبارسنجی ایران دکتر رضا قاسم‌پور هستند. ایشان دارای مدرک دک | 5 chunks: دکتر رضا قاسم‌پور در حال حاضر مدیرعامل شرکت اعتبارسنجی ایران |

### conv_mixed_01 — cheque -> facilities_person re-spec [mixed]

elapsed 3500 ms · turns 2

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | چک | stop → stop ✓ | cheque → cheque ✓ | 1362 ms | 0.000 | حوزه «گزارش اعتباری چک» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |
| 2 | حالا درباره تسهیلات اشخاص حقیقی بگو | stop → stop ✓ | facilities_person → facilities_person ✓ | 1427 ms | 1.000 | حوزه «تسهیلات اشخاص حقیقی» انتخاب شد. حالا سوالتان را در همین حوزه بفرمایید. | 0 |

### conv_greeting_01 — greeting x2 -> scattered clarify [greeting]

elapsed 6469 ms · turns 3

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سلام | greeting → stop ✓ | — → ∅ — | 1401 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 2 | سلام علیکم | greeting → stop ✓ | — → ∅ — | 1390 ms | 0.000 | سلام! من دستیار هوشمند شرکت اعتبارسنجی ایران هستم. سوالتان را درباره گزارش اعتبا | 0 |
| 3 | اعتبارسنجی چیست | clarify → clarify ✓ | — → ∅ — | 2689 ms | 0.000 | برای راهنمایی دقیق‌تر، آیا مایلید درباره اعتبارسنجی تسهیلات (برای افراد یا شرکت‌ | 5 chunks: سوال: آیا سابقه سفته در سامانه اعتبارسنجی ثبت می‌شود و بر رت |

### conv_hallucination_01 — hallucination guard: fake G5 grade must not be hallucinated [general]

elapsed 9099 ms · turns 1

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | نمره اعتباری من G5 است چه امتیازی میگیرم | stop → stop ✓ | — → ∅ — | 8872 ms | 1.000 | سلام. من دستیار هوشمند شرکت اعتبارسنجی ایران هستم و می‌توانم در زمینه گزارش اعتب | 5 chunks: سوال: رتبه A1 یعنی چی؟ پاسخ کوتاه: رتبه اعتباری A1 در بازه ا |

### conv_supplement_01 — supplemental entity list: shareholders [general]

elapsed 7187 ms · turns 1

| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |
|---|---|---|---|---|---|---|---|
| 1 | سهامداران شرکت اعتبارسنجی ایران چه کسانی هستند | stop → stop ✓ | general → facilities_legal ✗ | 6832 ms | 1.000 | سلام. من دستیار هوشمند شرکت اعتبارسنجی ایران هستم و می‌توانم در زمینه‌های مربوط  | 5 chunks: سوال: آیا سابقه اعتباری من در شرکت‌های اعتبارسنجی دیگر کشوره |

### Single-Turn Baselines

| ID | Query | Expected → Actual | Latency | Faith | Retrieved |
|---|---|---|---|---|---|
| single_cheque_granular | چک برگشتی چیست و چگونه رفع اثر می‌شود؟ | stop → stop | 10911 ms | 0.600 | 10 |
| single_facilities_person_granular | امتیاز اعتباری اشخاص حقیقی چگونه محاسبه می‌شود؟ | stop → stop | 9364 ms | 0.600 | 10 |
| single_facilities_legal_granular | الزامات وثایق برای اشخاص حقوقی چیست؟ | stop → stop | 20312 ms | 1.000 | 10 |
| single_general_granular | تاریخچه شرکت اعتبارسنجی ایران را بگو | stop → stop | 10254 ms | 0.600 | 10 |
| single_cheque_bounce_effect | تاثیر چک برگشتی بر امتیاز اعتباری چقدر است؟ | stop → stop | 10638 ms | 0.600 | 10 |
| single_facilities_person_income | آیا میزان درآمد یا گردش حساب در رتبه اعتباری تاثیر | stop → stop | 9710 ms | 0.900 | 10 |
| single_facilities_legal_board | هیات مدیره شرکت اعتبارسنجی ایران چه کسانی هستند؟ | stop → stop | 13396 ms | 1.000 | 10 |
| single_general_shareholders | سهامداران شرکت اعتبارسنجی ایران چه کسانی هستند؟ | stop → stop | 10106 ms | 1.000 | 10 |
| single_greeting | سلام | greeting → stop | 1295 ms | 0.000 | 0 |
| single_scattered | وضعیت اعتباری چطور است | clarify → clarify | 3026 ms | 0.500 | 10 |
| single_hallucination_probe | نمره اعتباری من G5 است چه امتیازی میگیرم | stop → stop | 10175 ms | 1.000 | 10 |
| single_qasem_bour | قاسم بور کیه | stop → stop | 8469 ms | 1.000 | 10 |

## 4. Hallucination Details — G5 Guard

> G5 is a non-existent grade. Correct response must contain `پاسخی یافت نشد` or `وجود ندارد / یافت نشد / نامعتبر` and must NOT invent a G5 tier/score. Hallucination 1.0 = hallucinated (bad).

- **conv_hallucination_01 T1:** query `نمره اعتباری من G5 است چه امتیازی میگیرم` · hallucination 1.000 · refusal `پاسخی یافت نشد` ✗ · response: `سلام. من دستیار هوشمند شرکت اعتبارسنجی ایران هستم و می‌توانم در زمینه گزارش اعتباری، امتیاز و رتبه اعتباری، روش‌های بهبود امتیاز و بررسی سوابق منفی و چک‌ها به ش`
- **single_hallucination_probe:** query `نمره اعتباری من G5 است چه امتیازی میگیرم` · hallucination 1.000 · refusal ✗ · response: `سلام. من دستیار هوشمند شرکت اعتبارسنجی ایران هستم و می‌توانم در زمینه گزارش اعتباری، امتیاز و رتبه اعتباری، روش‌های بهبود امتیاز و بررسی سوابق منفی و چک‌ها به ش`

## 5. Ambiguity Resolution Scatter

| Conv / Turn | Query | Expected | Actual | Score | Result |
|---|---|---|---|---|---|
| conv_cheque_02 T1 | وضعیت اعتباری چطور است | clarify | clarify | 1.000 | ✓ clarified |
| conv_facilities_person_01 T1 | وضعیت اعتباری چطور است | clarify | clarify | 1.000 | ✓ clarified |
| conv_facilities_person_02 T2 | بدهکار شدم چیکار کنم | clarify | clarify | 1.000 | ✓ clarified |
| conv_general_02 T1 | وضعیت اعتباری چطور است | clarify | clarify | 1.000 | ✓ clarified |
| conv_greeting_01 T3 | اعتبارسنجی چیست | clarify | clarify | 1.000 | ✓ clarified |
| single_scattered | وضعیت اعتباری چطور است | clarify | clarify | 1.000 | ✓ clarified |

## 6. Sticky Persistence Timeline

### conv_cheque_01 — greeting -> cheque granular -> cheque sticky follow-up

- **applied_subspace:** T1:∅ → T2:∅ → T3:∅
- **expected_subspace:** T1:— → T2:cheque → T3:cheque
  - T1 `سلام` sticky 1.000 
  - T2 `چک برگشتی چیست و چگونه رفع سوء اثر می‌شو` sticky 0.000 ✗
  - T3 `اگر چکم بدون موجودی باشد چه کار کنم؟` sticky 0.000 ✗

### conv_cheque_02 — scattered clarify -> cheque spec -> cheque sticky granular

- **applied_subspace:** T1:∅ → T2:cheque → T3:cheque
- **expected_subspace:** T1:— → T2:cheque → T3:cheque
  - T1 `وضعیت اعتباری چطور است` sticky 1.000 
  - T2 `چک` sticky 1.000 ✓
  - T3 `تاثیر چک برگشتی بر امتیاز اعتباری چقدر ا` sticky 1.000 ✓

### conv_facilities_person_01 — clarify -> facilities_person -> sticky -> cheque re-spec

- **applied_subspace:** T1:∅ → T2:facilities_person → T3:facilities_person → T4:cheque
- **expected_subspace:** T1:— → T2:facilities_person → T3:facilities_person → T4:cheque
  - T1 `وضعیت اعتباری چطور است` sticky 1.000 
  - T2 `تسهیلات اشخاص حقیقی` sticky 1.000 ✓
  - T3 `آیا میزان درآمد یا گردش حساب من هم در به` sticky 1.000 ✓
  - T4 `چک` sticky 1.000 ✓

### conv_facilities_person_02 — greeting -> scattered -> facilities_person granular

- **applied_subspace:** T1:∅ → T2:∅ → T3:facilities_person
- **expected_subspace:** T1:— → T2:— → T3:facilities_person
  - T1 `سلام خوبی؟` sticky 1.000 
  - T2 `بدهکار شدم چیکار کنم` sticky 1.000 
  - T3 `اعتبارسنجی تسهیلات برای اشخاص حقیقی` sticky 1.000 ✓

### conv_facilities_legal_01 — facilities_legal granular -> board-role re-spec to general

- **applied_subspace:** T1:∅ → T2:general
- **expected_subspace:** T1:facilities_legal → T2:general
  - T1 `محدودیت‌های تسهیلات برای اشخاص حقوقی چیس` sticky 0.000 ✗
  - T2 `هیات مدیره چه نقشی دارد؟` sticky 1.000 ✓

### conv_facilities_legal_02 — greeting -> facilities_legal short spec

- **applied_subspace:** T1:∅ → T2:facilities_legal
- **expected_subspace:** T1:— → T2:facilities_legal
  - T1 `سلام` sticky 1.000 
  - T2 `تسهیلات اشخاص حقوقی` sticky 1.000 ✓

### conv_general_01 — general entity -> general intro -> cheque re-spec

- **applied_subspace:** T1:general → T2:general → T3:cheque
- **expected_subspace:** T1:general → T2:general → T3:cheque
  - T1 `قاسم بور کیه` sticky 1.000 ✓
  - T2 `معرفی شرکت اعتبارسنجی ایران` sticky 1.000 ✓
  - T3 `چک برگشتی چیست` sticky 1.000 ✓

### conv_general_02 — clarify -> general rejection with manager query

- **applied_subspace:** T1:∅ → T2:∅
- **expected_subspace:** T1:— → T2:general
  - T1 `وضعیت اعتباری چطور است` sticky 1.000 
  - T2 `هیچکدوم موارد بالا نیست، مدیر عامل شرکت ` sticky 0.000 ✗

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

## 8. Retry / Fallback Observability (T7)

Total turns 41 — fallback_used 14 (34.1% if fb_total_m else '0%') — broaden_used 18 (43.9% if fb_total_m else '0%')

| Subspace | turns | fallback_used | fallback rate | broaden_used | broaden rate |
|---|---|---|---|---|---|
| cheque | 12 | 4 | 33.3% | 7 | 58.3% |
| facilities_legal | 4 | 1 | 25.0% | 1 | 25.0% |
| facilities_person | 9 | 3 | 33.3% | 3 | 33.3% |
| general | 12 | 6 | 50.0% | 7 | 58.3% |
| greeting | 4 | 0 | 0.0% | 0 | 0.0% |

| ID / Turn | Subspace | Query | Fallback? | Broaden? | Reason | Timing |
|---|---|---|---|---|---|---|
| conv_cheque_01 T2 | cheque | چک برگشتی چیست و چگونه رفع سوء اثر می‌شو | yes | yes | low_score top=0.0262 < thr=0.150 / broadened top_k=30 boost= | broad 3212.2ms |
| conv_cheque_01 T3 | cheque | اگر چکم بدون موجودی باشد چه کار کنم؟ | — | yes |  |  |
| conv_cheque_02 T3 | cheque | تاثیر چک برگشتی بر امتیاز اعتباری چقدر ا | yes | yes | filtered_empty sub=گزارش اعتباری چک / broadened top_k=30 boo | retry 940.9ms broad 1384.4ms |
| conv_facilities_person_01 T3 | facilities_person | آیا میزان درآمد یا گردش حساب من هم در به | yes | yes | low_score top=0.0323 < thr=0.100 sub=اشخاص حقیقی/اعتبارسنجی  | retry 43.1ms broad 119.4ms |
| conv_facilities_person_01 T4 | cheque | چک | — | yes |  |  |
| conv_facilities_legal_01 T2 | general | هیات مدیره چه نقشی دارد؟ | yes | yes | low_score top=0.0290 < thr=0.150 sub=پایگاه دانش عمومی / bro | retry 1686.4ms broad 766.4ms |
| conv_general_01 T1 | general | قاسم بور کیه | yes | yes | low_score top=0.0323 < thr=0.150 sub=پایگاه دانش عمومی / bro | retry 2314.2ms broad 53.6ms |
| conv_general_01 T2 | general | معرفی شرکت اعتبارسنجی ایران | — | yes |  |  |
| conv_general_01 T3 | cheque | چک برگشتی چیست | — | yes |  |  |
| conv_hallucination_01 T1 | general | نمره اعتباری من G5 است چه امتیازی میگیرم | yes | yes | low_score top=0.0272 < thr=0.150 / broadened top_k=30 boost= | broad 48.9ms |
| single_cheque_granular | cheque | چک برگشتی چیست و چگونه رفع اثر می‌شود؟ | yes | yes | low_score top=0.0279 < thr=0.150 / broadened top_k=30 boost= | broad 589.4ms |
| single_facilities_person_granular | facilities_person | امتیاز اعتباری اشخاص حقیقی چگونه محاسبه  | yes | yes | low_score top=0.0315 < thr=0.150 / broadened top_k=30 boost= | broad 92.6ms |
| single_facilities_legal_granular | facilities_legal | الزامات وثایق برای اشخاص حقوقی چیست؟ | yes | yes | low_score top=0.0228 < thr=0.150 / broadened top_k=30 boost= | broad 3957.1ms |
| single_cheque_bounce_effect | cheque | تاثیر چک برگشتی بر امتیاز اعتباری چقدر ا | yes | yes | low_score top=0.0320 < thr=0.150 / broadened top_k=30 boost= | broad 38.5ms |
| single_facilities_person_income | facilities_person | آیا میزان درآمد یا گردش حساب در رتبه اعت | yes | yes | low_score top=0.0308 < thr=0.150 / broadened top_k=30 boost= | broad 68.9ms |
| single_facilities_legal_board | general | هیات مدیره شرکت اعتبارسنجی ایران چه کسان | yes | yes | low_score top=0.0328 < thr=0.150 sub=پایگاه دانش عمومی / bro | retry 4114.6ms broad 118.9ms |
| single_hallucination_probe | general | نمره اعتباری من G5 است چه امتیازی میگیرم | yes | yes | low_score top=0.0272 < thr=0.150 / broadened top_k=30 boost= | broad 833.3ms |
| single_qasem_bour | general | قاسم بور کیه | yes | yes | low_score top=0.0323 < thr=0.150 sub=پایگاه دانش عمومی / bro | retry 36.0ms broad 2334.0ms |

---
_Generated 2026-10-13 11:00 UTC · bench 2026-10-13T11:00:40.674846+00:00 · judge gemma-4-31b · error_rate 0.0%_