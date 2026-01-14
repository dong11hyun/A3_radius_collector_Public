# stores/management/commands/load_public_data_api.py
"""
공공데이터포탈 API로 상가(상권)정보를 조회하는 커맨드
소상공인시장진흥공단_상가(상권)정보 API 활용

CSV 대신 실시간 API 호출로 최신 데이터 조회
"""

import requests
import urllib.parse
from django.core.management.base import BaseCommand


# 영등포구 행정동 코드 (10자리)
# 출처: 행정안전부 행정동코드
YEONGDEUNGPO_DONGS = [
    {'code': '1156052000', 'name': '여의동'},
    {'code': '1156053000', 'name': '당산제1동'},
    {'code': '1156054000', 'name': '당산제2동'},
    {'code': '1156055000', 'name': '도림동'},
    {'code': '1156056000', 'name': '문래동'},
    {'code': '1156057000', 'name': '양평제1동'},
    {'code': '1156058000', 'name': '양평제2동'},
    {'code': '1156059000', 'name': '신길제1동'},
    {'code': '1156060500', 'name': '신길제3동'},
    {'code': '1156061000', 'name': '신길제4동'},
    {'code': '1156061500', 'name': '신길제5동'},
    {'code': '1156062000', 'name': '신길제6동'},
    {'code': '1156062500', 'name': '신길제7동'},
    {'code': '1156063000', 'name': '대림제1동'},
    {'code': '1156064000', 'name': '대림제2동'},
    {'code': '1156065000', 'name': '대림제3동'},
    {'code': '1156051000', 'name': '영등포본동'},
    {'code': '1156051500', 'name': '영등포동'},
]


class Command(BaseCommand):
    help = '공공데이터포탈 API로 상가(상권)정보 조회 (편의점 필터링)'
    
    # API 엔드포인트
    BASE_URL = "http://apis.data.go.kr/B553077/api/open/sdsc2"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            required=True,
            help='공공데이터포탈 API 서비스키 (URL 인코딩된 키 사용)'
        )
        parser.add_argument(
            '--dong',
            type=str,
            help='특정 행정동만 조회 (예: 여의동)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='조회만 하고 DB 저장하지 않음'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='상세 정보 출력'
        )
    
    def handle(self, *args, **options):
        api_key = options['api_key']
        target_dong = options.get('dong')
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("🏪 공공데이터포탈 API - 영등포구 편의점 조회"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  --dry-run 모드: DB에 저장하지 않음"))
        
        # 조회할 행정동 목록
        dongs_to_query = YEONGDEUNGPO_DONGS
        if target_dong:
            dongs_to_query = [d for d in YEONGDEUNGPO_DONGS if target_dong in d['name']]
            if not dongs_to_query:
                self.stdout.write(self.style.ERROR(f"'{target_dong}' 행정동을 찾을 수 없습니다."))
                return
        
        total_stores = []
        convenience_stores = []
        
        for dong in dongs_to_query:
            self.stdout.write(f"\n📍 {dong['name']} 조회 중...")
            
            stores = self.fetch_stores_in_dong(api_key, dong['code'], verbose)
            total_stores.extend(stores)
            
            # 편의점 필터링 (상권업종소분류명에 '편의점' 포함)
            conv_stores = [
                s for s in stores 
                if '편의점' in s.get('indsLclsNm', '') or 
                   '편의점' in s.get('indsMclsNm', '') or
                   '편의점' in s.get('indsSclsNm', '')
            ]
            convenience_stores.extend(conv_stores)
            
            self.stdout.write(f"   - 전체: {len(stores)}개, 편의점: {len(conv_stores)}개")
        
        # 결과 요약
        self.stdout.write(self.style.SUCCESS(f"""
{'=' * 60}
📊 조회 결과 요약
{'=' * 60}
  - 조회한 행정동: {len(dongs_to_query)}개
  - 전체 상가: {len(total_stores)}개
  - 편의점: {len(convenience_stores)}개
{'=' * 60}
        """))
        
        # 편의점 목록 출력 (verbose 모드)
        if verbose and convenience_stores:
            self.stdout.write("\n📋 편의점 목록:")
            for i, store in enumerate(convenience_stores[:20], 1):
                name = store.get('bizesNm', '이름없음')
                addr = store.get('rdnmAdr', '') or store.get('lnoAdr', '주소없음')
                self.stdout.write(f"   {i}. {name} | {addr}")
            
            if len(convenience_stores) > 20:
                self.stdout.write(f"   ... 외 {len(convenience_stores) - 20}개")
        
        return convenience_stores
    
    def fetch_stores_in_dong(self, api_key, dong_code, verbose=False):
        """행정동 코드로 상가 목록 조회"""
        all_stores = []
        page_no = 1
        num_of_rows = 1000  # 한 페이지당 최대 1000개
        
        while True:
            params = {
                'serviceKey': api_key,
                'pageNo': str(page_no),
                'numOfRows': str(num_of_rows),
                'divId': 'adongCd',  # 행정동 코드 기준
                'key': dong_code,
                'type': 'json'
            }
            
            try:
                url = f"{self.BASE_URL}/storeListInDong"
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # 응답 구조 확인
                if verbose:
                    self.stdout.write(f"   [페이지 {page_no}] 응답 코드: {data.get('header', {}).get('resultCode')}")
                
                # 에러 체크
                result_code = data.get('header', {}).get('resultCode')
                if result_code != '00':
                    result_msg = data.get('header', {}).get('resultMsg', '알 수 없는 오류')
                    self.stdout.write(self.style.ERROR(f"   API 오류: {result_msg}"))
                    break
                
                # 데이터 추출
                body = data.get('body', {})
                items = body.get('items', [])
                
                if not items:
                    break
                
                all_stores.extend(items)
                
                # 다음 페이지 확인
                total_count = int(body.get('totalCount', 0))
                if page_no * num_of_rows >= total_count:
                    break
                
                page_no += 1
                
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f"   요청 오류: {e}"))
                break
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f"   JSON 파싱 오류: {e}"))
                if verbose:
                    self.stdout.write(f"   응답: {response.text[:500]}")
                break
        
        return all_stores
