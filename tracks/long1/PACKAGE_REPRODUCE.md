# 실행과 재현

세 ZIP을 각각 model/, training/, input/에 풀고 같은 상위 폴더에 둡니다. CPython 3.14.8 일반 GIL 빌드와 requirements.txt의 패키지를 사용합니다. GPU와 네트워크는 필요하지 않습니다.

```sh
python -m pip install -r model/requirements.txt
python model/script.py --output reproduced.csv
python model/train.py --out retrained.joblib
python model/predict.py --track long1 --weights retrained.joblib --output retrained.csv
python model/split_slim.py retrained.joblib model/config.json long1 regenerated_weights.joblib
python model/validate_2020_2024.py
```

script.py의 기본 트랙은 long1입니다. 모든 사례·기준일·목표 기간은 input/cases.json에서 읽습니다. input/input-manifest.json이 사례별 입력 폴더와 기준일을 연결하며 predict.py는 해당 사례의 관측만 읽습니다. 새 기준일에는 그 기준일에 맞는 입력 자료와 사례 정의를 제공해야 합니다. 기존 input/<year>/ 구조도 지원합니다.

train.py는 전체 2020–2024 자료에서 세 트랙의 은행을 학습합니다. split_slim.py는 해당 트랙에서 사용하는 은행만 남깁니다. 예측 규칙은 디스크 config.json에서 읽습니다. 저장된 장기 트랙 은행을 재현하기 위해 train.LongTrainingFeatureBuilder는 중심화한 np.polyfit으로 기울기를 계산합니다. 단기 트랙 학습과 제출 추론은 harness.py의 안정화한 OLS 계산을 유지합니다. 수학적으로 같은 기울기라도 부동소수점 차이가 트리의 구간 분할을 바꿀 수 있어 두 경로를 구분합니다.

reproducibility.json에는 파일 해시, 실행 환경과 재현 확인 결과가 있습니다. validation_2020_2024.json의 수치는 validate_2020_2024.py로 다시 계산할 수 있습니다. 이 명령은 고정 설정을 검증하며 후보 탐색이나 선택 이력을 생성하지 않습니다.

2026-11-08 Linux 확인(네이티브 Linux x86_64(Ubuntu 24.04.4, WSL2, Intel Core Ultra 7 265KF), CPython 3.14.8 일반 GIL 빌드, requirements.txt 지정 패키지, 네트워크 차단, 스레드 4): 이 패키지의 세 ZIP을 새 폴더에 풀어 실행한 저장 모델의 60개 예측과, 같은 환경에서 train.py로 새로 학습한 모델의 60개 예측을 제출 예측가격.xlsx의 저장 값과 소수점 4자리 문자열 그대로 비교했으며 결과는 reproducibility.json의 observed_verification에 있습니다. 같은 Linux 환경에서 재학습을 반복하면 바이트 단위로 같은 가중치가 생성되었습니다. macOS·Windows에서의 재학습은 이 후보에 대해 확인하지 않았습니다. HistGradientBoosting 은행은 특징값의 부동소수점 차이(약 1e-16)로 구간 분할이 달라질 수 있어, 다른 플랫폼에서 재학습하면 일부 예측이 달라질 수 있습니다.
