# 🏪 Radius Collector: 편의점 폐업 검증 시스템

> **"API 한계를 넘어, 신뢰할 수 있는 상권 데이터를 만들다"**  
> 카카오맵 데이터의 정확성을 공공데이터와 교차 검증하여 폐업 매장을 자동 탐지하는 시스템

![Map Result](images/스크린샷%202026-01-25%20165604.png)

**프로젝트 기간**: 2025.11 ~ 2026.02

**참여 인원**: 2인 (김동현, 전대원)

---

## 📌 프로젝트 개요

### 문제 인식
카카오맵에 등록된 편의점들이 실제로 영업 중인지 확인할 방법이 없음

### 해결 방안
3가지 공공데이터(휴게음식점 인허가, 담배소매업 인허가, 소상공인 상권정보)와 **교차 검증**하여 폐업 추정 매장 자동 탐지

### 핵심 성과
| 항목 | 수치 |
|------|------|
| 카카오맵 편의점 | 463개 |
| 공공데이터 확인 (정상) | 452개 (97.6%) |
| **폐업 추정** | **11개 (2.4%)** |

### 비즈니스 임팩트
- **상권 분석 신뢰도 향상**: 카카오맵 단독 사용 대비 2.4%의 잘못된 데이터 의존 리스크 제거
- **프랜차이즈 입점 분석**: 폐업 매장 오판으로 인한 경쟁사 분석 오류 방지
- **부동산 투자 의사결정**: 실제 영업 중인 점포 기반 상권 활성도 평가 가능

---

## 🛠️ 기술 스택 & 아키텍처

| 분류 | 기술 |
|------|------|
| **Backend** | Django 5.2, Python 3.x |
| **Database** | PostgreSQL + PostGIS (공간 쿼리), SQLite (개발용) |
| **Infra** | Docker Compose |
| **API** | Kakao Local API, 서울시 OpenAPI, 다이소 내부 API |
| **Frontend** | Kakao Maps JS API |
| **Async (확장)** | aiohttp, asyncio |
| **Testing** | pytest, pytest-django |

### 시스템 아키텍처

**왜 다이소를 기준점으로?**
- 서울 전역 **균일한 분포** (260+개 지점) → 상권 커버리지 극대화
- 다이소 반경 1~2km에 **편의점 밀집도 높음** → 상권 활성도 proxy로 적합
- 공식 API 미제공 → **리버스 엔지니어링 경험** 획득

```
[1단계: 데이터 수집]
┌─────────────────┐     ┌──────────────────────┐
│ 다이소 공식 API  │────▶│ YeongdeungpoDaiso    │ 16개
│ + 카카오 API    │     │ (좌표 보완)           │
└─────────────────┘     └──────────┬───────────┘
                                   │ 기준점
                                   ▼
┌─────────────────┐     ┌──────────────────────┐
│ 카카오 API      │────▶│ YeongdeungpoConvenience│ 463개
│ (4분면 검색)    │     │                       │
└─────────────────┘     └──────────┬────────────┘
                                   │
[2단계: 교차 검증]                  ▼
┌─────────────────────────────────────────────────┐
│ 공공데이터 3종                                   │
│ ├─ 휴게음식점 인허가 (OpenAPI) - 310개 편의점    │
│ ├─ 담배소매업 인허가 (OpenAPI) - 1,034개         │
│ └─ 소상공인 상권정보 (CSV) - 504개(영등포구 한정) │
└────────────────────────┬────────────────────────┘
                         │ OR 조건 매칭
                         │ (이름/주소/좌표)
                         ▼
[3단계: 결과]    ┌──────────────────────┐
                │ StoreClosureResult(DB)│
                │ 정상: 452 / 폐업: 11  │
                └──────────┬───────────┘
                           ▼
                    [카카오 지도 시각화 & 수집기]           http://localhost:8000/
                    [개발자 모니터링 대시보드]     http://localhost:8000/dev/monitor/
```

### 프로젝트 구조

```
├── stores/
│   ├── management/commands/        # 데이터 수집 파이프라인
│   │   ├── run_all.py              # 🔥 전체 파이프라인 실행 (1개 명령어로 5단계 실행)
│   │   ├── v2_3_1_collect_yeongdeungpo_daiso.py  # 1단계: 다이소 수집
│   │   ├── v2_3_2_collect_Convenience_Only.py    # 2단계: 편의점 수집 (4분면 분할)
│   │   ├── openapi_1.py            # 3단계: 휴게음식점 인허가
│   │   ├── openapi_2.py            # 4단계: 담배소매업 인허가
│   │   ├── check_store_closure.py  # 5단계: 폐업 판별
│   │   ├── async_collector.py      # 비동기 수집기 (확장)
│   │   └── gu_codes.py             # 서울 25개 구 코드 매핑
│   ├── templates/
│   │   ├── collector.html          # 웹 UI 수집기
│   │   ├── store_closure_map.html  # 카카오맵 결과 시각화
│   │   └── dev_monitor.html        # 개발자 모니터링 대시보드
│   ├── models.py                   # 7개 DB 모델 정의
│   ├── views.py                    # API 엔드포인트 (739 라인)
│   ├── test_core.py                # 핵심 테스트 (1,256 라인)
│   └── test_unit.py                # 단위 테스트
├── config/                         # Django 설정
│   ├── settings.py
│   └── urls.py
├── public_data.csv                 # 소상공인 상권정보 (영등포구 한정)
├── boundary_viewer.html            # 🗺️ 구 경계 및 커버리지 시각화 검증 도구
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 🔥 핵심 트러블슈팅

### 1. API 45개 제한 돌파 — 4분면 분할 검색 ⭐⭐⭐

**문제**: 카카오 API는 반경 검색 시 최대 45개(15개×3페이지)만 반환

**분석**:
```
요청: 반경 2km 내 편의점 검색
결과: 45개 (최대치)
실제: 약 150개 존재 → 105개 누락!
```

**해결**: 다이소 중심점 기준 4분면(1.8km 사각형) 분할 검색
```
기존: 중심점 기준 반경 r 원형 검색
     ┌─────────────────┐
     │        ●        │  ← 45개만 수집
     │     반경 2km    │
     └─────────────────┘

개선: 4개의 1km×1km 사각형으로 분할
     ┌────────┬────────┐
     │   Q2   │   Q1   │  ← 각 45개씩
     │  ●     │     ●  │  = 180개 수집 가능
     ├────────┼────────┤
     │   Q3   │   Q4   │
     │  ●     │     ●  │
     └────────┴────────┘
```

**결과**: 16개 다이소 × 4분면 = 영등포구 전체 463개 편의점 수집 (100% 커버리지)

---

### 2. 신규 매장 누락 — 다이소 공식 API 리버스 엔지니어링 ⭐⭐⭐

**문제**: 카카오 API에서 신규 오픈 매장(다이소 신길점) 검색 불가

**해결 과정**:
| 단계 | 작업 | 결과 |
|------|------|------|
| 1 | 다이소몰 매장찾기 페이지 접속 | `daisomall.co.kr/store` |
| 2 | 개발자도구(F12) → Network 탭 | 서버 요청 트리거 모니터링 |
| 3 | 검색 액션 시 트래픽 캡처 | JSON 응답 포함된 요청 식별 |
| 4 | 패킷 분석 | Endpoint, Method, Content-Type 명세 확보 |
| 5 | 필수 헤더/페이로드 식별 | `Referer`, `Origin`, `keyword` 필드 확인 |

```python
# 최종 추출된 API 스펙
url = "https://fapi.daisomall.co.kr/ms/msg/selStr"
headers = {
    "Content-Type": "application/json",
    "Referer": "https://www.daisomall.co.kr/",
    "Origin": "https://www.daisomall.co.kr"
}
payload = {"keyword": "영등포", "pageSize": 100}
# 결과: 신길점 포함 16개 매장 전수 확보
```

---

### 3. 좌표계 불일치 — EPSG 변환 ⭐⭐

**문제**: 서울시 OpenAPI(TM좌표 EPSG:5174) ≠ 카카오(WGS84 EPSG:4326)

**해결**: `pyproj` 라이브러리로 좌표 변환
```python
from pyproj import Proj, transform

proj_tm = Proj(init='epsg:5174')
proj_wgs = Proj(init='epsg:4326')

def tm_to_wgs(x, y):
    lng, lat = transform(proj_tm, proj_wgs, x, y)
    return round(lat, 4), round(lng, 4)  # 소수점 4자리 = 오차 ~7m
```

---

### 4. 전체 레코드 로드 문제 → 필요 필드만 조회 ⭐⭐

**문제**: 폐업 결과 조회 시 응답 지연 **서울시의 모든 데이터를 띄울때** (3초 이상)

**해결**:
```python
# Before: 전체 레코드 + 모든 필드 로드 후 Python에서 처리
all_results = list(StoreClosureResult.objects.all())  # 모든 필드 로드
stores_list = []
for result in all_results:
    stores_list.append({
        'name': result.name,
        'lat': result.latitude,
        # ... 필요한 필드만 사용하지만 전체 로드됨
    })

# After: DB에서 필요한 필드만 조회 (values())
results = StoreClosureResult.objects.values('name', 'address', 'latitude', 'longitude', 'gu')
# SQL: SELECT name, address, latitude, longitude, gu FROM store_closure_result
```

**결과**: 전송 데이터 양 감소, 응답 시간 3초 → 0.1초 (97% 개선)

---

### 5. Race Condition 방지 ⭐⭐⭐

**문제**: (비동기상황) 확장 대비 & 동시 수집 요청 시 `IntegrityError` 발생

**해결**: `select_for_update()` 트랜잭션 락 사용
```python
from django.db import transaction

with transaction.atomic():
    store, created = YeongdeungpoConvenience.objects.select_for_update().update_or_create(
        place_id=place_id,
        defaults={...}
    )
```

### 6. 지리적 변수 통제 — 산과 강이 만드는 커버리지 왜곡 (데이터 분석) ⭐⭐

**문제**: 강북구(60.7%), 관악구(67.1%) 등 특정 지역의 커버리지가 합격 기준(70%)보다 현저히 낮음.

**분석 (with `boundary_viewer.html`)**:
코드의 오류인지 확인하기 위해 **검증용 시각화 도구**(`boundary_viewer.html`)를 급히 제작하여 눈으로 확인했습니다.
- **발견**: 커버리지가 낮은 구들은 공통적으로 **북한산(강북/도봉), 관악산(관악), 한강(강서/마포)** 등 편의점이 입점할 수 없는 지형이 전체 면적의 상당수를 차지했습니다.
- **한계**: 산과 강의 좌표를 자동으로 발라내려면 지적도 API나 고도 데이터가 필요하여 프로젝트 범위를 벗어남.

**해결 (Rule-based 최적화)**:
기계적인 "전체 평균" 대신 **"상위 10개 구(평지 위주)"의 평균인 1.8km**를 기준값으로 채택했습니다.
> "모든 케이스를 코드로 해결하려 들지 말고, **데이터의 특성(Domain Knowledge)**을 이해하여 통계적 기준을 조정하는 것이 더 효율적이다."

---

## 📊 추가 트러블슈팅 요약

| # | 문제 | 원인 | 해결책 | 난이도 |
|---|------|------|--------|--------|
| 7 | Rate Limit 초과 | 연속 호출 | 지수 백오프 재시도 | ⭐⭐ |
| 8 | 데이터 중복 | 4분면 경계 중복 | 좌표 기반 dedupe | ⭐ |
| 9 | 메모리 누수 | 대용량 로드 | iterator + gc | ⭐⭐ |
| 10 | 타임존 오류 | UTC 기본값 | Asia/Seoul 설정 | ⭐ |
| 11 | 정적 파일 404 | collectstatic 미실행 | whitenoise | ⭐ |
| 12 | CSV 정합성 | 정적 데이터 | OpenAPI 병행 검증 | ⭐⭐ |
| 13 | 중구 다이소 문제 | 구 코드 특수케이스 | gu_codes.py 수정 | ⭐ |

> 상세 기록: [트러블슈팅_기록.md](트러블슈팅_기록.md)

---

## 🚀 실행 가이드

### 환경 설정

```bash
# 1. 환경변수 설정 (.env)
KAKAO_API_KEY=your_kakao_rest_api_key
KAKAO_JS_KEY=your_kakao_js_key
SEOUL_OPENAPI_KEY=your_seoul_openapi_key

# 2. Docker 실행
docker compose up -d
docker compose exec web python manage.py migrate
```

### 웹 UI (수집기) - 메인 페이지

![Collector UI](images/스크린샷%202026-01-25%20165531.png)

```
http://localhost:8000/
```

**collector.html** (750줄) - 편의점 폐업 검증 시스템 메인 UI

| 기능 | 설명 |
|------|------|
| API 키 입력 | 카카오 REST, 카카오 JS, 서울시 OpenAPI 키 입력 |
| API 키 자동 저장 | `localStorage`에 키 저장, 새로고침 후에도 유지 |
| 구 선택 | 서울 25개 구 드롭다운 선택 (기본: 영등포구) |
| 실시간 진행률 | 프로그레스 바 + 단계별 메시지 표시 |
| 결과 시각화 | 카카오맵에 정상(🔵)/폐업(🔴) 마커 실시간 표시 |
| 인포윈도우 | 마커 클릭 시 매장명, 주소, 상태 표시 |
| 중복 실행 방지 | 수집 중 버튼 비활성화 |

**지도 기능:**
- 수집 완료 시 자동으로 결과 범위에 맞게 지도 줌
- 줌 컨트롤 제공
- 정상 매장: 파란색 마커 / 폐업 추정: 빨간색 마커

### 수집 데이터 뷰어

```
http://localhost:8000/store-closure/
```

**store_closure_map.html** (540줄) - 수집된 전체 데이터 조회 UI

| 기능 | 설명 |
|------|------|
| 전체 통계 | 총 데이터, 정상 영업, 폐업 추정 개수 표시 |
| 상태별 필터 | 정상/폐업 버튼으로 필터링 |
| 지역별 필터 | 구별 데이터 필터링 (동적 생성) |
| 전체 데이터 보기 | 모든 필터 해제 |
| 활성 필터 표시 | 현재 적용된 필터 시각적 표시 |

**인포윈도우 정보:**
- 매장명, 주소
- 상태 (정상 영업 / 폐업 추정)
- 매칭 이유 (이름/주소/좌표)

### 개발자 모니터링 대시보드

![Developer Dashboard](images/스크린샷%202026-01-25%20161650.png)

```
http://localhost:8000/dev/monitor/
```

**dev_monitor.html** (938줄) - 개발자용 상세 모니터링 UI

| 섹션 | 표시 내용 |
|------|----------|
| **실시간 모니터링** | 경과 시간, API 호출 수, 수집 데이터 수, 진행률 |
| **5단계 진행 현황** | 각 단계별 상태(대기/실행/완료), 수집 건수, 소요시간, API 호출 수 |
| **4분면 시각화** | 다이소 기준점 + 4분면 검색 영역 지도 표시 |
| **교차 검증 결과** | 정상/폐업 수, 이름/주소/좌표 매칭 수 |
| **수집 성능** | 초당 수집 건수, 예상 완료 시간, API 에러 수 |
| **시스템 리소스** | CPU, 메모리, 디스크, 스레드 수, 네트워크 I/O |
| **실시간 로그** | 단계별 진행 로그, 복사 기능 |

**특수 기능:**
- 자동 새로고침 (1초 간격) ON/OFF
- test_core 테스트 실행 버튼 (`/dev/test/`)
- 로그 복사 기능
- 사용자 지도 조작 시 자동 줌 비활성화

### CLI 명령어

```bash
# 🔥 전체 파이프라인 한 번에 실행 (권장)
docker compose exec web python manage.py run_all --gu 영등포구

# 개별 단계 실행
docker compose exec web python manage.py v2_3_1_collect_yeongdeungpo_daiso --gu 영등포구
docker compose exec web python manage.py v2_3_2_collect_Convenience_Only --gu 영등포구
docker compose exec web python manage.py openapi_1 --gu 영등포구
docker compose exec web python manage.py openapi_2 --gu 영등포구
docker compose exec web python manage.py check_store_closure --gu 영등포구

# 결과 확인
# http://127.0.0.1:8000/store-closure/
```

### 테스트 실행

```bash
# 핵심 테스트 (1,256 라인)
docker compose exec web python manage.py test stores.test_core -v 2

# 스트리밍 테스트 UI
# http://localhost:8000/dev/test/

# 테스트 항목:
# 1. ScalabilityTests - 서울 25개 구 경계선 & 최적 반경 테스트
# 2. EndToEndIntegrationTests - 전체 파이프라인 시뮬레이션
# 3. DockerReproducibilityTests - Docker 환경 재현성 검증
```

---

## ⚡ 성능 지표

| 항목 | 수치 | 비고 |
|------|------|------|
| 대량 데이터 생성 | 1,000개 / 0.8초 | Bulk Create 최적화 |
| 공간 쿼리 속도 | 100회 / 0.05초 | PostGIS 인덱스 활용 |
| 전체 파이프라인 | 약 40~50초 / 1개 구 | 16개 다이소 × 4분면 크롤링 + 검증 |
| API 호출 | 약 200회 / 1개 구 | 4분면 분할 검색 최적화 |
| N+1 쿼리 개선 | 3초 → 0.1초 | 97% 응답 시간 단축 |

---

## 📈 버전별 개발 히스토리

### v1.0 — MVP: 데이터 수집기
- 카카오 API로 다이소 주변 상권 데이터 수집
- Rate Limit 준수 (`time.sleep(0.2)`)
- **한계**: API 45개 제한 미인지 (45개 초과해서 수집 불가🔺)

### v1.1 — 안정성 강화
- `update_or_create()` Upsert 로직 도입
- Docker/Local DB 포트 충돌 해결
- **발견**: API 45개 제한 확인

### v2.0 — PostGIS 도입
- PostgreSQL + PostGIS, GeoDjango 적용
- 웹 지도 시각화 (`/map/`)
- **한계**: 45개 제한 미해결

### v2.1 — BigQuery 실험 (실패 → 교훈)
- Google BigQuery + OSM 데이터 시도
- 서울 다이소: (카카오, 네이버)지도 250개 vs OSM지도 60개 (75% 누락)
- **교훈**: "구글의 범용성보다 데이터의 정확도가 중요하다"

### v2.3 — 최종 완성: 3중 검증 시스템 ✅
- 다이소 공식 API 리버스 엔지니어링
- 4분면 분할 검색 (Quadrant Search)
- 3중 교차 검증 (OpenAPI + CSV)
- 서울 25개 구 확장 지원
- 웹 UI 수집기 & 개발자 모니터링 대시보드
- 비동기 수집 기능 (`async_collector.py`)
- N+1 쿼리 최적화, 시스템 리소스 모니터링

---

## ⚠️ 프로젝트 한계점 및 향후 계획

### Critical (프로덕션 배포 시 필수)
- 환경변수 분리 (SECRET_KEY, DEBUG, DB 비밀번호)
- 비동기 처리 도입 (Celery + Redis)

### High Priority
- 25개 구 병렬 수집 지원 (현재 순차 실행 22분 소요)
- 에러 복구 로직 (체크포인트 기반 재시작)
- API 모킹 테스트 (CI/CD 파이프라인 지원)

### Medium Priority
- Service Layer 패턴 분리 (현재 Fat View 구조)
- 구조화된 로깅 (현재 stdout 출력만 사용)
- WebSocket 기반 실시간 모니터링

### 상세 분석
프로젝트 한계점에 대한 자세한 분석은 다음 문서들을 참고하세요:
- [프로젝트_한계점_분석요약.md](프로젝트_한계점_분석요약.md) - 확장성 핵심 한계점
- [비동기_확장_분석_보고서.md](비동기_확장_분석_보고서.md) - 비동기 도입 시 22분 → 2분 개선 기대

---

## 🎓 회고

1. **데이터 품질이 도구보다 중요하다**  
   구글 BigQuery(OSM지도 데이터)보다 Kakao API의 한국 내 데이터가 훨씬 정확

2. **API 한계는 알고리즘으로 극복한다**  
   45개 제한 → Divide & Conquer(4분면 분할)로 전수 조사 달성

3. **단일 소스의 한계는 교차 검증으로 보완한다**  
   API 데이터의 신뢰성을 **공공데이터 3종**으로 검증

4. **제약 사항이 창의적인 해결책을 만든다**  
   API 제한을 극복하기 위해 알고리즘적 사고를 적용하여 데이터 파이프라인의 견고함 향상

---

## 📚 관련 문서

| 문서 | 설명 |
|------|------|
| [트러블슈팅_기록.md](트러블슈팅_기록.md) | 14개 문제 해결 상세 기록 |
| [테스트_체크리스트.md](테스트_체크리스트.md) | 성능/데이터/확장성 테스트 가이드 |
| [프로젝트_한계점_분석요약.md](프로젝트_한계점_분석요약.md) | 확장성 관점 핵심 한계점 |
| [비동기_확장_분석_보고서.md](비동기_확장_분석_보고서.md) | 비동기 도입 전략 및 ROI 분석 |
| [테스트_코어_실행가이드.md](테스트_코어_실행가이드.md) | 테스트 실행 상세 가이드 |
| [최종.md](최종.md) | 이력서용 요약 |

---

## 📄 라이선스

이 프로젝트는 **MIT License**에 따라 배포됩니다.
