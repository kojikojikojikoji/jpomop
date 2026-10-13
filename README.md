# jpomop

jpomop converts Japanese DPC inpatient data to the OMOP Common Data Model v5.4.
It reads two DPC files: Form 1 (様式1) and the EF file (入院EF統合ファイル).

I wrote jpomop using the public DPC specification from the Ministry of Health, Labour and Welfare.
This repository has no hospital data or code masters.

## Status

jpomop is in early development.
It can read and check the two files and write eight CDM tables.
I tested it with synthetic data and the examples in the specification.
I have not tried it with real hospital data or measured mapping rates with a full Athena vocabulary yet.

I plan to release v0.1 at the end of November 2026.

## Try it

```sh
pip install jpomop
jpomop synth --n 100 --out synth/
jpomop validate --yoshiki1 synth/yoshiki1.txt --ef synth/ef.txt
jpomop convert --yoshiki1 synth/yoshiki1.txt --ef synth/ef.txt --out cdm.duckdb
jpomop report --cdm cdm.duckdb
```

`synth` makes fake data for 100 patients, and you can change the number with `--n`.

`validate` checks the files against the FY2026 specification and lists the problems it finds.

Without `--vocab`, the concept IDs for diagnoses and drugs are 0.
The original codes stay in the source value columns.
To map diagnoses and drugs, build a vocabulary first:

```sh
jpomop vocab build --athena athena/ --drug-master y_ALL20261001.csv \
    --kimura rxnorm_mapping.tsv --out vocab.duckdb
jpomop convert ... --vocab vocab.duckdb
```

You need the following three sources, and you must download them yourself.

- Athena vocabularies: ICD10, SNOMED, RxNorm and RxNorm Extension (https://athena.ohdsi.org)
- The drug master (医薬品マスター, `y_*.csv`) (https://www.hpdx.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_04.html)
- The drug mapping table by Kimura et al. 2025, CC BY 4.0 (https://doi.org/10.17632/y3756v8237.1)

## Walkthrough

[examples/walkthrough_en.ipynb](https://github.com/kojikojikojikoji/jpomop/blob/main/examples/walkthrough_en.ipynb) runs every step on 100 invented patients.
It shows the input files, the checks and each CDM table for one patient.
A Japanese version is in [examples/walkthrough_ja.ipynb](https://github.com/kojikojikojikoji/jpomop/blob/main/examples/walkthrough_ja.ipynb).

## How each part is converted

| DPC | CDM table | Notes |
|---|---|---|
| Form 1, one form per stay | `person`, `visit_occurrence`, `observation_period` | Patient IDs are hashed. Some form types are counted but not converted. See below. |
| EF, ward code for each day | `visit_detail` | One row for each run of days on the same ward. |
| Form 1, diagnoses (ICD-10) | `condition_occurrence` | Form 1 has no date for each diagnosis, so the start date is the admission date. Suspected diagnoses (modifier 8002) are left out and counted. |
| EF, codes that start with 6 | `drug_exposure` | Mapped through the NHI drug price code. Drugs that patients bring from home are left out. |
| EF, codes that start with 1 | `procedure_occurrence` | The concept ID is 0 for now. The DPC code stays as the source value. Room and meal charges are left out. |
| Form 1, discharge outcome 6 or 7 | `death` | The death date is the discharge date. |

Form 1 has several form types, and jpomop uses the form for the whole stay.
It uses the day-90 interim form only when the stay has no whole-stay form yet.
It counts the ward-group forms and the readmission forms, but it does not convert them.
These forms cover the same days as the whole-stay forms (specification p42 and p125).

## Code masters are not included

The code masters (基本マスター) come from 医療情報基盤・診療報酬審査支払機構.
The website terms say that its documents may not be used or copied without permission.
So this repository does not include the masters.
Please download them from https://www.hpdx.or.jp/seikyushiharai/tensuhyo/kihonmasta/index.html.

## Sources

Each field in the specification files shows the document, the version and the page.
See [PROVENANCE.md](https://github.com/kojikojikojikoji/jpomop/blob/main/PROVENANCE.md).

## Licence

The code uses the Apache-2.0 licence.
Mapping tables made by this project use CC BY 4.0. See [LICENSE-DATA](LICENSE-DATA).

---

## 日本語

厚生労働省が公開している DPC 調査の仕様（様式1・入院EF統合ファイル）だけを元に、DPC データを OMOP CDM v5.4 へ変換する Python のプログラムです。病院の実データとマスターは含みません。動作の確認には、このリポジトリで作る架空データと、仕様書の記載例だけを使っています。

読み込み・仕様の確認・8つの表への変換までできています。病院の実データでの確認と、Athena の語彙一式での変換率の測定はこれからです。

架空の患者 100 人のデータで最初から最後まで動かした例を、[examples/walkthrough_ja.ipynb](https://github.com/kojikojikojikoji/jpomop/blob/main/examples/walkthrough_ja.ipynb) に置いています。

マスターは、医療情報基盤・診療報酬審査支払機構のサイトから各自でダウンロードしてください。
