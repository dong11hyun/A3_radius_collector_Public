# stores/management/commands/collect_yeongdeungpo_daiso.py
"""
영등포구 내 다이소 지점만 수집하는 커맨드 (개선판)

핵심 개선사항:
1. 그리드 기반 영역 검색으로 45개 제한 우회
2. 엄격한 영등포구 주소 필터링
3. 모든 다이소 매장 완전 수집
"""

import os
import requests
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from stores.models import YeongdeungpoDaiso


# 영등포구 경계 좌표 (대략적인 사각형)
YEONGDEUNGPO_BOUNDS = {
    'min_lat': 37.490,  # 남쪽 (대림동 최남단 포함)
    'max_lat': 37.545,  # 북쪽 (여의도)
    'min_lng': 126.876,  # 서쪽 (양평동)
    'max_lng': 126.944,  # 동쪽 (영등포동)
}

# 주변 구 이름 (제외 대상)
EXCLUDED_GU = ['구로구', '금천구', '양천구', '관악구', '동작구', '서초구', '마포구', '용산구']


class Command(BaseCommand):
    help = '영등포구 내 다이소 지점만 수집합니다. (그리드 기반 완전 수집)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='카카오 API REST KEY'
        )
        parser.add_argument(
            '--grid-size',
            type=int,
            default=4,
            help='그리드 분할 크기 (기본: 4x4=16개 영역)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='기존 데이터 삭제 후 재수집'
        )

    def is_strictly_yeongdeungpo(self, address):
        """
        주소가 정확히 영등포구인지 확인 (엄격한 필터)
        
        Args:
            address: 주소 문자열
            
        Returns:
            bool: 영등포구 주소이면 True, 다른 구면 False
        """
        if not address:
            return False
        
        # 다른 구 이름이 포함되면 제외
        for gu in EXCLUDED_GU:
            if gu in address:
                return False
        
        # 영등포구가 반드시 포함되어야 함
        return '영등포구' in address

    def generate_grid_rects(self, grid_size):
        """
        영등포구 영역을 그리드로 분할하여 rect 좌표 목록 생성
        
        Args:
            grid_size: 그리드 분할 크기 (예: 4 → 4x4=16개)
            
        Returns:
            list: rect 좌표 문자열 목록
        """
        rects = []
        
        lat_step = (YEONGDEUNGPO_BOUNDS['max_lat'] - YEONGDEUNGPO_BOUNDS['min_lat']) / grid_size
        lng_step = (YEONGDEUNGPO_BOUNDS['max_lng'] - YEONGDEUNGPO_BOUNDS['min_lng']) / grid_size
        
        for i in range(grid_size):
            for j in range(grid_size):
                min_lng = YEONGDEUNGPO_BOUNDS['min_lng'] + (j * lng_step)
                min_lat = YEONGDEUNGPO_BOUNDS['min_lat'] + (i * lat_step)
                max_lng = min_lng + lng_step
                max_lat = min_lat + lat_step
                
                # rect 형식: "좌x,좌y,우x,우y" (경도,위도,경도,위도)
                rect = f"{min_lng:.6f},{min_lat:.6f},{max_lng:.6f},{max_lat:.6f}"
                rects.append({
                    'rect': rect,
                    'center_x': (min_lng + max_lng) / 2,
                    'center_y': (min_lat + max_lat) / 2,
                    'label': f"그리드[{i+1},{j+1}]"
                })
        
        return rects

    def search_daiso_in_rect(self, headers, rect_info):
        """
        특정 rect 영역에서 다이소 검색
        
        카테고리 검색 (MT1: 대형마트) + 키워드 '다이소' 필터링
        """
        found_stores = []
        
        # 방법 1: 키워드 검색 "다이소" with rect
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        page = 1
        
        while page <= 3:  # 최대 3페이지
            params = {
                "query": "다이소",
                "rect": rect_info['rect'],
                "page": page,
                "size": 15,
            }
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=5)
                if response.status_code != 200:
                    break
                    
                data = response.json()
                documents = data.get('documents', [])
                
                if not documents:
                    break
                
                for item in documents:
                    place_name = item.get('place_name', '')
                    
                    # 다이소가 이름에 포함되어야 함
                    if '다이소' not in place_name:
                        continue
                    
                    address = item.get('address_name') or item.get('road_address_name', '')
                    
                    # 영등포구 엄격 필터
                    if not self.is_strictly_yeongdeungpo(address):
                        continue
                    
                    found_stores.append({
                        'id': item.get('id'),
                        'name': place_name,
                        'address': address,
                        'x': item.get('x'),
                        'y': item.get('y'),
                    })
                
                # 마지막 페이지 확인
                if data.get('meta', {}).get('is_end'):
                    break
                
                page += 1
                time.sleep(0.2)
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  API 오류: {e}"))
                break
        
        return found_stores

    def handle(self, *args, **options):
        # API 키 설정 (우선순위: 인자 > settings > 환경변수)
        KAKAO_API_KEY = (
            options.get('api_key') or 
            getattr(settings, 'KAKAO_API_KEY', None) or 
            os.environ.get('KAKAO_API_KEY', '')
        )
        
        if not KAKAO_API_KEY:
            self.stdout.write(self.style.ERROR(
                "카카오 API 키가 필요합니다. --api-key 옵션 또는 KAKAO_API_KEY 환경변수를 설정하세요."
            ))
            return
        
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        grid_size = options['grid_size']
        
        # 기존 데이터 삭제 옵션
        if options['clear']:
            deleted_count = YeongdeungpoDaiso.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f"기존 데이터 {deleted_count}개 삭제"))
        
        self.stdout.write(self.style.SUCCESS(
            f"--- 영등포구 다이소 수집 시작 ({grid_size}x{grid_size}={grid_size**2}개 그리드) ---"
        ))
        
        # 그리드 생성
        grid_rects = self.generate_grid_rects(grid_size)
        
        all_stores = {}  # place_id 기준 중복 제거
        skipped_count = 0
        
        for idx, rect_info in enumerate(grid_rects, 1):
            self.stdout.write(f"[{idx}/{len(grid_rects)}] {rect_info['label']} 검색 중...")
            
            stores = self.search_daiso_in_rect(headers, rect_info)
            
            for store in stores:
                place_id = store['id']
                if place_id not in all_stores:
                    all_stores[place_id] = store
                    self.stdout.write(f"  ✅ 발견: {store['name']}")
            
            time.sleep(0.3)  # API 호출 제한 방지
        
        # 추가 키워드 검색 (동별로 세분화)
        dong_list = ['여의도동', '신길동', '당산동', '영등포동', '양평동', '문래동', '대림동', '도림동']
        
        self.stdout.write(self.style.WARNING("\n--- 동별 추가 검색 ---"))
        
        for dong in dong_list:
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            query = f"영등포구 {dong} 다이소"
            
            params = {
                "query": query,
                "page": 1,
                "size": 15,
            }
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get('documents', []):
                        place_name = item.get('place_name', '')
                        address = item.get('address_name') or item.get('road_address_name', '')
                        
                        if '다이소' not in place_name:
                            continue
                        
                        if not self.is_strictly_yeongdeungpo(address):
                            continue
                        
                        place_id = item.get('id')
                        if place_id not in all_stores:
                            all_stores[place_id] = {
                                'id': place_id,
                                'name': place_name,
                                'address': address,
                                'x': item.get('x'),
                                'y': item.get('y'),
                            }
                            self.stdout.write(f"  ✅ 추가 발견 ({dong}): {place_name}")
                
                time.sleep(0.3)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  검색 오류 ({dong}): {e}"))
        
        # DB 저장
        self.stdout.write(self.style.SUCCESS(f"\n--- DB 저장 ({len(all_stores)}개) ---"))
        
        saved_count = 0
        for place_id, store in all_stores.items():
            try:
                lng = float(store['x'])
                lat = float(store['y'])
                point = Point(lng, lat)
                
                _, created = YeongdeungpoDaiso.objects.update_or_create(
                    daiso_id=place_id,
                    defaults={
                        'name': store['name'],
                        'address': store['address'],
                        'location': point,
                    }
                )
                
                action = "생성" if created else "업데이트"
                self.stdout.write(f"  ✅ {store['name']} - {action}")
                saved_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ 저장 실패: {store['name']} - {e}"))
        
        # 최종 결과
        total_in_db = YeongdeungpoDaiso.objects.count()
        
        self.stdout.write(self.style.SUCCESS(f"""
--- 수집 완료 ---
  ✅ 이번 수집: {saved_count}개
  📊 DB 전체: {total_in_db}개
  ⚠️ 스킵 (영등포구 아님): {skipped_count}개
        """))
        
        # 영등포구 외 데이터 경고
        wrong_gu = [d for d in YeongdeungpoDaiso.objects.all() if not self.is_strictly_yeongdeungpo(d.address)]
        if wrong_gu:
            self.stdout.write(self.style.ERROR(f"\n⚠️ 영등포구 아닌 데이터 {len(wrong_gu)}개 발견!"))
            for d in wrong_gu[:5]:
                self.stdout.write(f"  - {d.name}: {d.address}")
