## 🏪 다이소 상권 분석 프로젝트 (Daiso Research)

이 프로젝트는 **중소기업벤처부 리서치**를 위해 개발된 Django 기반 데이터 수집 서비스입니다.
카카오맵 API를 활용하여 다이소 지점 주변(반경 1km~5km)의 경쟁 매장(카페, 편의점 등) 데이터를 수집하고 분석합니다.

---

### 개발 환경 (Tech Stack)

* **Language:** Python 3.10+
* **Framework:** Django
* **API:** Kakao Maps REST API
* **Data Processing:** Pandas, OpenPyXL

---

### 환경 설정

### 1. 저장소 클론
git clone [Repository URL]

### 2. 가상환경 생성 및 패키지 설치
```
- python -m venv venv

- venv\scripts\activate

- pip install -r requirements.txt

- py manage.py migrate

- py manage.py createsuperuser

- py manage.py runserver
```
### 3. (중요) 환경변수 설정 **(.env 파일 생성)**
### KAKAO_API_KEY=your_kakao_rest_api_key

Kakao API Key 입력 위치
현재 코드는 보안을 위해 API 키를 소스 코드에 직접 적지 않고, 환경 변수(.env) 파일을 통해 불러오도록 작성되어 있습니다

**설정 방법:**

- .env 파일 생성: 프로젝트의 최상위 폴더에 .env라는 이름의 파일을 생성

`KAKAO_API_KEY=발급받은_카카오_REST_API_키_여기에_입력`
`KAKAO_JS_KEY=발급받은_카카오_JS_키_여기에_입력`

---
### 혹시라도 db폴더 꼬였다면 <sqlite3 삭제후 다시만들기>
> db.sqlite3 파일 삭제

> migrations/ 폴더 안으로 > 0001_initial.py 등 숫자가 붙은 파일들을 모두 삭제
> ⚠️ 주의: _init_.py 파일과 migrations 폴더 자체는 지우면 안됨

> `python manage.py makemigrations`
> `python manage.py migrate`
> `python manage.py createsuperuser`

- **작동 원리:**

settings.py 파일의 load_dotenv(BASE_DIR / '.env') 코드가 이 파일을 읽어옵니다

그 후 os.getenv("KAKAO_API_KEY")를 통해 장고 설정으로 가져옵니다

collect_cafes.py에서는 settings.KAKAO_API_KEY를 통해 이 값을 사용하여 API를 호출합니다

### 데이터 수집 실행

- 수집 커맨드 실행 (manage.py 폴더 있는곳에서)

**`python manage.py collect_cafes`**  데이터 수집 및 저장
**`python manage.py analyze_stores`** 데이터 분석, 상권점수 산출
