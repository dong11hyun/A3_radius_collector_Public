# stores/management/commands/collect_yeongdeungpo_daiso_v2.py
"""
다이소 수집 V2 - 다이소 공식 API + 카카오 API 2중 체크
1. 다이소 공식 API로 매장 수집
2. 좌표가 (0,0)인 경우 카카오 API로 보완
3. 중복 방지: 다이소 매장코드(strCd) 기준
4. --gu 옵션으로 대상 구 지정 가능
"""

import requests
import json
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from stores.models import YeongdeungpoDaiso
from .gu_codes import list_supported_gu


class Command(BaseCommand):
    help = '다이소 수집 V2 - 다이소 공식 API + 카카오 API 2중 체크 (--gu 옵션으로 대상 구 지정)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--gu',
            type=str,
            default='영등포구',
            help=f'대상 구 (기본: 영등포구). 지원: {", ".join(list_supported_gu())}'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='기존 데이터를 삭제하고 새로 수집'
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='카카오 API REST KEY (좌표 보완용)'
        )

    def fetch_from_daiso_api(self, keyword):
        """다이소 공식 API에서 매장 목록 조회"""
        url = "https://fapi.daisomall.co.kr/ms/msg/selStr"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Referer": "https://www.daisomall.co.kr/",
            "Origin": "https://www.daisomall.co.kr",
        }
        
        payload = {
            "curLitd": 126.9088468,  # 서울 중심 좌표 (참고용)
            "curLttd": 37.4989756,
            "currentPage": 1,
            "geolocationAgrYn": "Y",
            "keyword": keyword,  # 동적으로 구 이름 사용
            "pageSize": 100,
            "srchBassPkupStrYn": "Y",
            "srchYn": "Y"
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('success'):
                return result.get('data', [])
            return []
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"다이소 API 오류: {e}"))
            return []

    def fetch_coords_from_kakao(self, store_name, address, api_key):
        """카카오 API로 좌표 조회 (주소 → 좌표)"""
        # 1. 키워드 검색 시도
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {api_key}"}
        
        # 매장명으로 검색
        params = {"query": f"다이소 {store_name}", "size": 1}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            documents = data.get('documents', [])
            
            if documents:
                item = documents[0]
                return {
                    'lat': float(item.get('y', 0)),
                    'lng': float(item.get('x', 0)),
                    'kakao_id': item.get('id')
                }
        except Exception as e:
            self.stdout.write(f"    카카오 키워드 검색 실패: {e}")
        
        # 2. 주소로 지오코딩 시도
        geocode_url = "https://dapi.kakao.com/v2/local/search/address.json"
        params = {"query": address}
        
        try:
            response = requests.get(geocode_url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            documents = data.get('documents', [])
            
            if documents:
                item = documents[0]
                return {
                    'lat': float(item.get('y', 0)),
                    'lng': float(item.get('x', 0)),
                    'kakao_id': None
                }
        except Exception as e:
            self.stdout.write(f"    카카오 지오코딩 실패: {e}")
        
        return None

    def handle(self, *args, **options):
        import os
        
        target_gu = options['gu']
        
        # 구 이름 끝의 '구'만 제거하여 키워드 생성 (예: 영등포구 → 영등포, 구로구 → 구로)
        # 단, "중구"처럼 결과가 한 글자인 경우 검색어가 너무 짧아 원래 이름("중구") 사용
        keyword = target_gu[:-1] if target_gu.endswith('구') else target_gu
        if len(keyword) < 2:
            keyword = target_gu
        
        # 카카오 API 키 설정
        KAKAO_API_KEY = (
            options.get('api_key') or
            getattr(settings, 'KAKAO_API_KEY', None) or
            os.environ.get('KAKAO_API_KEY', '')
        )
        
        # 기존 데이터 삭제 옵션 (해당 구의 데이터만 삭제)
        if options.get('clear'):
            deleted_count = YeongdeungpoDaiso.objects.filter(gu=target_gu).delete()[0]
            self.stdout.write(self.style.WARNING(f"🗑️ {target_gu} 기존 데이터 {deleted_count}개 삭제"))
        
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"📦 {target_gu} 다이소 수집 V2 시작 (공식 API + 카카오 보완)"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        
        # 1단계: 다이소 공식 API 조회
        self.stdout.write(f"\n🔍 [1단계] 다이소 공식 API 조회... (keyword: {keyword})")
        stores = self.fetch_from_daiso_api(keyword)
        
        if not stores:
            self.stdout.write(self.style.ERROR("다이소 API에서 데이터를 가져오지 못했습니다."))
            return
        
        self.stdout.write(f"  → API에서 {len(stores)}개 매장 발견")
        
        # 서울 지역 매장만 필터링 (부산 강서구 등 다른 지역 제외)
        original_count = len(stores)
        stores = [s for s in stores if '서울' in s.get('strAddr', '')]
        filtered_count = original_count - len(stores)
        
        if filtered_count > 0:
            self.stdout.write(self.style.WARNING(f"  ⚠️ 서울 외 지역 {filtered_count}개 매장 필터링됨"))
        self.stdout.write(f"  서울 지역 {len(stores)}개 매장 대상")
        
        collected_count = 0
        sertify_count = 0
        failed_count = 0
        
        for store in stores:
            name = store.get('strNm', '')
            address = store.get('strAddr', '')
            store_code = str(store.get('strCd', ''))
            lat = store.get('strLttd', 0) or 0
            lng = store.get('strLitd', 0) or 0
            
            # 좌표 검증
            if lat == 0 or lng == 0:
                self.stdout.write(f"\n⚠️ [{name}] 좌표 누락 (0,0)")
                
                # 2단계: 카카오 API로 보완
                if KAKAO_API_KEY:
                    self.stdout.write(f"  🔧 [2단계] 카카오 API로 좌표 보완 시도...")
                    coords = self.fetch_coords_from_kakao(name, address, KAKAO_API_KEY)
                    
                    if coords and coords['lat'] != 0:
                        lat = coords['lat']
                        lng = coords['lng']
                        self.stdout.write(self.style.SUCCESS(f"  ✅ 좌표 보완 성공: ({lat}, {lng})"))
                        sertify_count += 1
                    else:
                        self.stdout.write(self.style.ERROR(f"  ❌ 좌표 보완 실패"))
                        failed_count += 1
                        continue
                else:
                    self.stdout.write(self.style.WARNING("  ⚠️ 카카오 API 키 없음 - 스킵"))
                    failed_count += 1
                    continue
            
            # DB 저장 (Race Condition 방지: transaction.atomic 사용)
            try:
                from django.db import transaction
                point = Point(lng, lat)
                
                with transaction.atomic():
                    obj, created = YeongdeungpoDaiso.objects.select_for_update().update_or_create(
                        daiso_id=store_code,  # 다이소 매장코드를 ID로 사용
                        defaults={
                            'name': f"다이소 {name}",
                            'address': address,
                            'location': point,
                            'gu': target_gu,  # 구 정보 저장
                        }
                    )
                
                action = "생성" if created else "업데이트"
                self.stdout.write(f"  ✅ [{name}] {action} | 좌표: ({lat:.4f}, {lng:.4f})")
                collected_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ [{name}] 저장 실패: {e}"))
                failed_count += 1
            
            time.sleep(0.2)  # API 호출 제한 방지
        
        # 결과 출력
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("📊 수집 결과"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"  ✅ 수집 성공: {collected_count}개")
        self.stdout.write(f"  🔧 카카오 보완: {sertify_count}개")
        self.stdout.write(f"  ❌ 실패: {failed_count}개")
        
        total_in_db = YeongdeungpoDaiso.objects.count()
        self.stdout.write(f"\n  📊 DB 총 다이소: {total_in_db}개")
