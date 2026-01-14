# 공공데이터 CSV 로딩 문제 해결 및 데이터 매칭 전략

## 문제점 요약

### 문제 1: 모든 데이터가 '스킵'으로 처리됨
**원인**: CSV 파일의 헤더가 한글 컬럼명이 아닌 `Column1`, `Column2` 등으로 되어 있음

코드에서 `row.get('상권업종중분류명', '')`로 접근하지만, 실제 CSV 키는 `Column7`이므로 항상 빈 문자열 반환 → '편의점' 필터 통과 실패

**CSV 컬럼 매핑** (0-indexed):
| Index | 실제 컬럼 | 코드에서 필요한 한글명 |
|-------|----------|----------------------|
| 0 | Column1 | 상가업소번호 |
| 1 | Column2 | 상호명 |
| 6 | Column7 | 상권업종중분류명 (편의점) |
| 14 | Column15 | 시군구명 (영등포구) |
| 24 | Column25 | 지번주소 |
| 31 | Column32 | 도로명주소 |

### 문제 2: 공공데이터(504개) vs 카카오데이터(462개) 개수 차이 (42개)
**가능한 원인**:
1. 공공데이터에만 있고 카카오에 없는 편의점 (신규/누락)
2. 카카오맵에서 폐업 처리된 매장
3. 다이소 반경 탐색 범위 밖의 편의점

---

## Proposed Changes

### Component 1: Management Commands 수정

#### [MODIFY] [load_public_data.py](file:///c:/A3_radius_collector-Public/stores/management/commands/load_public_data.py)

CSV 헤더 문제 해결을 위해 인덱스 기반 접근으로 변경:
- 첫 번째 행이 'Column1', 'Column2' 패턴인지 감지
- 패턴 감지 시 표준 공공데이터 컬럼명으로 매핑
- `csv.reader` + 수동 헤더 매핑 방식으로 전환

#### [MODIFY] [compare_public_data.py](file:///c:/A3_radius_collector-Public/stores/management/commands/compare_public_data.py)

동일한 CSV 헤더 문제 해결:
- `load_closed_stores_from_csv` 함수에 동일한 컬럼 매핑 로직 적용

---

### Component 2: 문서 업데이트

#### [MODIFY] [영등포구확장(2단계)상세설명.md](file:///c:/A3_radius_collector-Public/영등포구확장(2단계)상세설명.md)

기존 2단계, 3단계 내용을 유지하고 **수정 버전** 섹션 추가:
- **2단계 수정버전**: 공공데이터와 카카오데이터 개수 불일치 해결 전략
- **3단계 수정버전**: 누락 데이터 보완 및 정확도 향상 방안

---

## Verification Plan

### Automated Test
```powershell
# 수정 후 공공데이터 로드 테스트
docker compose exec web python manage.py load_public_data --csv=public_data.csv --gu=영등포구

# 예상 결과:
# - 편의점 데이터: 504개 (기존 0개 → 504개)
# - 폐업 상태: N개
# - 스킵: 0개 또는 최소 (비편의점 업종)
```

### Manual Verification
1. 명령어 실행 후 "편의점 데이터: 504개" 출력 확인
2. 스킵 개수가 0 또는 비편의점 업종만 스킵되는지 확인
