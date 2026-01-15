# stores/management/commands/collect_convenience_only.py
"""
영등포구 다이소 기준 편의점만 수집하는 커맨드 (개선판)

핵심 개선사항:
1. 엄격한 영등포구 주소 필터링
2. 불필요한 다른 구 편의점 제외
3. 수집 결과 상세 통계
"""

import os
import requests
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from stores.models import YeongdeungpoDaiso, YeongdeungpoConvenience


# 주변 구 이름 (제외 대상)
EXCLUDED_GU = ['구로구', '금천구', '양천구', '관악구', '동작구', '서초구', '마포구', '용산구']


class Command(BaseCommand):
    help = '영등포구 다이소 기준 편의점만 수집합니다. (엄격한 영등포구 필터링)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='카카오 API REST KEY'
        )
        parser.add_argument(
            '--gu',
            type=str,
            default='영등포구',
            help='대상 구 (기본: 영등포구)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='기존 편의점 데이터 삭제 후 재수집'
        )
        parser.add_argument(
            '--radius',
            type=float,
            default=1.3,
            help='탐색 반경 (km, 기본: 1.3)'
        )

    def is_strictly_yeongdeungpo(self, address):
        """
        주소가 정확히 영등포구인지 확인 (엄격한 필터)
        """
        if not address:
            return False
        
        # 다른 구 이름이 포함되면 제외
        for gu in EXCLUDED_GU:
            if gu in address:
                return False
        
        # 영등포구가 반드시 포함되어야 함
        return '영등포구' in address

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
        
        # [핵심] 편의점만 수집 (카페 제외)
        TARGET_CATEGORIES = ['CS2']  # CS2: 편의점
        
        target_gu = options['gu']
        radius_km = options['radius']
        
        # 기존 데이터 삭제 옵션
        if options['clear']:
            deleted_count = YeongdeungpoConvenience.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f"기존 편의점 데이터 {deleted_count}개 삭제"))
        
        # 영등포구 다이소 전체 조회
        daiso_list = YeongdeungpoDaiso.objects.all()
        total_daiso_count = daiso_list.count()
        
        if total_daiso_count == 0:
            self.stdout.write(self.style.ERROR(
                f"{target_gu} 다이소가 없습니다. 먼저 collect_yeongdeungpo_daiso를 실행하세요."
            ))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f"총 {total_daiso_count}개의 {target_gu} 다이소에 대해 편의점 수집을 시작합니다."
        ))
        self.stdout.write(f"탐색 반경: {radius_km}km")

        # 반경에 따른 위도/경도 차이 계산 (근사치)
        DELTA_LAT = 0.0090 * radius_km  
        DELTA_LNG = 0.0113 * radius_km

        total_collected = 0
        total_skipped = 0
        
        for idx, daiso in enumerate(daiso_list, 1):
            if not daiso.location:
                continue

            cx = daiso.location.x  # 경도
            cy = daiso.location.y  # 위도

            self.stdout.write(f"[{idx}/{total_daiso_count}] '{daiso.name}' 주변 편의점 탐색 중...")

            # 사분면 좌표 생성
            quadrants = [
                # 1사분면 (우상)
                f"{cx:.6f},{cy:.6f},{(cx + DELTA_LNG):.6f},{(cy + DELTA_LAT):.6f}",
                # 2사분면 (좌상)
                f"{(cx - DELTA_LNG):.6f},{cy:.6f},{cx:.6f},{(cy + DELTA_LAT):.6f}",
                # 3사분면 (좌하)
                f"{(cx - DELTA_LNG):.6f},{(cy - DELTA_LAT):.6f},{cx:.6f},{cy:.6f}",
                # 4사분면 (우하)
                f"{cx:.6f},{(cy - DELTA_LAT):.6f},{(cx + DELTA_LNG):.6f},{cy:.6f}"
            ]

            stored_count = 0
            skipped_count = 0

            for category_code in TARGET_CATEGORIES:
                for rect in quadrants:
                    url = "https://dapi.kakao.com/v2/local/search/category.json"
                    page = 1
                    
                    while True:
                        params = {
                            "category_group_code": category_code,
                            "rect": rect,
                            "x": f"{cx:.6f}",
                            "y": f"{cy:.6f}",
                            "page": page,
                            "size": 15,
                            "sort": "distance"
                        }

                        try:
                            response = requests.get(url, headers=headers, params=params, timeout=5)
                            
                            if response.status_code == 400:
                                self.stdout.write(self.style.ERROR(f"API 400 에러: {response.text}"))
                                break
                            
                            response.raise_for_status()
                            data = response.json()
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"API 요청 실패: {e}"))
                            break

                        documents = data.get('documents', [])
                        
                        if not documents:
                            break

                        for item in documents:
                            try:
                                # [핵심] 영등포구 엄격 필터링
                                address = item.get('road_address_name') or item.get('address_name', '')
                                
                                if not self.is_strictly_yeongdeungpo(address):
                                    skipped_count += 1
                                    continue
                                
                                lng = float(item.get('x'))
                                lat = float(item.get('y'))
                                point = Point(lng, lat)
                                dist = int(item.get('distance', 0))
                                
                                # place_id 기준 중복 방지
                                YeongdeungpoConvenience.objects.update_or_create(
                                    place_id=item.get('id'),
                                    defaults={
                                        'name': item.get('place_name'),
                                        'address': address,
                                        'phone': item.get('phone'),
                                        'location': point,
                                        'distance': dist,
                                        'base_daiso': daiso.name
                                    }
                                )
                                stored_count += 1
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f"저장 실패: {e}"))
                                continue

                        if data.get('meta', {}).get('is_end'):
                            break
                        
                        page += 1
                        if page > 3:  # 최대 3페이지
                            break
                        
                        time.sleep(0.2)

            self.stdout.write(f"  -> {stored_count}개 저장, {skipped_count}개 스킵 (영등포구 아님)")
            total_collected += stored_count
            total_skipped += skipped_count
            time.sleep(0.3)

        # 최종 통계
        convenience_count = YeongdeungpoConvenience.objects.count()
        
        # 영등포구 외 데이터 확인
        wrong_gu_count = sum(1 for c in YeongdeungpoConvenience.objects.all() 
                           if not self.is_strictly_yeongdeungpo(c.address))
        
        self.stdout.write(self.style.SUCCESS(f"""
--- 수집 완료 ---
  ✅ 이번 수집: {total_collected}개
  ⚠️ 스킵 (영등포구 아님): {total_skipped}개

📊 현재 DB 상태:
  - 영등포구 편의점: {convenience_count}개
  - 영등포구 외 데이터: {wrong_gu_count}개
        """))
        
        if wrong_gu_count > 0:
            self.stdout.write(self.style.WARNING(
                f"⚠️ 영등포구 아닌 편의점 {wrong_gu_count}개가 DB에 있습니다."
            ))
