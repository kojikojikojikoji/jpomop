# Provenance

jpomop is written from public documents only. This file lists each document, the version used, and when it was retrieved. Specification YAML files cite the page number for every field.

No code, data, documents or other material from any employer or client of the author were used.

## DPC specification

| Document | Version | URL | Retrieved | SHA-256 |
|---|---|---|---|---|
| DPCの評価・検証等に係る調査（退院患者調査）実施説明資料 | FY2026, 2026-07-17 (244 pages) | https://www.mhlw.go.jp/content/12400000/001738680.pdf | 2026-10-12 | f1a099cb57c14251497863cc1fb46c9186c7febd3a7160dca73f9639383b1ed1 |

Terms: the Ministry of Health, Labour and Welfare website allows reuse and modification with attribution (公共データ利用規約 第1.0版, https://www.mhlw.go.jp/chosakuken/index.html). jpomop does not copy the text of the specification. It records field names, lengths, types and page numbers only.

The PDF itself is not committed.

## Code masters (not redistributed)

基本マスター from 医療情報基盤・診療報酬審査支払機構: https://www.hpdx.or.jp/seikyushiharai/tensuhyo/kihonmasta/index.html

The site terms (https://www.hpdx.or.jp/riyo.html) prohibit reproduction without permission, so the masters are never committed. Users download them and build the vocabulary locally.

Drug master layout: receipt code in field 3 and NHI price listing code (薬価基準収載医薬品コード) in field 32, checked against `y_ALL20261001.csv` (42 fields per row).

## Third-party mapping tables (not redistributed)

| Table | Licence | Where | Used for |
|---|---|---|---|
| Kimura E. et al. A dataset for mapping the Japanese drugs to RxNorm standard concepts. Data in Brief, 2025. doi:10.1016/j.dib.2025.111418 | CC BY 4.0 | https://doi.org/10.17632/y3756v8237.1 | NHI price listing code (`NHIDPLC`) to OMOP concept (`OSV_ID`) |
| OMOP Standardized Vocabularies (ICD10, SNOMED, RxNorm, RxNorm Extension) | per vocabulary, see Athena | https://athena.ohdsi.org | ICD-10 to SNOMED (`Maps to`) |

Users download both themselves; `jpomop vocab build` joins them locally.
