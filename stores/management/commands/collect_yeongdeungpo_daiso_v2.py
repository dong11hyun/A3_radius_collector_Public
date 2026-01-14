# stores/management/commands/collect_yeongdeungpo_daiso_v2.py
"""
영등포구 다이소 수집 V2 - 다이소 공식 API + 카카오 API 2중 체크
1. 다이소 공식 API로 16개 매장 수집
2. 좌표가 (0,0)인 경우 카카오 API로 보완
3. 중복 방지: 다이소 매장코드(strCd) 기준
"""

import requests
import json
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from stores.models import YeongdeungpoDaiso


class Command(BaseCommand):
    help = '영등포구 다이소 수집 V2 - 다이소 공식 API + 카카오 API 2중 체크'

    def add_arguments(self, parser):
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
            "curLitd": 126.9088468,  # 영등포구 중심 좌표
            "curLttd": 37.4989756,
            "currentPage": 1,
            "geolocationAgrYn": "Y",
            "keyword": keyword,
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
        
        # 카카오 API 키 설정
        KAKAO_API_KEY = (
            options.get('api_key') or
            getattr(settings, 'KAKAO_API_KEY', None) or
            os.environ.get('KAKAO_API_KEY', '')
        )
        
        # 기존 데이터 삭제 옵션
        if options.get('clear'):
            deleted_count = YeongdeungpoDaiso.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f"🗑️ 기존 데이터 {deleted_count}개 삭제"))
        
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("📦 다이소 수집 V2 시작 (공식 API + 카카오 보완)"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        
        # 1단계: 다이소 공식 API 조회
        self.stdout.write("\n🔍 [1단계] 다이소 공식 API 조회...")
        stores = self.fetch_from_daiso_api("영등포")
        
        if not stores:
            self.stdout.write(self.style.ERROR("다이소 API에서 데이터를 가져오지 못했습니다."))
            return
        
        self.stdout.write(f"  → {len(stores)}개 매장 발견")
        
        collected_count = 0
        補完_count = 0
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
                        補完_count += 1
                    else:
                        self.stdout.write(self.style.ERROR(f"  ❌ 좌표 보완 실패"))
                        failed_count += 1
                        continue
                else:
                    self.stdout.write(self.style.WARNING("  ⚠️ 카카오 API 키 없음 - 스킵"))
                    failed_count += 1
                    continue
            
            # DB 저장
            try:
                point = Point(lng, lat)
                
                obj, created = YeongdeungpoDaiso.objects.update_or_create(
                    daiso_id=store_code,  # 다이소 매장코드를 ID로 사용
                    defaults={
                        'name': f"다이소 {name}",
                        'address': address,
                        'location': point,
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
        self.stdout.write(f"  🔧 카카오 보완: {補完_count}개")
        self.stdout.write(f"  ❌ 실패: {failed_count}개")
        
        total_in_db = YeongdeungpoDaiso.objects.count()
        self.stdout.write(f"\n  📊 DB 총 다이소: {total_in_db}개")
