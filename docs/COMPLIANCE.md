# 대회 규정 준수 근거

본선 규정의 핵심 항목마다 이 저장소에서 근거를 확인하는 방법을 정리했습니다. 판정은 운영진의 재현 검증으로 확정되며, 이 문서는 참가팀의 설명입니다.

| 규정 | 구현 | 확인 방법 |
|:--|:--|:--|
| 학습·추가 학습은 2020–2024 자료로만 | `train.py`는 `data.bundle(infer=False)`로 `training/2020-2024`만 읽고 가격 최대 날짜 ≤ 2024-12-31을 assert합니다. 은행 A/B 목표 컷오프는 2024-12-30/31입니다. | `model/train.py` · `tracks/*/reproducibility.json`의 `training.bank_cutoffs`, `cases[].weights_cutoff` |
| 추론은 각 기준일 이전 관측만 | 입력 ZIP을 사례별 폴더로 나눠 관측일 < D인 행만 저장했습니다. `predict.py`는 사례 ID와 기준일이 모두 일치하는 폴더만 읽습니다. | `data/input/*/by_case/Cxx/input-manifest.json`의 `maximum_date` · 감사 로그 `outputs/*_audit.json`의 `last_obs` |
| 기간 통계는 마지막 관측일이 D보다 앞서야 함 | 모든 창이 `[D−w, D−1]`이며 원자료를 먼저 자른 뒤 특성을 계산합니다. 운영진 순별 합계 파일은 쓰지 않습니다. | `model/harness.py`의 `Daily.last`, `Daily.mean` |
| 사례별 계수·상태 추정은 사전에 정한 절차로만 | EWMA·이동평균·변동성은 고정 계산식이고, 혼합비율·배율·감쇠 계수·명절 배율은 `config.json`에 고정되어 있습니다. 추론 중 재학습·잔차 피드백·온라인 가중 갱신은 없습니다. | `tracks/*/config.json` · `model/predict.py` |
| 정답 하드코딩 금지 | 코드와 설정에 2025 날짜별 상수나 정답값이 없습니다. 입력 ZIP에는 각 기준일 이후 가격이 없습니다. | `config.json`에 2025·2026 날짜 문자열 0건 |
| 외부자료 출처 기록 | 운영진 배포 자료 7종만 사용했습니다. 원본 메타데이터를 입력 ZIP의 `source_metadata/`에 보존했습니다. | 모델기술서·학습전략보고서의 외부자료 사용 내역 표 |
| 공휴일 달력 | 2025 공휴일은 운영진 원본 20행(SHA-256 `17c9d363…`) 그대로이며 2026년 행을 추가하지 않았습니다. | 사례별 manifest의 `calendar` 항목 |
| 네 파일·같은 판본 | 트랙마다 모델 ZIP·전체 학습 데이터 ZIP·입력 자료 ZIP·예측가격.xlsx를 같은 묶음에서 제출했습니다. | `scripts/check_hashes.py` · `predictions/` |
| 원본 추론·재학습 재현 | Linux 검증 환경에서 저장 가중치 추론과 재학습 모두 600/60/60 일치가 기록되어 있습니다. | `make predict && make verify` · `make retrain && make verify-retrained` |

## 설명 범위

- 2022–2024 전진 검증은 **고정된 최종 설정**의 성능과 배율 계산식을 확인합니다. 방법·창·혼합비율의 최초 탐색 이력을 재현하는 절차는 아닙니다([VALIDATION.md](VALIDATION.md) §5).
- 저장소에는 대회 규정 문서·양식·운영진 배포 데이터를 포함하지 않았습니다.
