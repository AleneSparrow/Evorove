# Corpus manifest — companion Step 1 (8 September 2026)

**Status:** catalog only. Not an approved playbook. Not a training job.  
**Cycle:** 2 (phrasing an already-chosen `SalesMove`). Not people search. Not booking.  
**Rule:** closed-access text is in-scope only if the owner deposited a copy in `private/sales-corpus/` (gitignored). This file never contains chapter text.

Provenance:

| Value | Meaning |
| --- | --- |
| `page-verified` | Owner-deposited copy; a specific page/section was checked |
| `title-only` | Title/author/concept known; pages not checked against a copy |
| `needs-licence` | Cited often; do not copy; wait for a deposited copy or a clear open licence |

Proposed use: `positive_rule` / `negative_counterexample` / `skip`.

## Owner-deposited

How to drop files: `docs/sales-knowledge/how-to-deposit-books-ru.md`. Scan: `python scripts/ingest_sales_corpus.py`.

| Title | Author / origin | Year | Licence | URL or private file | Deposited | Provenance | Use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sales training Q&A pack (161 pairs) | owner-supplied zip | 2026 | owner deposited the pack; underlying books inside the Q&A are **not** licensed by this deposit | `private/sales-corpus/sales_training_project.zip`; working copy `evals/companion_step1/` | yes (synthetic Q&A, not PDFs) | title-only for named books inside | **skip as positive SFT.** Textbook Q&A, often Russian. Feel-Felt-Found appears as a correct answer. Conflicts with spec 0.4. Keep on disk as a source index only. |

Live book scan (filenames only; ingest rewrites this block):

<!-- corpus-ingest:deposited:start -->
Scanned 2026-09-12T07:06:46+00:00. Book bytes stay gitignored. This table has filenames only.


| File | Title | Licence | Catalog | Pages | Provenance | Use |
| --- | --- | --- | --- | --- | --- | --- |
| `Adam Lashinsky — Inside Apple How America's Most Admired--and Secretive--Company.epub` | Adam Lashinsky — Inside Apple How America's Most Admired--and Secretive--Company | my-copy | unmapped | 24 | title-only | unmapped; owner should name the methodology |
| `Aliza Sherman, Danielle Elliott Smith — Social Media Engagement For Dummies®.epub` | Aliza Sherman, Danielle Elliott Smith — Social Media Engagement For Dummies® | my-copy | unmapped | 29 | title-only | unmapped; owner should name the methodology |
| `Barbara Joanne Winter — Making a Living Without a Job Winning Ways for Creating .fb2` | Barbara Joanne Winter — Making a Living Without a Job Winning Ways for Creating  | my-copy | unmapped | 290 | title-only | unmapped; owner should name the methodology |
| `Colin Gautrey — 21 Dirty Tricks at Work How to Beat the Game of Office Politics.epub` | 21 Dirty Tricks at Work | my-copy | gautrey-dirty-tricks | 17 | page-located | negative_counterexample; office politics is not a sales move |
| `Ellen E. Schultz — Retirement Heist how companies plunder and profit from the ne.fb2` | Ellen E. Schultz — Retirement Heist how companies plunder and profit from the ne | my-copy | unmapped | 257 | title-only | unmapped; owner should name the methodology |
| `Harvard Business Review (HBR) — Продажи.epub` | HBR on Sales | my-copy | hbr-sales | 21 | page-located | positive_rule only for diagnose/confirm; skip corporate-process dump |
| `Jan Zimmerman, Deborah Ng — Social Media Marketing All-in-One For Dummies®.epub` | Jan Zimmerman, Deborah Ng — Social Media Marketing All-in-One For Dummies® | my-copy | unmapped | 58 | title-only | unmapped; owner should name the methodology |
| `Javier Blas, Jack Farchy — Мир на продажу. Деньги, власть и торговцы, которые об.fb2` | Javier Blas, Jack Farchy — Мир на продажу. Деньги, власть и торговцы, которые об | my-copy | unmapped | 377 | title-only | unmapped; owner should name the methodology |
| `Mitsuyuki Masatsugu — The Modern Samurai Society Duty and Dependence in Contempo.fb2` | Mitsuyuki Masatsugu — The Modern Samurai Society Duty and Dependence in Contempo | my-copy | unmapped | 233 | title-only | unmapped; owner should name the methodology |
| `Richard Nelson Bolles — What Color Is Your Parachute.fb2` | Richard Nelson Bolles — What Color Is Your Parachute | my-copy | unmapped | 346 | title-only | unmapped; owner should name the methodology |
| `Smart Reading — Ключевые идеи книги Оффер на $100 миллионов. Как делать предложе.epub` | Smart Reading — Ключевые идеи книги Оффер на $100 миллионов. Как делать предложе | my-copy | unmapped | 4 | title-only | unmapped; owner should name the methodology |
| `Smart Reading — Убеждай и продавай. 11 лучших книг для успешных продаж в одной.epub` | Smart Reading — Убеждай и продавай. 11 лучших книг для успешных продаж в одной | my-copy | unmapped | 46 | title-only | unmapped; owner should name the methodology |
| `Tony Hsieh — Exceptional Customer service.epub` | Exceptional Customer Service | my-copy | hsieh-service | 33 | page-located | positive_rule for warm tone; skip invented wow-gifts |
| `Адам_Грант_Брать_или_отдавать_Новый_взгляд_на_психологию_отнош.fb2` | Адам Грант Брать или отдавать Новый взгляд на психологию отнош | my-copy | give-and-take | 388 | page-located | positive_rule only when DNA already authorizes a free step; otherwise skip invented reciprocity |
| `Александр Дьяк — Техника продаж для новичков. Основы телефонных переговоров.fb2` | Техника продаж для новичков | my-copy | dyak-phone-sales | 2 | page-located | skip as call-center formula; not companion tone |
| `Александр Михайлович Банкин — Контент-маркетинг для роста продаж.fb2` | Контент-маркетинг для роста продаж | my-copy | bankin-content | 216 | page-located | skip as a content calendar; not a live sales turn |
| `Анатолий Николаевич Верчинский — Продажи и переговоры смотрите, как надо продава.epub` | Продажи и переговоры | my-copy | verchinsky-sales | 53 | page-located | skip demo-lecture tone; map only, no SFT until reviewed |
| `Арндт Трайндл — Мастерство ритейл-брендинга.fb2` | Мастерство ритейл-брендинга | my-copy | traindl-retail-brand | 113 | page-located | skip branding textbook |
| `Брайан_Трейси_Оставьте_брезгливость,_съешьте_лягушку!.fb2` | Брайан Трейси Оставьте брезгливость, съешьте лягушку! | my-copy | eat-that-frog | 83 | page-located | positive_rule for doing the hard follow-up first; not a customer-pressure tactic |
| `Даниэль Канеман   Thinking, Fast and Slow.epub` | Даниэль Канеман   Thinking, Fast and Slow | my-copy | thinking-fast-slow | 71 | page-located | negative_counterexample for System-1 fake urgency; diagnose slowly |
| `Джеб_Блаунт_Фанатичные_продажи_Принципы_экстремально_быстрого.epub` | Fanatical Prospecting | my-copy | fanatical-prospecting | 62 | page-located | positive_rule |
| `Джеффри А. Мур — Преодоление пропасти. Маркетинг и продажа хайтек-товаров массов.fb2` | Crossing the Chasm | my-copy | crossing-the-chasm | 274 | page-located | skip as a chat script; positioning, not a customer turn |
| `Джил Конрат   Гибкие продажи.fb2` | Agile Selling | my-copy | agile-selling | 160 | page-located | positive_rule |
| `Джил_Конрат_Продажи_большим_компаниям.fb2` | Selling to Big Companies | my-copy | selling-to-big-companies | 50 | page-located | positive_rule |
| `Джо_Наварро,_Марвин_Карлинс_Я_вижу,_о_чём_вы_думаете.fb2` | Джо Наварро, Марвин Карлинс Я вижу, о чём вы думаете | my-copy | what-every-body-is-saying | 245 | page-located | skip in SMS/chat; negative if the mouth claims it can read the body |
| `Дмитрий Потапов — Маркетинг продаж.fb2` | Маркетинг продаж | my-copy | potapov-sales-marketing | 29 | page-located | skip as a marketing textbook; not a chat turn |
| `Дональд_Миллер,_Джей_Джей_Питерсон_Воронки_продаж_по_методу_St.epub` | Marketing Made Simple | my-copy | storybrand-funnel | 21 | page-located | positive_rule |
| `Дональд_Миллер_Метод_StoryBrand_2_0_Расскажите_о_своем_бренде.fb2` | Building a StoryBrand 2.0 | my-copy | storybrand-2 | 197 | page-located | positive_rule |
| `Дональд_Миллер_Метод_StoryBrand_Расскажите_о_своем_бренде_так,.epub` | Building a StoryBrand | my-copy | storybrand | 23 | page-located | positive_rule |
| `Дэвид Мэттсон   49 законов продаж.fb2` | The Sandler Rules | my-copy | sandler-rules | 132 | page-located | positive_rule |
| `Дэн_Ариели_Предсказуемая_иррациональность_Скрытые_силы,_опред.fb2` | Дэн Ариели Предсказуемая иррациональность Скрытые силы, опред | my-copy | predictably-irrational | 269 | page-located | negative_counterexample for invented anchors, fake free, or comparison prices |
| `Йанив Заид — Библия продаж XXI века. Секреты маркетинга, переговоров и убеждения.fb2` | Библия продаж XXI века | my-copy | zaid-sales-bible | 318 | page-located | positive_rule only where it matches spec 0.4; skip hard close |
| `Йенс Нордфальт — Ритейл-маркетинг.fb2` | Ритейл-маркетинг | my-copy | nordfalt-retail | 606 | page-located | skip store layout; not SMS/chat companion |
| `Кейт_Феррацци_Никогда_не_ешьте_в_одиночку_и_другие_правила_нет.fb2` | Кейт Феррацци Никогда не ешьте в одиночку и другие правила нет | my-copy | never-eat-alone | 372 | page-located | positive_rule for generous follow-up; spray-and-pray networking is skip |
| `Крис_Восс_Никаких_компромиссов_Веди_переговоры_так,_словно_от.fb2` | Never Split the Difference | my-copy | never-split-the-difference | 276 | page-located | positive_rule |
| `Мартин_Э_П_Селигман_Как_научиться_оптимизму_Измените_взгляд.fb2` | Мартин Э П Селигман Как научиться оптимизму Измените взгляд | my-copy | learned-optimism | 379 | page-located | positive_rule for tone; outcome guarantees stay negative |
| `Мэттью_Диксон,_Брент_Адамсон_Чемпионы_продаж.epub` | The Challenger Sale | my-copy | challenger-sale | 97 | deposited-copy | positive_rule |
| `Николай Юрьевич Рысев — Активные продажи 3.4 Стратегии переговоров.fb2` | Активные продажи | my-copy | rysev-active-sales | 84 | page-located | positive_rule for one discovery question; skip pressure closes |
| `Нил Рекхэм   СПИН-продажи.fb2` | SPIN Selling | my-copy | spin-selling | 152 | page-located | positive_rule |
| `Ричард_Талер,_Касс_Р_Санстейн_Nudge_Архитектура_выбора.fb2` | Ричард Талер, Касс Р Санстейн Nudge Архитектура выбора | my-copy | nudge | 269 | page-located | negative_counterexample unless DNA already has a real default the customer chose |
| `Роберт_Бено_Чалдини_Influence_The_Psychology_of_Persuasion.fb2` | Influence: The Psychology of Persuasion | my-copy | influence | 350 | page-located | positive_rule (reciprocity/consistency); scarcity is negative unless DNA has a real limit |
| `Роберт_Бено_Чалдини_Психология_согласия_Революционная_методик.fb2` | Influence: The Psychology of Persuasion | my-copy | influence | 347 | page-located | positive_rule (reciprocity/consistency); scarcity is negative unless DNA has a real limit |
| `Роджер_Фишер,_Уильям_Юри,_Брюс_Паттон_Переговоры_без_поражения.fb2` | Getting to Yes | my-copy | getting-to-yes | 206 | page-located | positive_rule |
| `Сергей Аширович Азимов — Продажи, переговоры. Практика, примеры.epub` | Продажи, переговоры. Практика, примеры | my-copy | azimov-sales-practice | 1 | page-located | skip call-center scripts; negative if it hammers close |
| `Тамара Сергеевна Жданова — Ленивый маркетинг. Принципы пассивных продаж.fb2` | Ленивый маркетинг | my-copy | zhdanova-lazy-marketing | 135 | page-located | skip passive-funnel lore; STOP still outranks nurture |
| `Эван Хантер — Сбытчик.fb2` | Эван Хантер — Сбытчик | my-copy | unmapped | 560 | title-only | unmapped; owner should name the methodology |
| `Эми_Кадди_Присутствие_духа_Как_направить_силы_своей_личност.fb2` | Эми Кадди Присутствие духа Как направить силы своей личност | my-copy | presence | 355 | page-located | positive_rule for calm tone; skip power-posing as a sales trick |
| `Ян Броди — Продающие рассылки. Повышаем продажи, используя email-маркетинг.fb2` | Email Persuasion / Продающие рассылки | my-copy | brody-email | 115 | page-located | positive_rule for a single next step in writing; skip blast-pack offers |
<!-- corpus-ingest:deposited:end -->

## Open or government (short derived rules allowed)

| Title | Author | Year | Licence | URL | Deposited | Provenance | Use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Advertising FAQ / truth-in-advertising guidance | U.S. FTC | n/a | U.S. government work (public domain) | https://www.ftc.gov/business-guidance/advertising-and-marketing | no (URL) | title-only (hub page; not a page-checked PDF) | positive_rule: no unsubstantiated guarantee, price, or performance claim |
| Stop Unwanted Robocalls and Texts | U.S. FCC | n/a | U.S. government work | https://www.fcc.gov/consumers/guides/stop-unwanted-robocalls-and-texts | no (URL) | title-only | positive_rule: STOP / revoke consent ends marketing texts; companion does not keep selling |
| TCPA consent revocation order | FCC 24-24 | 2024 | U.S. government work | https://docs.fcc.gov/public/attachments/FCC-24-24A1.pdf | no | title-only | positive_rule: honor opt-out; do not invent a legal exception |
| Scientific Advertising | Claude C. Hopkins | 1923 | public domain in the U.S. (1923) | https://archive.org/details/scientificadvert0000hopk | **no copy in this repo** (do not commit the scan) | title-only until owner deposits a file | positive_rule: specific, testable claims; skip puffery. Do not paste chapters. |

## Methodologies still needs-licence (title rows only)

Do not reconstruct paywalled books. Do not scrape LibGen / Anna’s Archive.

| Title | Author | Year | Licence | Notes | Use |
| --- | --- | --- | --- | --- | --- |
| SPIN Selling | Neil Rackham | 1988 | closed | owner deposited a copy; card still `candidate` | positive_rule |
| The Challenger Sale | Dixon / Adamson | 2011 | closed | owner deposited a copy; reframe only with DNA fact (0.4) | positive_rule |
| Influence | Robert Cialdini | various | closed | owner deposited a copy; scarcity stays **negative** unless DNA has a real limit | positive_rule / negative scarcity |
| Never Split the Difference | Voss / Raz | 2016 | closed | owner deposited a copy; one what/how for DIAGNOSE_OBJECTION | positive_rule |
| Fanatical Prospecting | Jeb Blount | 2015 | closed | owner deposited a copy; STOP still outranks cadence | positive_rule |
| Feel-Felt-Found formula | attribution disputed | n/a | n/a | `candidate-objection-script-feel-felt-found-CONTESTED-008` | **negative_counterexample** |
| Trial time-to-value industry lore | unnamed | n/a | n/a | `candidate-trial-time-to-value-007` | **skip** until a named deposited source |

The 84 URLs in `evals/companion_step1/sources/sources.csv` are a **needs-licence queue**, not a licence grant. Many are blogs, Amazon book pages, or vendor summaries. None were copied into git as article text.

## Product posture (not a book)

Spec 0.4 in `docs/sales-agent-implementation-plan-ru.md` is binding for this dataset: no Feel-Felt-Found as a positive; scarcity only with a verified fact; one calibrated question; no invented reciprocity gift.

## Ready for Step 2 training?

<!-- corpus-ingest:ready:start -->
**Yes (corpus only, 2026-09-12T07:06:46+00:00).** At least one **core** conversation-sales title is deposited. Archive files stay registered and do not unlock SFT. The incoming folder stays open — drop more purchased files and re-run ingest anytime. Ingest still does **not** start a training job. Review derived JSONL, then Step 2 is a separate owner decision.
<!-- corpus-ingest:ready:end -->
