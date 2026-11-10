# tracks/

| 폴더 | 트랙 | 예측 대상 | 가중치 | 은행 |
|:--|:--|:--|:--|:--|
| `short/` | 10일 예측 | 기준일 다음 날부터 10일 일별 가격 × 5품목 | 6.0MB | `b1_coint` · `et` · `et_hg_e20_x3` · `et_hg_x3` · `et_mf3` · `pooled_mw` (A/B) |
| `long1/` | 2순 후 | 기준일이 속한 순으로부터 두 번째 다음 순 평균 | 1.5MB | `et` · `et_mf3_e20_wx` · `pooled_mw` (A/B) |
| `long2/` | 3순 후 | 세 번째 다음 순 평균 | 1.5MB | `et_clip` · `et_mf3_e20_wx` · `pooled_mw` (A/B) |

각 폴더의 파일은 제출한 `model.zip`의 같은 이름 파일과 바이트 단위로 같습니다(`python scripts/check_hashes.py`).

- `config.json` — 학습 설정(`bank_variants`, `gbm_params`)과 예측 규칙(`rules`, `holiday_short`, `holiday_block`). `package_track`이 트랙을 지정합니다.
- `weights.joblib` — `train.py` 출력에 `split_slim.py`를 적용해 이 트랙이 읽는 은행만 남긴 가중치.
- `reproducibility.json` — 파일 해시, 실행 환경, 12개 사례별 가중치 컷오프, 원본 추론·재학습 확인 결과.
- `PACKAGE_README.md` · `PACKAGE_REPRODUCE.md` — 제출 패키지의 원래 안내문.
