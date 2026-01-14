"""
서울시 영등포구 휴게음식점 인허가 정보 수집 (편의점만)
- Open API에서 페이지네이션으로 전체 데이터 수집
- 편의점만 필터링하여 PostgreSQL에 저장
"""
import requests
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from stores.models import SeoulRestaurantLicense


class Command(BaseCommand):
    help = '서울시 영등포구 휴게음식점 인허가 정보에서 편의점만 수집하여 DB에 저장'

    # API 설정
    API_KEY = '78734e43486a6f6e37377950477350'
    SERVICE_NAME = 'LOCALDATA_072405_YD'
    BASE_URL = 'http://openAPI.seoul.go.kr:8088'
    PAGE_SIZE = 1000  # 한 번에 가져올 최대 건수
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 DB 저장 없이 결과만 확인',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='기존 데이터 삭제 후 새로 저장',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clear = options['clear']
        
        if clear and not dry_run:
            deleted_count = SeoulRestaurantLicense.objects.filter(uptaenm='편의점').delete()[0]
            self.stdout.write(self.style.WARNING(f'기존 편의점 데이터 {deleted_count}건 삭제'))
        
        self.stdout.write(self.style.SUCCESS('=== 서울시 영등포구 휴게음식점 인허가 정보 수집 시작 ==='))
        
        # 1. 전체 데이터 수 확인
        total_count = self.get_total_count()
        if total_count == 0:
            self.stdout.write(self.style.ERROR('데이터를 가져올 수 없습니다.'))
            return
        
        self.stdout.write(f'총 휴게음식점 데이터: {total_count}건')
        
        # 2. 페이지네이션으로 전체 데이터 수집 (편의점만 필터)
        all_convenience_stores = []
        start_index = 1
        
        while start_index <= total_count:
            end_index = min(start_index + self.PAGE_SIZE - 1, total_count)
            self.stdout.write(f'데이터 조회 중... ({start_index} ~ {end_index})')
            
            rows = self.fetch_data(start_index, end_index)
            if rows:
                # 편의점 + 영업중인 것만 필터링
                convenience_stores = [
                    row for row in rows 
                    if row.get('UPTAENM', '').strip() == '편의점'
                    and row.get('TRDSTATENM', '').strip() == '영업/정상'
                ]
                all_convenience_stores.extend(convenience_stores)
                self.stdout.write(f'  → 영업중 편의점 {len(convenience_stores)}건 발견 (누적: {len(all_convenience_stores)}건)')
            
            start_index += self.PAGE_SIZE
        
        self.stdout.write(self.style.SUCCESS(f'\n총 편의점 데이터: {len(all_convenience_stores)}건'))
        
        # 3. DB에 저장
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] DB 저장 생략'))
            self.print_sample_data(all_convenience_stores[:10])
        else:
            saved_count, updated_count = self.save_to_db(all_convenience_stores)
            self.stdout.write(self.style.SUCCESS(f'\nDB 저장 완료: 신규 {saved_count}건, 업데이트 {updated_count}건'))
        
        self.stdout.write(self.style.SUCCESS('=== 수집 완료 ==='))

    def get_total_count(self):
        """전체 데이터 수 조회"""
        url = f'{self.BASE_URL}/{self.API_KEY}/json/{self.SERVICE_NAME}/1/1/'
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if self.SERVICE_NAME in data:
                return data[self.SERVICE_NAME]['list_total_count']
            else:
                self.stdout.write(self.style.ERROR(f'응답 오류: {data}'))
                return 0
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'API 호출 오류: {e}'))
            return 0

    def fetch_data(self, start_index, end_index):
        """데이터 조회"""
        url = f'{self.BASE_URL}/{self.API_KEY}/json/{self.SERVICE_NAME}/{start_index}/{end_index}/'
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if self.SERVICE_NAME in data:
                return data[self.SERVICE_NAME].get('row', [])
            return []
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'데이터 조회 오류: {e}'))
            return []

    def save_to_db(self, stores):
        """DB에 저장 (update_or_create 사용)"""
        saved_count = 0
        updated_count = 0
        
        for store in stores:
            mgtno = store.get('MGTNO', '')
            if not mgtno:
                continue
            
            # 좌표 변환 (TM -> WGS84 변환은 별도 처리 필요, 일단 원본 저장)
            x_coord = store.get('X', '')
            y_coord = store.get('Y', '')
            location = None
            
            # X, Y 좌표가 있으면 Point 생성 시도 (원본은 TM 좌표이므로 주의)
            # 실제 사용 시 좌표계 변환 필요
            
            defaults = {
                'opnsfteamcode': store.get('OPNSFTEAMCODE', ''),
                'bplcnm': store.get('BPLCNM', ''),
                'uptaenm': store.get('UPTAENM', ''),
                'sntuptaenm': store.get('SNTUPTAENM', ''),
                'trdstategbn': store.get('TRDSTATEGBN', ''),
                'trdstatenm': store.get('TRDSTATENM', ''),
                'dtlstategbn': store.get('DTLSTATEGBN', ''),
                'dtlstatenm': store.get('DTLSTATENM', ''),
                'apvpermymd': store.get('APVPERMYMD', ''),
                'apvcancelymd': store.get('APVCANCELYMD', ''),
                'dcbymd': store.get('DCBYMD', ''),
                'clgstdt': store.get('CLGSTDT', ''),
                'clgenddt': store.get('CLGENDDT', ''),
                'ropnymd': store.get('ROPNYMD', ''),
                'sitewhladdr': store.get('SITEWHLADDR', ''),
                'rdnwhladdr': store.get('RDNWHLADDR', ''),
                'sitepostno': store.get('SITEPOSTNO', ''),
                'rdnpostno': store.get('RDNPOSTNO', ''),
                'sitetel': store.get('SITETEL', ''),
                'homepage': store.get('HOMEPAGE', ''),
                'x': x_coord,
                'y': y_coord,
                'location': location,
                'sitearea': store.get('SITEAREA', ''),
                'faciltotscp': store.get('FACILTOTSCP', ''),
                'totepnum': store.get('TOTEPNUM', ''),
                'maneipcnt': store.get('MANEIPCNT', ''),
                'wmeipcnt': store.get('WMEIPCNT', ''),
                'bdngownsenm': store.get('BDNGOWNSENM', ''),
                'multusnupsoyn': store.get('MULTUSNUPSOYN', ''),
                'lastmodts': store.get('LASTMODTS', ''),
                'updategbn': store.get('UPDATEGBN', ''),
                'updatedt': store.get('UPDATEDT', ''),
            }
            
            obj, created = SeoulRestaurantLicense.objects.update_or_create(
                mgtno=mgtno,
                defaults=defaults
            )
            
            if created:
                saved_count += 1
            else:
                updated_count += 1
        
        return saved_count, updated_count

    def print_sample_data(self, stores):
        """샘플 데이터 출력"""
        self.stdout.write('\n--- 샘플 데이터 (최대 10건) ---')
        for idx, store in enumerate(stores, 1):
            self.stdout.write(f"\n[{idx}] {store.get('BPLCNM', 'N/A')}")
            self.stdout.write(f"    영업상태: {store.get('TRDSTATENM', 'N/A')} ({store.get('DTLSTATENM', '')})")
            self.stdout.write(f"    업태: {store.get('UPTAENM', 'N/A')}")
            self.stdout.write(f"    주소: {store.get('RDNWHLADDR', store.get('SITEWHLADDR', 'N/A'))}")
            self.stdout.write(f"    인허가일자: {store.get('APVPERMYMD', 'N/A')}")