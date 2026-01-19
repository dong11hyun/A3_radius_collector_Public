"""
서울시 담배소매업 인허가 정보 수집
- Open API에서 페이지네이션으로 전체 데이터 수집
- 영업중인 담배소매업만 필터링하여 PostgreSQL에 저장
- TM 좌표를 WGS84(위도/경도)로 변환
- --gu 옵션으로 대상 구 지정 가능
"""
import os
import requests
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from pyproj import Transformer
from stores.models import TobaccoRetailLicense
from .gu_codes import get_tobacco_service, list_supported_gu


# 좌표계 변환기: Korea 1985 / Central Belt (EPSG:5174) -> WGS84 (EPSG:4326)
# 서울시 OpenAPI의 X, Y 좌표는 EPSG:5174 좌표계 사용
transformer = Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)


def convert_tm_to_wgs84(x, y):
    """TM 좌표를 WGS84 위도/경도로 변환"""
    try:
        x_float = float(x)
        y_float = float(y)
        lon, lat = transformer.transform(x_float, y_float)
        return lat, lon  # latitude, longitude
    except (ValueError, TypeError):
        return None, None


class Command(BaseCommand):
    help = '서울시 담배소매업 인허가 정보 수집 (--gu 옵션으로 대상 구 지정)'

    # API 설정 (.env에서 로드)
    API_KEY = os.environ.get('SEOUL_OPENAPI_KEY', '')
    BASE_URL = 'http://openAPI.seoul.go.kr:8088'
    PAGE_SIZE = 1000  # 한 번에 가져올 최대 건수
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--gu',
            type=str,
            default='영등포구',
            help=f'대상 구 (기본: 영등포구). 지원: {", ".join(list_supported_gu())}'
        )
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
        parser.add_argument(
            '--all',
            action='store_true',
            help='폐업 포함 전체 데이터 저장 (기본값: 영업중만)',
        )

    def handle(self, *args, **options):
        target_gu = options['gu']
        dry_run = options['dry_run']
        clear = options['clear']
        include_all = options['all']
        
        # 서비스명 동적 조회
        try:
            service_name = get_tobacco_service(target_gu)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return
        
        # 서비스명을 인스턴스 변수로 저장 (메서드에서 사용)
        self.service_name = service_name
        
        if clear and not dry_run:
            deleted_count = TobaccoRetailLicense.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f'기존 담배소매업 데이터 {deleted_count}건 삭제'))
        
        self.stdout.write(self.style.SUCCESS(f'=== 서울시 {target_gu} 담배소매업 인허가 정보 수집 시작 ==='))
        self.stdout.write(f'서비스명: {service_name}')
        
        # 1. 전체 데이터 수 확인
        total_count = self.get_total_count()
        if total_count == 0:
            self.stdout.write(self.style.ERROR('데이터를 가져올 수 없습니다.'))
            return
        
        self.stdout.write(f'총 담배소매업 데이터: {total_count}건')
        
        # 2. 페이지네이션으로 전체 데이터 수집
        all_stores = []
        start_index = 1
        
        while start_index <= total_count:
            end_index = min(start_index + self.PAGE_SIZE - 1, total_count)
            self.stdout.write(f'데이터 조회 중... ({start_index} ~ {end_index})')
            
            rows = self.fetch_data(start_index, end_index)
            if rows:
                if include_all:
                    # 모든 데이터 포함
                    all_stores.extend(rows)
                    self.stdout.write(f'  → {len(rows)}건 추가 (누적: {len(all_stores)}건)')
                else:
                    # 영업중인 것만 필터링 (TRDSTATENM이 '영업' 포함 또는 TRDSTATEGBN이 '01')
                    active_stores = [
                        row for row in rows 
                        if row.get('TRDSTATEGBN', '') == '01' or '영업' in row.get('TRDSTATENM', '')
                    ]
                    all_stores.extend(active_stores)
                    self.stdout.write(f'  → 영업중 {len(active_stores)}건 발견 (누적: {len(all_stores)}건)')
            
            start_index += self.PAGE_SIZE
        
        status_msg = '전체' if include_all else '영업중'
        self.stdout.write(self.style.SUCCESS(f'\n총 {status_msg} 담배소매업 데이터: {len(all_stores)}건'))
        
        # 3. DB에 저장
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] DB 저장 생략'))
            self.print_sample_data(all_stores[:10])
        else:
            saved_count, updated_count = self.save_to_db(all_stores)
            self.stdout.write(self.style.SUCCESS(f'\nDB 저장 완료: 신규 {saved_count}건, 업데이트 {updated_count}건'))
        
        self.stdout.write(self.style.SUCCESS('=== 수집 완료 ==='))

    def get_total_count(self):
        """전체 데이터 수 조회"""
        url = f'{self.BASE_URL}/{self.API_KEY}/json/{self.service_name}/1/1/'
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if self.service_name in data:
                return data[self.service_name]['list_total_count']
            else:
                self.stdout.write(self.style.ERROR(f'응답 오류: {data}'))
                return 0
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'API 호출 오류: {e}'))
            return 0

    def fetch_data(self, start_index, end_index):
        """데이터 조회"""
        url = f'{self.BASE_URL}/{self.API_KEY}/json/{self.service_name}/{start_index}/{end_index}/'
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if self.service_name in data:
                return data[self.service_name].get('row', [])
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
            
            # 원본 TM 좌표
            x_coord = store.get('X', '')
            y_coord = store.get('Y', '')
            
            # 공백 제거 (API에서 좌표값에 공백이 포함될 수 있음)
            if x_coord:
                x_coord = x_coord.strip()
            if y_coord:
                y_coord = y_coord.strip()
            
            # TM 좌표를 WGS84(위도/경도)로 변환
            latitude, longitude = None, None
            location = None
            
            if x_coord and y_coord:
                latitude, longitude = convert_tm_to_wgs84(x_coord, y_coord)
                if latitude and longitude:
                    location = Point(longitude, latitude, srid=4326)  # Point(x=lon, y=lat)
            
            defaults = {
                'opnsfteamcode': store.get('OPNSFTEAMCODE', ''),
                'bplcnm': store.get('BPLCNM', ''),
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
                'sitearea': store.get('SITEAREA', ''),
                'x': x_coord,
                'y': y_coord,
                'latitude': latitude,
                'longitude': longitude,
                'location': location,
                'lastmodts': store.get('LASTMODTS', ''),
                'updategbn': store.get('UPDATEGBN', ''),
                'updatedt': store.get('UPDATEDT', ''),
                'uptaenm': store.get('UPTAENM', ''),
                'asgnymd': store.get('ASGNYMD', ''),
                'mwsrnm': store.get('MWSRNM', ''),
            }
            
            obj, created = TobaccoRetailLicense.objects.update_or_create(
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
            self.stdout.write(f"    주소: {store.get('RDNWHLADDR', store.get('SITEWHLADDR', 'N/A'))}")
            self.stdout.write(f"    인허가일자: {store.get('APVPERMYMD', 'N/A')}")
            self.stdout.write(f"    지정일자: {store.get('ASGNYMD', 'N/A')}")
            self.stdout.write(f"    전화번호: {store.get('SITETEL', 'N/A')}")
