# stores/management/commands/collect_convenience_only.py
"""
다이소 기준 편의점만 수집하는 커맨드 (확장성 개선판)

핵심 개선사항:
1. --gu 인자로 타겟 구 지정 가능 (기본: 영등포구)
2. 타겟 구 주소 필터링 (확장성 확보)
3. 수집 결과 상세 통계
"""

import os
import requests
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from stores.models import YeongdeungpoDaiso, YeongdeungpoConvenience


class Command(BaseCommand):
    help = '다이소 기준 편의점만 수집합니다. (--gu 옵션으로 대상 구 지정)'

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
            default=1.8,
            help='탐색 반경 (km, 이전: 1.3km >>> (상위10개)통계값 바탕: 1.8km)'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            dest='use_async',
            help='비동기 병렬 수집 모드 (4분면 동시 호출, 75% 성능 개선)'
        )

    def is_target_gu(self, address, target_gu):
        """
        주소가 타겟 구인지 확인 (단순화된 필터)
        """
        if not address:
            return False
        return target_gu in address

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
        
        # 기존 데이터 삭제 옵션 (해당 구의 데이터만 삭제)
        if options['clear']:
            deleted_count = YeongdeungpoConvenience.objects.filter(gu=target_gu).delete()[0]
            self.stdout.write(self.style.WARNING(f"{target_gu} 기존 편의점 데이터 {deleted_count}개 삭제"))
        
        # 해당 구 다이소 전체 조회
        daiso_list = YeongdeungpoDaiso.objects.filter(gu=target_gu)
        total_daiso_count = daiso_list.count()
        
        if total_daiso_count == 0:
            self.stdout.write(self.style.ERROR(
                f"{target_gu} 다이소가 없습니다. 먼저 collect_yeongdeungpo_daiso를 실행하세요."
            ))
            return
        
        use_async = options.get('use_async', False)
        
        self.stdout.write(self.style.SUCCESS(
            f"총 {total_daiso_count}개의 {target_gu} 다이소에 대해 편의점 수집을 시작합니다."
        ))
        self.stdout.write(f"탐색 반경: {radius_km}km")
        if use_async:
            self.stdout.write(self.style.WARNING("🚀 비동기 모드 활성화 (4분면 동시 호출)"))
        
        # 비동기 모드 분기
        if use_async:
            self._handle_async(KAKAO_API_KEY, daiso_list, target_gu, radius_km, total_daiso_count)
            return

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
                                # [핵심] 타겟 구 필터링
                                address = item.get('road_address_name') or item.get('address_name', '')
                                
                                if not self.is_target_gu(address, target_gu):
                                    skipped_count += 1
                                    continue
                                
                                lng = float(item.get('x'))
                                lat = float(item.get('y'))
                                point = Point(lng, lat)
                                dist = int(item.get('distance', 0))
                                
                                # place_id 기준 중복 방지 (Race Condition 방지: transaction.atomic 사용)
                                from django.db import transaction
                                with transaction.atomic():
                                    YeongdeungpoConvenience.objects.select_for_update().update_or_create(
                                        place_id=item.get('id'),
                                        defaults={
                                            'name': item.get('place_name'),
                                            'address': address,
                                            'phone': item.get('phone'),
                                            'location': point,
                                            'distance': dist,
                                            'base_daiso': daiso.name,
                                            'gu': target_gu,  # 구 정보 저장
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

            self.stdout.write(f"  -> {stored_count}개 저장, {skipped_count}개 스킵 ({target_gu} 아님)")
            total_collected += stored_count
            total_skipped += skipped_count
            time.sleep(0.3)

        # 최종 통계
        convenience_count = YeongdeungpoConvenience.objects.count()
        
        # 타겟 구 외 데이터 확인
        wrong_gu_count = sum(1 for c in YeongdeungpoConvenience.objects.all() 
                           if not self.is_target_gu(c.address, target_gu))
        
        self.stdout.write(self.style.SUCCESS(f"""
--- 수집 완료 ---
  ✅ 이번 수집: {total_collected}개
  ⚠️ 스킵 ({target_gu} 아님): {total_skipped}개

📊 현재 DB 상태:
  - {target_gu} 편의점: {convenience_count}개
  - {target_gu} 외 데이터: {wrong_gu_count}개
        """))
        
        if wrong_gu_count > 0:
            self.stdout.write(self.style.WARNING(
                f"⚠️ {target_gu} 아닌 편의점 {wrong_gu_count}개가 DB에 있습니다."
            ))

    def _handle_async(self, api_key, daiso_list, target_gu, radius_km, total_daiso_count):
        """
        비동기 모드 편의점 수집 핸들러
        
        4분면 동시 호출로 성능 75% 개선
        """
        import time as time_module
        from django.db import transaction
        from .async_collector import run_async_collection
        
        start_time = time_module.time()
        
        # 진행 상황 콜백
        def progress_callback(idx, total, daiso_name, count):
            self.stdout.write(f"[{idx}/{total}] '{daiso_name}' → {count}개 수집")
        
        self.stdout.write(self.style.WARNING("비동기 수집 시작..."))
        
        # 비동기 수집 실행
        stores, stats = run_async_collection(
            api_key=api_key,
            daiso_list=daiso_list,
            target_gu=target_gu,
            radius_km=radius_km
        )
        
        # DB 저장 (bulk upsert)
        stored_count = 0
        for item in stores:
            try:
                lng = float(item.get('x'))
                lat = float(item.get('y'))
                point = Point(lng, lat)
                address = item.get('road_address_name') or item.get('address_name', '')
                
                with transaction.atomic():
                    YeongdeungpoConvenience.objects.update_or_create(
                        place_id=item.get('id'),
                        defaults={
                            'name': item.get('place_name'),
                            'address': address,
                            'phone': item.get('phone'),
                            'location': point,
                            'distance': int(item.get('distance', 0)),
                            'base_daiso': item.get('_base_daiso', ''),
                            'gu': target_gu,
                        }
                    )
                stored_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"저장 실패: {e}"))
        
        elapsed = time_module.time() - start_time
        
        # 최종 통계
        convenience_count = YeongdeungpoConvenience.objects.filter(gu=target_gu).count()
        
        self.stdout.write(self.style.SUCCESS(f"""
--- 🚀 비동기 수집 완료 ---
  ⏱️ 소요 시간: {elapsed:.2f}초
  📡 API 호출: {stats['api_calls']}회
  ✅ DB 저장: {stored_count}개
  ⚠️ 스킵 ({target_gu} 아님): {stats['skipped_count']}개

📊 현재 DB 상태:
  - {target_gu} 편의점: {convenience_count}개
        """))
        
        if stats['errors']:
            self.stdout.write(self.style.WARNING(
                f"⚠️ 에러 {len(stats['errors'])}건: {stats['errors'][:3]}"
            ))
