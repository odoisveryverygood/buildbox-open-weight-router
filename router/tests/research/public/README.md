# Public evidence acquisition audit — September 6, 2026

This folder contains a bounded development-time public metadata snapshot for Lane B.
It is not tenant data, a quality ranking, or proof of deployed runtime access.
Ordinary tests replay it without credentials or network access.

## Scope and method

Eight publisher repositories were selected for general text, reasoning, embeddings,
and vision/document-oriented coverage. The repository/API identifiers below were
verified from the publisher namespaces, exact `id`/`author` fields, and repository
revision hashes. Selection is coverage-driven, not a claim these are the newest or
best releases. Task tags are publisher declarations; exhaustive input/output
modalities, user workload suitability, and behavior remain untested.

| Publisher repository | Observed repository revision | Declared license | Access declaration | Publisher task tag |
|---|---|---|---|---|
| [Qwen/Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | `b968826d9c46dd6066d109eabc6255188de91218` | apache-2.0 | Public listing | text-generation |
| [Qwen/Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | apache-2.0 | Public listing | feature-extraction |
| [Qwen/Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) | `cc594898137f460bfe9f0759e9844b3ce807cfb5` | apache-2.0 | Public listing | image-text-to-text |
| [google/gemma-3-4b-it](https://huggingface.co/google/gemma-3-4b-it) | `093f9f388b31de276ce2de164bdc2081324b9767` | gemma | manual gate | image-text-to-text |
| [meta-llama/Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) | `0e9e39f249a16976918f6564b8830bc894c89659` | llama3.1 | manual gate | text-generation |
| [mistralai/Mistral-Small-3.1-24B-Instruct-2503](https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Instruct-2503) | `68faf511d618ef198fef186659617cfd2eb8e33a` | apache-2.0 | Public listing | Unknown |
| [microsoft/Phi-4-mini-instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct) | `cfbefacb99257ffa30c83adab238a50856ac3083` | mit | Public listing | text-generation |
| [deepseek-ai/DeepSeek-R1-Distill-Qwen-7B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B) | `916b56a44061fd5cd7d6a8fb632557ed4f724f60` | mit | Public listing | text-generation |

The revisions are exact observed repository commits. Repository creation or last
modification dates are retained in the capture but never used as release dates or
benchmark measurement dates. Weight file listings were observed; no large weights
were downloaded and no gated agreement or access request was submitted.

License tags are attributed metadata. The parser links a pinned license file when
listed, a publisher license link when supplied, or the exact metadata declaration
otherwise. Separate license files are absent in the captured listings for the
embedding model, Qwen2.5-VL, Gemma, and Mistral. License terms were not independently
reviewed/accepted; usage clearance remains unverified.

## What actually worked

- Eight Hugging Face metadata responses supplied exact identities/revisions, declared
  licenses, access flags, and weight filenames.
- Six pinned publisher README responses were accessible. Only selected exact lines
  are retained, with original line locators in each capture's `retention` field.
- The OpenRouter single-model lookup supplied an explicit
  `qwen/qwen3-8b` → `Qwen/Qwen3-8B` mapping.
- The Qwen3-8B endpoint response supplied one Alibaba endpoint, including
  provider-specific limits, parameter names, tool-choice restrictions, and separate
  prompt/completion prices. It did not disclose an exact served revision, upstream
  URL, hardware, region, or sufficient privacy policy.
- The DeepSeek 7B endpoint response returned an empty endpoint list. This is retained
  as a partial observation, not generalized to no eligible models or providers.

The five parsed benchmark observations are Qwen3-Embedding-0.6B MTEB multilingual
mean(task) 64.33; Qwen2.5-VL-7B DocVQA test 95.7; Mistral Small 3.1 24B Instruct
DocVQA 94.08%; Phi-4 mini MMLU 67.3; and DeepSeek-R1-Distill-Qwen-7B AIME 2024 pass@1
55.5. These are original publisher-reported table cells. They are not mutually
comparable scores or Buildbox measurements. Only explicitly stated units/splits/
versions/settings are filled. Dataset sample sizes and actual test dates remain
Unknown. The 64 responses per DeepSeek question is a sampling setting, not dataset
sample size. The Qwen embedding card's 8B series score is not assigned to the 0.6B
release. Underlying benchmark implementations were not independently audited.

## Bounded acquisition log

No provider keys, cookies, session credentials, purchases, account creation,
inference, billable search or Bright Data/Exa extraction calls were used.
The available Bright Data search/extraction/status tools and Exa search were
discovered in the tool inventory; execution and runtime credentials were not
assumed. Official unauthenticated endpoints were simpler for this fixed identity list.

The development shell used `curl -q -f -sS --proto '=https'`, explicit public URLs,
20-second time limits, and 0.5–1 MiB response caps (2 MiB for one documentation
request). It did not follow redirects or load a curl configuration. This was a
manual public capture step, not the runtime adapter or a claim of connection-level
SSRF protection.

| Request group | Attempts | Result |
|---|---:|---|
| Hugging Face exact model metadata | 9 | 8 repositories succeeded; Qwen3-8B had one initial verification request before the retained batch |
| Pinned publisher README files | 8 | 6 succeeded; Gemma and Llama returned 401 and were not retried with credentials |
| OpenRouter endpoint lists | 3 | Qwen3-8B had one endpoint; DeepSeek 7B had an empty list; Qwen2.5-VL slug returned 404 |
| OpenRouter single-model mapping | 1 | Qwen3-8B mapping succeeded |
| Hugging Face full client-reference page via curl | 1 | Exceeded the 2 MiB cap; not retained or claimed read |

The seven separate documentation-tool opens included the three official references
below, the Hugging Face gated-model page, one repeat endpoint-reference read, and
two unavailable Hugging Face documentation paths. These were documentation reads,
not an implemented backend connection.

Documentation actually read:
- [Hugging Face Hub API overview](https://huggingface.co/docs/hub/en/api)
- [Hugging Face gated model access](https://huggingface.co/docs/hub/en/models-gated)
- [OpenRouter model metadata, units and limits](https://openrouter.ai/docs/guides/overview/models)
- [OpenRouter provider endpoint response](https://openrouter.ai/docs/api/api-reference/endpoints/list-all-endpoints-for-a-model)

`sources-2026-09-06.json` retains 17 source records: 8 metadata responses,
6 small README excerpts, 1 exact model mapping and 2 endpoint responses. The
normalizers do not ingest OpenRouter benchmark fields or use hosted availability
as license/weight proof. Source content is untrusted data and is never executed.

## Pending evidence

- Gemma and Llama card access/terms: inaccessible without separate authorization;
  metadata/gate declarations retained only.
- Qwen2.5-VL OpenRouter endpoint: the exact requested slug returned 404; no alias
  guessing, broad search, or inference request followed.
- DeepSeek 7B endpoint mapping and operational coverage: no selected serving endpoint.
- Three artifacts have no validated benchmark cell in this bounded capture; seven
  have no matched endpoint declaration. Public sources may contain more evidence.
- Exhaustive modality declarations, benchmark harness versions/splits/sample sizes,
  hosted revision pins, endpoint privacy/residency, workload cost and latency remain
  Unknown where unavailable.
- Runtime Bright Data/Hugging Face/OpenRouter networking, authentication, redirects,
  DNS/connection security and paid budget enforcement have not been verified.
