# 모델 상세

`hackathon-ensemble-v11-zero` · 세 트랙(10일 예측 `short`, 2순 후 `long1`, 3순 후 `long2`)이 같은 코드와 학습 설정을 공유하고, 트랙별로 읽는 가중치 은행과 `rules`만 다릅니다.

## 1. 목표 변수

기준일 D 직전 마지막 관측 가격을 `L`이라 할 때 기본 목표는 다음과 같습니다.

```
y      = log(Y / L)                 # Y: 10일 예측은 D+h 일별 가격, 장기는 해당 순의 관측 가격 평균
target = y − base                   # base: EWMA 로그 비율 e20 또는 e50 (평활계수 0.20 / 0.50)
price  = L × exp(clip(plog, −log 4, +log 4)) × shrink
```

- 수준 대신 **변화율**을 배우므로 배추 1만 원대와 양파 1천 원대 가격을 한 모델에서 다룰 수 있습니다.
- 다섯 품목을 함께 학습하고 품목 더미(`is_cabbage` 등)를 특성으로 넣습니다.
- 10일 트랙의 `y3`는 목표일 ±1일 평균이며, 이 목표를 쓰는 은행은 학습 컷오프에서 하루를 더 제외합니다.

## 2. 학습 기준일과 은행

| 항목 | 값 |
|:--|:--|
| 학습 기준일 | 2020-07-01 ~ 2024-12-30 매일 (유효 입력·정답이 있는 행만) |
| 은행 A | 목표 종료일 ≤ 2024-12-30 → 기준일 2024-12-31(C01)에 사용 |
| 은행 B | 목표 종료일 ≤ 2024-12-31 → 2025년 기준일(C02–C12)에 사용 |
| 학습 데이터 | `training/2020-2024`만. `train.py`가 가격 최대 날짜 ≤ 2024-12-31을 assert |
| 시드 | 모든 추정기 `random_state=0`, ExtraTrees `n_jobs=4` |

`train.py`는 `config.json`의 모든 은행 변형을 학습하고, `split_slim.py`가 트랙 규칙이 실제로 읽는 은행만 남겨 제출 가중치를 만듭니다(예측값 불변).

## 3. 은행 변형 (제출 규칙이 사용하는 것)

| 변형 | 종류 | 핵심 설정 | 사용 트랙 |
|:--|:--|:--|:--|
| `et` | ExtraTrees | max_features 0.5 · min_samples_leaf 30(short)/15(long) · n_estimators 15/25 · base e50 | short, long1 |
| `et_mf3` | ExtraTrees | max_features 0.3, 나머지 `et`와 같음 | short |
| `et_hg_x3` | ExtraTrees | 예측 거리 [1–3]·[4–6]·[7–10]별 분리 학습 · 특성 집합 `x3` | short |
| `et_hg_e20_x3` | ExtraTrees | `et_hg_x3` + base e20 | short |
| `b1_coint` | ExtraTrees | 10일 블록 평균 목표 · 공적분형 교차 품목 특성 · 15그루 · max_features 0.3 · base e20 | short |
| `pooled_mw` | HistGradientBoosting | absolute_error · lr 0.03 · max_iter 300 · 15 leaves · L2 2.0 · min_samples_leaf 100/60 · **sample_weight = exp(−y) = L/Y** | short, long1, long2 |
| `et_mf3_e20_wx` | ExtraTrees | max_features 0.3 · base e20 · 산지 권역 기상 특성(`wxcr_nov2`) · min_samples_leaf 15 · 25그루 | long1, long2 |
| `et_clip` | ExtraTrees | 원 로그 목표를 [−0.6, +0.8]로 자른 뒤 기준 수준 차감 | long2 |

- `pooled_mw`의 가중치는 MAPE가 실제값의 역수로 가중한 절대오차라는 점에서 착안했지만, 손실을 로그 공간에서 계산하므로 MAPE를 직접 최소화하는 것은 아닌 대리 목적함수입니다.
- ExtraTrees 앞에는 학습 행으로 적합한 `SimpleImputer(strategy="median")`가 있고 HGB는 결측을 자체 처리합니다. 학습 유효값이 2개 미만인 열은 0으로 바꾸고 같은 목록을 추론에도 적용합니다.
- 전체 변형 목록과 정확한 값은 [`tracks/short/config.json`](../tracks/short/config.json)의 `bank_variants`·`gbm_params`에 있습니다.

## 4. 규칙 적용 순서 (`predict.py`)

1. 은행별 로그 예측에 기준 수준을 더해 후보 `cands[name]`을 만듭니다. `+block`, `+ewma50`, `+ewma+seas`는 블록 평균·EWMA·과거 계절 변화 앵커와의 50:50 로그 혼합입니다.
2. `A|B|…` 규칙은 항들의 **로그 공간 동일 가중 평균**입니다. 같은 항이 두 번 나오면 비중도 두 배입니다.
3. `h1last_*`는 예측 거리 h=1에서 마지막 가격을 그대로 쓰고, 이후 거리는 해당 은행을 씁니다. 배율은 h=1에도 곱해지므로 10일 양파의 h=1 예측은 `1.0086 × L`입니다.
4. 로그 예측을 ±log 4로 자르고 `L × exp(·) × shrink`로 가격을 만듭니다.
5. `state_space`(10일 배추·무): `plog −= λ · vol30² · h/10` 감쇠 후, 가격 공간에서 앵커 후보 쪽으로 `w_h = w_max · h/10` 보간합니다. 학습된 칼만 필터가 아닌 고정 규칙입니다.
6. `volshrink`(2순 양파): `plog −= c · vol30² · h`.
7. 명절 배율을 곱하고 소수점 4자리로 반올림합니다.

## 5. 명절 보정

`public_holidays.csv`의 설날·추석 날짜에 인접 공휴일과 일요일을 이어 붙여 **휴장 구간**을 만들고, 그 경계에서 오프셋을 셉니다.

| 트랙 | 규칙 | 배율 | 계산식 |
|:--|:--|:--:|:--|
| short | 설날 휴장 종료 후 +1 ~ +5일 배추 | 1.1365 | round(exp(0.75 × 평균 로그 잔차), 4) |
| short | 추석 휴장 시작 −1일 배추 | 1.2276 | 〃 |
| short | 추석 휴장 시작 −3일, −1일 무 | 1.0985 | 〃 |
| long1 | 설날 첫 공휴일이 속한 순과 다음 두 순의 무 | 1.1159 | round(exp(0.50 × 평균 로그 잔차), 4) |

평균 로그 잔차는 2022·2023·2024 폴드 각각의 명절 구간 평균을 다시 평균한 값입니다. `holiday_guard`는 비활성(`{}`)입니다.

## 6. 품목·트랙별 최종 규칙

| 품목 | short | long1 | long2 |
|:--|:--|:--|:--|
| 배추 | `et`, shrink 1.0, state_space(λ 0.1, 앵커 `ewma50+0.5seas`, w_max 0.25) | `pooled_mw+ewma+seas`, 0.9442 | `pooled_mw+ewma+seas`, 0.9261 |
| 무 | `et+block｜et_mf3+block｜et_hg_x3+block｜pooled_mw+block｜b1_coint｜b1_coint`, 0.9813, state_space(λ 0.75, 앵커 `block`, w_max 0.25) | `et_mf3_e20_wx`, 0.9553 | `et_mf3_e20_wx+ewma50`, 0.9387 |
| 양파 | `h1last_et_hg_e20_x3`, 1.0086 | `et｜et+block｜et+ewma+seas`, 0.9827, volshrink 0.25 | `et_clip`, 0.9773 |
| 깐마늘 | `last` | `last` | `last` |
| 건고추 | `last` | `last` | `last` |

## 7. 특성 경계

모든 특성은 `harness.Daily.last(D)`(D 직전 마지막 관측)와 `[D−w, D−1]` 창으로 계산합니다. 전년 동기 특성도 D−365를 기준으로 같은 규칙을 따릅니다. 추론에서는 사례별 폴더에 D 이전 행만 있으므로, 코드가 잘못되더라도 D 이후 관측을 읽을 수 없습니다.

장기 은행의 기울기 특성(`slope14`, `slope30`)은 제출 가중치를 재현하기 위해 `train.LongTrainingFeatureBuilder`에서 중심화 `np.polyfit`으로 계산하고, 단기 학습과 모든 추론은 `harness.py`의 안정화 OLS로 계산합니다. 수학적으로 같은 기울기지만 부동소수점 차이가 트리 분할에 영향을 줄 수 있어 두 경로를 구분합니다.
