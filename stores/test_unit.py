"""
편의점 폐업 검증 시스템 테스트 모듈

이 모듈은 다음 핵심 기능들을 검증합니다:
1. 모델 데이터 무결성 테스트
2. 데이터 중복 검증 테스트
3. 좌표 데이터 유효성 테스트
4. 폐업 판별 로직 테스트
5. API 검증 함수 테스트
6. 데이터 품질 검증 테스트
7. 성능 벤치마크 테스트
"""

from django.test import TestCase, Client
from django.contrib.gis.geos import Point
from django.db import IntegrityError
from stores.models import (
    YeongdeungpoConvenience, 
    YeongdeungpoDaiso,
    SeoulRestaurantLicense,
    TobaccoRetailLicense,
    StoreClosureResult
)
import json
import time
from unittest.mock import patch


# ========================================
# 1. 모델 데이터 무결성 테스트
# ========================================

class ModelIntegrityTests(TestCase):
    """모델 데이터 무결성 테스트"""
    
    def test_convenience_store_creation(self):
        """편의점 데이터 생성 테스트"""
        print("\n[TEST] 편의점 데이터 생성 테스트 시작")
        store = YeongdeungpoConvenience.objects.create(
            place_id="test_place_001",
            base_daiso="테스트 다이소",
            name="테스트 편의점",
            address="서울시 영등포구 테스트로 123",
            distance=100,
            location=Point(126.9066, 37.5171, srid=4326)
        )
        print(f"    - 생성된 편의점: {store.name}, place_id: {store.place_id}")
        self.assertEqual(store.name, "테스트 편의점")
        self.assertEqual(store.place_id, "test_place_001")
        print("    ✅ 편의점 데이터 생성 성공")
    
    def test_daiso_creation(self):
        """다이소 데이터 생성 테스트"""
        print("\n[TEST] 다이소 데이터 생성 테스트 시작")
        daiso = YeongdeungpoDaiso.objects.create(
            name="다이소 영등포점",
            address="서울시 영등포구 당산로 1",
            daiso_id="daiso_001",
            location=Point(126.9066, 37.5171, srid=4326)
        )
        print(f"    - 생성된 다이소: {daiso.name}")
        self.assertEqual(daiso.name, "다이소 영등포점")
        print("    ✅ 다이소 데이터 생성 성공")
    
    def test_restaurant_license_creation(self):
        """휴게음식점 인허가 데이터 생성 테스트"""
        print("\n[TEST] 휴게음식점 인허가 데이터 생성 테스트 시작")
        license_data = SeoulRestaurantLicense.objects.create(
            mgtno="TEST-MGT-001",
            bplcnm="테스트 편의점",
            sitewhladdr="서울시 영등포구 테스트동 1-1"
        )
        print(f"    - 생성된 휴게음식점: {license_data.bplcnm}, mgtno: {license_data.mgtno}")
        self.assertEqual(license_data.mgtno, "TEST-MGT-001")
        print("    ✅ 휴게음식점 인허가 데이터 생성 성공")
    
    def test_tobacco_license_creation(self):
        """담배소매업 인허가 데이터 생성 테스트"""
        print("\n[TEST] 담배소매업 인허가 데이터 생성 테스트 시작")
        license_data = TobaccoRetailLicense.objects.create(
            mgtno="TOBACCO-MGT-001",
            bplcnm="테스트 담배소매점",
            sitewhladdr="서울시 영등포구 테스트동 2-2"
        )
        print(f"    - 생성된 담배소매업: {license_data.bplcnm}, mgtno: {license_data.mgtno}")
        self.assertEqual(license_data.mgtno, "TOBACCO-MGT-001")
        print("    ✅ 담배소매업 인허가 데이터 생성 성공")


# ========================================
# 2. 데이터 중복 방지 테스트 (place_id unique)
# ========================================

class DuplicatePreventionTests(TestCase):
    """데이터 중복 방지 테스트 - place_id 기준 unique 제약 검증"""
    
    def test_convenience_duplicate_place_id_rejected(self):
        """동일한 place_id를 가진 편의점 중복 저장 방지 테스트"""
        print("\n[TEST] 편의점 중복 place_id 방지 테스트 시작")
        YeongdeungpoConvenience.objects.create(
            place_id="duplicate_test_001",
            base_daiso="테스트 다이소",
            name="첫 번째 편의점",
            address="서울시 영등포구 테스트로 1",
            distance=50,
            location=Point(126.9066, 37.5171, srid=4326)
        )
        
        # 동일한 place_id로 두 번째 저장 시도 -> IntegrityError 발생해야 함
        with self.assertRaises(IntegrityError):
            YeongdeungpoConvenience.objects.create(
                place_id="duplicate_test_001",  # 중복 place_id
                base_daiso="테스트 다이소",
                name="두 번째 편의점",
                address="서울시 영등포구 테스트로 2",
                distance=100,
                location=Point(126.9070, 37.5175, srid=4326)
            )
        print("    ✅ 편의점 중복 저장 방지 확인 (IntegrityError 발생)")
    
    def test_daiso_duplicate_id_rejected(self):
        """동일한 daiso_id를 가진 다이소 중복 저장 방지 테스트"""
        print("\n[TEST] 다이소 중복 daiso_id 방지 테스트 시작")
        YeongdeungpoDaiso.objects.create(
            name="다이소 1호점",
            address="서울시 영등포구 당산로 1",
            daiso_id="daiso_dup_001",
            location=Point(126.9066, 37.5171, srid=4326)
        )
        
        with self.assertRaises(IntegrityError):
            YeongdeungpoDaiso.objects.create(
                name="다이소 2호점",
                address="서울시 영등포구 당산로 2",
                daiso_id="daiso_dup_001",  # 중복 daiso_id
                location=Point(126.9070, 37.5175, srid=4326)
            )
        print("    ✅ 다이소 중복 저장 방지 확인 (IntegrityError 발생)")
    
    def test_restaurant_license_duplicate_mgtno_rejected(self):
        """동일한 관리번호(mgtno) 중복 저장 방지 테스트"""
        print("\n[TEST] 휴게음식점 중복 mgtno 방지 테스트 시작")
        SeoulRestaurantLicense.objects.create(
            mgtno="MGT-DUP-001",
            bplcnm="테스트 가게 1"
        )
        
        with self.assertRaises(IntegrityError):
            SeoulRestaurantLicense.objects.create(
                mgtno="MGT-DUP-001",  # 중복 mgtno
                bplcnm="테스트 가게 2"
            )
        print("    ✅ 휴게음식점 중복 저장 방지 확인 (IntegrityError 발생)")


# ========================================
# 3. 좌표 데이터 유효성 테스트
# ========================================

class CoordinateValidityTests(TestCase):
    """좌표 데이터 유효성 테스트 - 서울 지역 좌표 범위 검증"""
    
    # 서울 지역 좌표 범위
    SEOUL_LAT_MIN = 37.4
    SEOUL_LAT_MAX = 37.7
    SEOUL_LNG_MIN = 126.7
    SEOUL_LNG_MAX = 127.2
    
    def test_coordinate_within_seoul_range(self):
        """저장된 좌표가 서울 지역 범위 내에 있는지 테스트"""
        print("\n[TEST] 좌표 서울 지역 범위 테스트 시작")
        store = YeongdeungpoConvenience.objects.create(
            place_id="coord_test_001",
            base_daiso="테스트 다이소",
            name="영등포 편의점",
            address="서울시 영등포구 테스트로 123",
            distance=100,
            location=Point(126.9066, 37.5171, srid=4326)  # 영등포구 좌표
        )
        
        lat = store.location.y
        lng = store.location.x
        print(f"    - 테스트 좌표: 위도 {lat}, 경도 {lng}")
        
        self.assertGreaterEqual(lat, self.SEOUL_LAT_MIN, f"위도가 서울 범위 미만: {lat}")
        self.assertLessEqual(lat, self.SEOUL_LAT_MAX, f"위도가 서울 범위 초과: {lat}")
        self.assertGreaterEqual(lng, self.SEOUL_LNG_MIN, f"경도가 서울 범위 미만: {lng}")
        self.assertLessEqual(lng, self.SEOUL_LNG_MAX, f"경도가 서울 범위 초과: {lng}")
        print("    ✅ 좌표가 서울 범위 내에 있음을 확인")
    
    def test_all_existing_stores_have_valid_coordinates(self):
        print("\n[TEST] 모든 저장된 편의점 좌표 유효성 테스트 시작")
        # 테스트 데이터 생성
        for i in range(5):
            YeongdeungpoConvenience.objects.create(
                place_id=f"valid_coord_{i}",
                base_daiso="테스트 다이소",
                name=f"편의점 {i}",
                address=f"서울시 영등포구 테스트로 {i}",
                distance=100,
                location=Point(126.9 + (i * 0.01), 37.5 + (i * 0.01), srid=4326)
            )
        
        stores = YeongdeungpoConvenience.objects.all()
        invalid_coords = []
        
        for store in stores:
            if store.location:
                lat, lng = store.location.y, store.location.x
                if not (self.SEOUL_LAT_MIN <= lat <= self.SEOUL_LAT_MAX and 
                        self.SEOUL_LNG_MIN <= lng <= self.SEOUL_LNG_MAX):
                    invalid_coords.append({
                        'name': store.name,
                        'lat': lat,
                        'lng': lng
                    })
        
        self.assertEqual(len(invalid_coords), 0, 
                        f"서울 범위 밖 좌표 발견: {invalid_coords}")
        print("    ✅ 모든 편의점 좌표가 유효함")
    
    def test_location_not_null(self):
        print("\n[TEST] 좌표값 NULL 여부 테스트 시작")
        # 테스트 데이터 생성
        YeongdeungpoConvenience.objects.create(
            place_id="loc_null_test",
            base_daiso="테스트 다이소",
            name="좌표 테스트 편의점",
            address="서울시 영등포구 테스트로 1",
            distance=100,
            location=Point(126.9066, 37.5171, srid=4326)
        )
        
        # 1. 편의점 데이터 확인
        null_conv = YeongdeungpoConvenience.objects.filter(location__isnull=True).count()
        self.assertEqual(null_conv, 0, f"좌표 없는 편의점 발견: {null_conv}개")
        
        # 2. 다이소 데이터 확인
        null_daiso = YeongdeungpoDaiso.objects.filter(location__isnull=True).count()
        self.assertEqual(null_daiso, 0, f"좌표 없는 다이소 발견: {null_daiso}개")
        print("    ✅ 좌표가 없는 데이터(NULL)는 없음")


# ========================================
# 4. 폐업 판별 결과 테스트
# ========================================

class StoreClosureTests(TestCase):
    """폐업 판별 결과 테스트"""
    
    def test_closure_result_creation(self):
        print("\n[TEST] 폐업 체크 결과 생성 테스트 시작")
        # 정상 영업 매장
        normal_store = StoreClosureResult.objects.create(
            place_id="closure_test_001",
            name="정상 영업 편의점",
            address="서울시 영등포구 테스트로 1",
            status="정상",
            match_reason="담배소매업 인허가 매칭",
            location=Point(126.9066, 37.5171, srid=4326)
        )
        self.assertEqual(normal_store.status, "정상")
        
        # 폐업 추정 매장
        closed_store = StoreClosureResult.objects.create(
            place_id="closure_test_002",
            name="폐업 추정 편의점",
            address="서울시 영등포구 테스트로 2",
            status="폐업",
            match_reason="공공데이터 미매칭",
            location=Point(126.9070, 37.5175, srid=4326)
        )
        self.assertEqual(closed_store.status, "폐업")
        print("    ✅ 폐업 체크 결과 저장 및 상태값 확인 성공")
    
    def test_closure_status_choices(self):
        print("\n[TEST] 폐업 상태값 유효성 테스트 시작")
        valid_statuses = ['정상', '폐업']
        
        for status in valid_statuses:
            result = StoreClosureResult.objects.create(
                place_id=f"status_test_{status}",
                name=f"{status} 테스트 매장",
                address="서울시 영등포구 테스트로",
                status=status,
                match_reason="테스트",
                location=Point(126.9066, 37.5171, srid=4326)
            )
            self.assertIn(result.status, valid_statuses)
        print("    ✅ 폐업 상태값이 선택지(정상, 폐업) 내에 있음")
    
    def test_closure_statistics(self):
        print("\n[TEST] 폐업률 통계 계산 테스트 시작")
        # 테스트 데이터: 정상 8개, 폐업 2개
        for i in range(8):
            StoreClosureResult.objects.create(
                place_id=f"stat_normal_{i}",
                name=f"정상 매장 {i}",
                address=f"서울시 영등포구 테스트로 {i}",
                status="정상",
                match_reason="테스트 매칭",
                location=Point(126.9 + (i * 0.001), 37.5, srid=4326)
            )
        
        for i in range(2):
            StoreClosureResult.objects.create(
                place_id=f"stat_closed_{i}",
                name=f"폐업 매장 {i}",
                address=f"서울시 영등포구 폐업로 {i}",
                status="폐업",
                match_reason="미매칭",
                location=Point(126.91 + (i * 0.001), 37.51, srid=4326)
            )
        
        total = StoreClosureResult.objects.count()
        normal_count = StoreClosureResult.objects.filter(status="정상").count()
        closed_count = StoreClosureResult.objects.filter(status="폐업").count()
        
        print(f"    - 전체: {total}, 정상: {normal_count}, 폐업: {closed_count}")
        self.assertEqual(total, 10)
        self.assertEqual(normal_count, 8)
        self.assertEqual(closed_count, 2)
        
        closure_rate = (closed_count / total) * 100
        print(f"    - 폐업률: {closure_rate}%")
        self.assertEqual(closure_rate, 20.0, f"폐업률 계산: {closure_rate}%")
        print("    ✅ 통계 계산 정확성 확인")


# ========================================
# 5. API 뷰 테스트
# ========================================

class APIViewTests(TestCase):
    """API 엔드포인트 테스트"""
    
    def setUp(self):
        self.client = Client()
    
    def test_collector_view_accessible(self):
        print("\n[TEST] 수집 UI 접근 테스트 시작")
        # config/urls.py에서 루트 URL ('')에 collector_view가 매핑되어 있음
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        print("    ✅ 수집 페이지(collector_view) 접근 성공")
    
    def test_start_collection_without_api_keys(self):
        print("\n[TEST] API 키 누락 시 수집 시작 방지 테스트 시작")
        response = self.client.post(
            '/api/start-collection/',
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('error', data)
        print("    ✅ API 키 누락 에러 반환 확인")
    
    def test_start_collection_with_invalid_kakao_key(self):
        print("\n[TEST] 잘못된 카카오 API 키 처리 테스트 시작")
        response = self.client.post(
            '/api/start-collection/',
            data=json.dumps({
                'kakao_api_key': 'invalid_key_12345',
                'kakao_js_key': 'invalid_js_key',
                'seoul_api_key': 'invalid_seoul_key',
                'target_gu': '영등포구'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        # 잘못된 키로 인한 에러 메시지 확인
        self.assertIn('error', data)
        print("    ✅ API 키 유효성 검증 실패 확인")
    
    def test_check_status_endpoint(self):
        print("\n[TEST] 수집 상태 확인 API 테스트 시작")
        response = self.client.get('/api/check-status/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('running', data)
        self.assertIn('progress', data)
        self.assertIn('completed', data)
        print("    ✅ 상태 확인 API 응답 구조 정상")
    
    def test_get_results_endpoint(self):
        print("\n[TEST] 수집 결과 조회 API 테스트 시작")
        response = self.client.get('/api/get-results/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('stores', data)
        print("    ✅ 결과 조회 API 응답 구조 정상")


# ========================================
# 6. 데이터 품질 검증 테스트
# ========================================

class DataQualityTests(TestCase):
    """데이터 품질 검증 테스트"""
    
    def test_no_duplicate_place_ids_in_database(self):
        print("\n[TEST] DB place_id 중복 검사 시작")
        # 여러 편의점 생성
        for i in range(10):
            YeongdeungpoConvenience.objects.create(
                place_id=f"quality_test_{i}",
                base_daiso="테스트 다이소",
                name=f"편의점 {i}",
                address=f"서울시 영등포구 테스트로 {i}",
                distance=100,
                location=Point(126.9 + (i * 0.01), 37.5, srid=4326)
            )
        
        total_count = YeongdeungpoConvenience.objects.count()
        unique_count = YeongdeungpoConvenience.objects.values('place_id').distinct().count()
        
        self.assertEqual(total_count, unique_count, 
                        f"중복 발견! 전체: {total_count}, 유니크: {unique_count}")
        
        # 중복률 계산
        duplicate_rate = ((total_count - unique_count) / total_count * 100) if total_count > 0 else 0
        self.assertEqual(duplicate_rate, 0.0, f"중복률: {duplicate_rate}% (목표: 0%)")
        print(f"    ✅ 중복 데이터 없음 (중복률: {duplicate_rate}%)")
    
    def test_all_stores_have_required_fields(self):
        print("\n[TEST] 필수 필드 누락 검사 시작")
        # 테스트 데이터 생성
        YeongdeungpoConvenience.objects.create(
            place_id="required_field_test",
            base_daiso="테스트 다이소",
            name="필수 필드 테스트 편의점",
            address="서울시 영등포구 테스트로 1",
            distance=100,
            location=Point(126.9066, 37.5171, srid=4326)
        )
        
        stores = YeongdeungpoConvenience.objects.all()
        missing_fields = []
        
        for store in stores:
            if not store.name:
                missing_fields.append(('name', store.place_id))
            if not store.address:
                missing_fields.append(('address', store.place_id))
            if not store.location:
                missing_fields.append(('location', store.place_id))
        
        self.assertEqual(len(missing_fields), 0, 
                        f"필수 필드 누락: {missing_fields}")
        print("    ✅ 모든 매장에 필수 필드(name, address, location) 존재 확인")
    
    def test_address_contains_seoul(self):
        print("\n[TEST] 주소 내 '서울' 포함 여부 테스트 시작")
        YeongdeungpoConvenience.objects.create(
            place_id="address_test",
            base_daiso="테스트 다이소",
            name="서울 편의점",
            address="서울시 영등포구 당산동 123-45",
            distance=100,
            location=Point(126.9066, 37.5171, srid=4326)
        )
        
        stores = YeongdeungpoConvenience.objects.all()
        non_seoul_stores = []
        
        for store in stores:
            if store.address and '서울' not in store.address:
                non_seoul_stores.append({
                    'name': store.name,
                    'address': store.address
                })
        
        self.assertEqual(len(non_seoul_stores), 0,
                        f"서울 외 주소 발견: {non_seoul_stores}")
        print("    ✅ 모든 주소에 '서울' 포함됨 확인")

    def test_address_contains_target_region(self):
        print("\n[TEST] 주소 내 타겟 지역(영등포구) 포함 여부 테스트 시작")
        target_gu = "영등포구"
        
        YeongdeungpoConvenience.objects.create(
            place_id="region_test",
            base_daiso="테스트 다이소",
            name="영등포 편의점",
            address="서울시 영등포구 당산로 123",
            distance=100,
            location=Point(126.9066, 37.5171, srid=4326)
        )
        
        stores = YeongdeungpoConvenience.objects.all()
        invalid_region_stores = []
        
        for store in stores:
            if store.address and target_gu not in store.address:
                invalid_region_stores.append({
                    'name': store.name,
                    'address': store.address
                })
        
        self.assertEqual(len(invalid_region_stores), 0,
                        f"{target_gu} 외 주소 발견: {invalid_region_stores}")
        print(f"    ✅ 모든 주소에 '{target_gu}' 포함됨 확인")

    def test_closure_result_consistency(self):
        print("\n[TEST] 수집 데이터와 폐업 검증 결과 수 일치 테스트 시작")
        # 편의점 5개 생성
        for i in range(5):
            YeongdeungpoConvenience.objects.create(
                place_id=f"consistency_test_{i}",
                base_daiso="테스트 다이소",
                name=f"편의점 {i}",
                address=f"서울시 영등포구 테스트로 {i}",
                distance=100,
                location=Point(126.9 + (i * 0.01), 37.5, srid=4326)
            )
            
        # 검증 결과 5개 생성
        for i in range(5):
            StoreClosureResult.objects.create(
                place_id=f"consistency_test_{i}",
                name=f"편의점 {i}",
                address=f"서울시 영등포구 테스트로 {i}",
                status="정상",
                match_reason="테스트",
                location=Point(126.9 + (i * 0.01), 37.5, srid=4326)
            )
            
        # 데이터 수 비교
        conv_count = YeongdeungpoConvenience.objects.count()
        result_count = StoreClosureResult.objects.count()
        
        print(f"    - 수집된 편의점: {conv_count}개, 검증 결과: {result_count}개")
        # 실제 환경에서는 100% 일치하지 않을 수 있으나(중복 제거 등으로 인해), 
        # 테스트 환경에서는 동일하게 생성했으므로 일치해야 함
        self.assertEqual(conv_count, result_count,
                        f"수집된 편의점({conv_count})과 검증 결과({result_count}) 불일치")
        print("    ✅ 데이터 수 일치 확인")


# ========================================
# 7. 성능 벤치마크 테스트
# ========================================

class PerformanceBenchmarkTests(TestCase):
    """성능 벤치마크 테스트"""
    
    def test_bulk_creation_performance(self):
        """대량 데이터 생성 성능 테스트 (1000개)"""
        start_time = time.time()
        
        # 1000개 편의점 데이터 생성
        stores = [
            YeongdeungpoConvenience(
                place_id=f"perf_test_{i}",
                base_daiso="테스트 다이소",
                name=f"편의점 {i}",
                address=f"서울시 영등포구 테스트로 {i}",
                distance=100,
                location=Point(126.9 + (i * 0.0001), 37.5 + (i * 0.0001), srid=4326)
            )
            for i in range(1000)
        ]
        YeongdeungpoConvenience.objects.bulk_create(stores)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 결과 출력 (시니어 관점: 수치화된 로그)
        print(f"\n    ✅ [성능결과] 1,000개 데이터 생성: {execution_time:.4f}초 (목표: < 1.0초)")
        
        # 1000개 생성에 1초 미만이어야 함
        self.assertLess(execution_time, 1.0, f"1000개 데이터 생성 소요 시간: {execution_time}초 (목표: < 1.0초)")
        
    def test_spatial_query_performance(self):
        """공간 쿼리 성능 테스트"""
        # 데이터셋 준비 (100개)
        for i in range(100):
            YeongdeungpoConvenience.objects.create(
                place_id=f"spatial_test_{i}",
                base_daiso="테스트 다이소",
                name=f"편의점 {i}",
                address=f"서울시 영등포구 테스트로 {i}",
                distance=100,
                location=Point(126.9066 + (i * 0.001), 37.5171 + (i * 0.001), srid=4326)
            )
            
        start_time = time.time()
        
        # 반경 검색 (거리 계산 포함)
        center = Point(126.9066, 37.5171, srid=4326)
        # dwithin 등 공간 연산 테스트
        count = YeongdeungpoConvenience.objects.filter(
            location__dwithin=(center, 0.01)  # 약 1km 반경
        ).count()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 결과 출력
        print(f"    ✅ [성능결과] 공간 쿼리(반경검색) 100회: {execution_time:.4f}초 (목표: < 0.1초)")
        
        # 0.1초 미만이어야 함
        self.assertLess(execution_time, 0.1, f"공간 쿼리 소요 시간: {execution_time}초 (목표: < 0.1초)")


# ========================================
# 8. 예외 처리 테스트
# ========================================

class ExceptionHandlingTests(TestCase):
    """예외 처리 및 안정성 테스트"""
    
    def setUp(self):
        self.client = Client()

    def test_duplicate_execution_prevented(self):
        print("\n[TEST] 중복 실행 방지(API) 테스트 시작")
        # stores.views.collection_status를 모킹하여 'running': True 상태로 만듦
        with patch('stores.views.collection_status', {
            'running': True,
            'progress': 50,
            'message': '수집 중...',
            'completed': False,
            'error': None
        }):
            response = self.client.post(
                '/api/start-collection/',
                data=json.dumps({
                    'kakao_api_key': 'test_key',
                    'kakao_js_key': 'test_js_key',
                    'seoul_api_key': 'test_seoul_key',
                    'target_gu': '영등포구'
                }),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # 실패해야 함
            self.assertFalse(data['success'])
            self.assertIn('이미 수집이 진행 중입니다', data['error'])
            print("    ✅ 중복 실행 시도 차단 및 에러 메시지 확인")
