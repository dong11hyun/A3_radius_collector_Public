# stores/management/commands/deduplicate_stores.py
"""
영등포구 다이소 주변 편의점 데이터 중복 제거 커맨드
여러 다이소에서 중복 발견된 동일 편의점을 place_id 기준으로 정리
"""

from django.core.management.base import BaseCommand
from stores.models import YeongdeungpoConvenience


class Command(BaseCommand):
    help = '영등포구 다이소 주변 편의점 데이터 중복 제거 및 통계 출력'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='상세 정보 출력'
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        
        # 영등포구 편의점 데이터 대상
        convenience_stores = YeongdeungpoConvenience.objects.all()
        total_count = convenience_stores.count()
        
        self.stdout.write(f"총 {total_count}개의 편의점 데이터 확인 중...")
        
        # place_id 기준으로 그룹화
        unique_stores = {}
        
        for store in convenience_stores:
            place_id = store.place_id
            
            if place_id not in unique_stores:
                unique_stores[place_id] = {
                    'name': store.name,
                    'address': store.address,
                    'phone': store.phone,
                    'location': store.location,
                    'daisos': [store.base_daiso],
                    'min_distance': store.distance,
                }
            else:
                # 동일 place_id가 여러 다이소에서 발견된 경우
                existing = unique_stores[place_id]
                
                if store.base_daiso not in existing['daisos']:
                    existing['daisos'].append(store.base_daiso)
                
                # 최소 거리 갱신
                if store.distance < existing['min_distance']:
                    existing['min_distance'] = store.distance
        
        unique_count = len(unique_stores)
        duplicate_count = total_count - unique_count
        
        self.stdout.write(self.style.SUCCESS(f"\n📊 중복 분석 결과:"))
        self.stdout.write(f"  - 원본 데이터: {total_count}개")
        self.stdout.write(f"  - 고유 편의점: {unique_count}개")
        self.stdout.write(f"  - 중복 데이터: {duplicate_count}개 ({duplicate_count/total_count*100:.1f}%)")
        
        # 여러 다이소에서 발견된 편의점 목록
        multi_daiso_stores = {k: v for k, v in unique_stores.items() if len(v['daisos']) > 1}
        
        if multi_daiso_stores:
            self.stdout.write(f"\n🔗 여러 다이소에서 발견된 편의점: {len(multi_daiso_stores)}개")
            
            if verbose:
                for place_id, data in list(multi_daiso_stores.items())[:10]:  # 최대 10개만 출력
                    self.stdout.write(f"  - {data['name']}")
                    self.stdout.write(f"    발견된 다이소: {', '.join(data['daisos'])}")
        
        # 주요 편의점 브랜드별 통계
        brand_stats = {}
        for place_id, data in unique_stores.items():
            name = data['name']
            
            # 브랜드 식별
            brand = '기타'
            if 'CU' in name or 'cu' in name.lower():
                brand = 'CU'
            elif 'GS25' in name or 'gs25' in name.lower():
                brand = 'GS25'
            elif '세븐일레븐' in name or '7-Eleven' in name or '711' in name:
                brand = '세븐일레븐'
            elif '이마트24' in name or 'emart24' in name.lower():
                brand = '이마트24'
            elif '미니스톱' in name:
                brand = '미니스톱'
            
            brand_stats[brand] = brand_stats.get(brand, 0) + 1
        
        self.stdout.write(f"\n🏪 브랜드별 분포:")
        for brand, count in sorted(brand_stats.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  - {brand}: {count}개 ({count/unique_count*100:.1f}%)")
        
        self.stdout.write(self.style.SUCCESS("\n중복 분석 완료!"))
        self.stdout.write("(참고: NearbyStore 테이블은 place_id가 unique로 설정되어 있어 실제 중복은 발생하지 않음)")
