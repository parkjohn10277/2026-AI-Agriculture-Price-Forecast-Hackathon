# 재현성

## 1. 이 저장소가 제출본과 같은지 확인

```bash
python scripts/check_hashes.py
```

```text
short   18/18 files match the submitted model.zip
long1   17/17 files match the submitted model.zip
long2   17/17 files match the submitted model.zip
```

각 트랙의 `reproducibility.json`에는 제출한 `model.zip` 안 모든 파일의 SHA-256이 들어 있습니다. 공통 코드는 `model/`에 한 번만, 트랙별 `config.json`·`weights.joblib`은 `tracks/<track>/`에 두었고, 패키지 안내문은 `PACKAGE_README.md`·`PACKAGE_REPRODUCE.md`로 이름만 바꿨습니다. `model/config.json`은 `tracks/short/config.json`과 같은 파일이며 `train.py`가 학습 설정을 읽는 위치입니다(학습 설정은 세 트랙이 같습니다).

## 2. 실행 환경

| 항목 | 값 |
|:--|:--|
| Python | CPython 3.14.8 일반 GIL 빌드 (가중치 생성 환경) |
| 패키지 | numpy 2.5.3 · pandas 3.0.6 · scikit-learn 1.9.1 · scipy 1.18.1 · joblib 1.6.0 · threadpoolctl 3.7.0 |
| 장치 | CPU만, GPU 불필요 |
| 시간 | 추론 트랙당 15–25초 · 재학습 2–4분 · 검증 재계산 약 40초 (4스레드 노트북) |
| 메모리 | 재학습 최대 RSS 약 1.3GB |
| 네트워크 | 패키지 설치 후 불필요 |

## 3. 데이터 배치

운영진 배포 데이터는 저장소에 없습니다. 제출 묶음(`v11_zero_linux/` 또는 `.zip`)에서 다음 명령으로 `data/`에 풉니다.

```bash
make data BUNDLE=/path/to/v11_zero_linux.zip
```

```text
data/
├── training/2020-2024/             # 전체 학습 데이터.zip (13개 원본 파일, 세 트랙 공통)
└── input/{short,long1,long2}/      # 트랙별 입력 자료.zip
    ├── cases.json                  #   12개 사례의 기준일과 목표 기간
    ├── input-manifest.json         #   사례 ↔ 폴더 대응, 파일별 관측 기간·해시
    ├── by_case/C01 … C12/2025/     #   관측일 < 기준일 인 행만
    └── source_metadata/            #   원본 README·DATA_DICTIONARY·TRAINING_MANIFEST
```

스크립트는 제출 코드를 고치지 않고 환경변수 `NONGNET_DATA_ROOT`, `NONGNET_TRAIN_DIR`로 `data/`를 가리킵니다([scripts/env.sh](../scripts/env.sh)).

## 4. 확인 결과

| 환경 | 저장 가중치 추론 | 처음부터 재학습 | 출처 |
|:--|:--|:--|:--|
| Linux x86_64 · Ubuntu 24.04.4(WSL2) · Intel Core Ultra 7 265KF · CPython 3.14.8 | 600/60/60 일치 | 600/60/60 일치, 반복 학습 시 가중치 바이트 동일 | `reproducibility.json` → `observed_verification` |
| macOS 13 · Apple Silicon · Python 3.12 · 같은 패키지 버전 | 600/60/60 일치, CSV 해시 일치 | short 600/600 · long1 49/60(배추 최대 1.06%) · long2 47/60(배추 1.27%, 무 0.10%) | 이 저장소 구조로 `make predict`·`make retrain` 실행 (2026-11-10) |

## 5. 플랫폼 차이의 원인

- 차이는 **재학습에서만** 생깁니다. 같은 가중치로 추론하면 어느 환경에서든 값이 같습니다.
- 차이는 주로 장기 트랙 배추에서 나타납니다. 배추 규칙이 쓰는 HistGradientBoosting 은행(`pooled_mw`)은 특성을 히스토그램 구간으로 나누는데, 특성값의 부동소수점 차이(약 1e-16)가 구간 경계를 넘으면 분할이 달라집니다.
- 같은 OS·CPU·패키지에서는 `random_state=0`으로 재학습 가중치가 바이트 단위로 같습니다. 스레드 수는 추론 결과에 영향을 주지 않았습니다.
- 그래서 가중치는 운영진 검증 환경과 같은 Linux x86_64에서 학습했고, 이 차이를 제출 문서(`PACKAGE_REPRODUCE.md`)에 미리 적었습니다.
