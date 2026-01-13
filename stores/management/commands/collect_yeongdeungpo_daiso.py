# stores/management/commands/collect_yeongdeungpo_daiso.py
"""
영등포구 내 다이소 지점만 수집하는 커맨드
기존 collect_daiso.py와 달리 영등포구에 한정하여 데이터 수집
"""

import requests
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from stores.models import YeongdeungpoDaiso


class Command(BaseCommand):
    help = '영등포구 내 다이소 지점만 수집합니다.'

    def is_yeongdeungpo_address(self, address):
        """
        주소가 영등포구인지 확인
        
        Args:
            address: 주소 문자열
            
        Returns:
            bool: 영등포구 주소이면 True
        """
        if not address:
            return False
        
        yeongdeungpo_keywords = ['영등포구', '영등포동', '영등포']
        return any(keyword in address for keyword in yeongdeungpo_keywords)

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='카카오 API REST KEY'
        )

    def handle(self, *args, **options):
        # API 키 설정 (우선순위: 인자 > settings > 환경변수)
        import os
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
        
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        query = "서울 영등포구 다이소"
        
        self.stdout.write(self.style.WARNING(f"--- 검색 시작: {query} ---"))
        
        collected_count = 0
        skipped_count = 0
        page = 1
        
        while True:
            params = {
                "query": query,
                "page": page,
                "size": 15,
            }
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=5)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f"네트워크 오류: {e}"))
                break
            
            data = response.json()
            documents = data.get('documents', [])
            meta = data.get('meta', {})
            
            if not documents:
                break
            
            for item in documents:
                place_name = item.get('place_name', '')
                
                # '다이소' 이름이 포함된 것만 저장
                if '다이소' not in place_name:
                    continue
                
                address = item.get('address_name') or item.get('road_address_name')
                
                # [핵심] 영등포구 주소 검증
                if not self.is_yeongdeungpo_address(address):
                    self.stdout.write(f"  ⚠️ 영등포구 아님, 스킵: {place_name} ({address})")
                    skipped_count += 1
                    continue
                
                # 좌표 변환
                try:
                    lng = float(item.get('x'))
                    lat = float(item.get('y'))
                    point = Point(lng, lat)
                except (ValueError, TypeError):
                    self.stdout.write(f"  ⚠️ 좌표 오류, 스킵: {place_name}")
                    continue
                
                # DB 저장 (중복 방지)
                store, created = YeongdeungpoDaiso.objects.update_or_create(
                    daiso_id=item.get('id'),
                    defaults={
                        'name': place_name,
                        'address': address,
                        'location': point,
                    }
                )
                
                action = "생성" if created else "업데이트"
                self.stdout.write(f"  ✅ {place_name} - {action}")
                collected_count += 1
            
            # 마지막 페이지 확인
            if meta.get('is_end'):
                break
            
            page += 1
            time.sleep(0.5)  # API 호출 제한 방지
        
        # 결과 출력
        self.stdout.write(self.style.SUCCESS(f"\n--- 수집 완료 ---"))
        self.stdout.write(f"  ✅ 수집된 다이소: {collected_count}개")
        self.stdout.write(f"  ⚠️ 스킵된 항목: {skipped_count}개")
