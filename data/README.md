# data/

이 폴더는 비어 있으며 git에서 제외됩니다. 대회 운영진(aT · 상상력집단)이 본선 참가팀에 배포한 자료는 재배포하지 않습니다.

본선 제출 묶음 `v11_zero_linux`(트랙별 `전체 학습 데이터.zip`, `입력 자료.zip`)를 가지고 있다면 다음 명령으로 배치합니다.

```bash
make data BUNDLE=/path/to/v11_zero_linux.zip   # 또는 압축을 푼 폴더 경로
```

| 경로 | 내용 | 원본 |
|:--|:--|:--|
| `training/2020-2024/` | 가격·물량·기상·공휴일·시장별 경락정보 2020–2024 (13개 파일) | `전체 학습 데이터.zip` |
| `input/short/` · `input/long1/` · `input/long2/` | 12개 사례별 2025 입력(관측일 < 기준일), `cases.json`, manifest | 트랙별 `입력 자료.zip` |

파일 목록과 SHA-256은 `training/manifest.json`, `input/*/input-manifest.json`, 그리고 [`tracks/*/reproducibility.json`](../tracks/short/reproducibility.json)에 기록되어 있습니다.
