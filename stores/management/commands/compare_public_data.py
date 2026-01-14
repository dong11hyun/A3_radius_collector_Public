# stores/management/commands/compare_public_data.py
"""
공공데이터와 카카오맵 데이터 비교하여 폐업 매장 탐지
공공데이터에서 폐업인데 카카오맵에 영업으로 나오는 매장 발견
"""

import csv
from difflib import SequenceMatcher
from django.core.management.base import BaseCommand
from stores.models import NearbyStore


class Command(BaseCommand):
    help = '공공데이터와 카카오맵 데이터 비교하여 폐업 매장 탐지'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=str,
            required=True,
            help='공공데이터 CSV 파일 경로'
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.6,
            help='매칭 임계값 (기본: 0.6, 범위: 0.0~1.0)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='저장하지 않고 결과만 출력'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='상세 정보 출력'
        )

    def similarity(self, a, b):
        """두 문자열의 유사도 계산 (0.0 ~ 1.0)"""
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def normalize_address(self, address):
        """주소 정규화 (비교용)"""
        if not address:
            return ''
        # 공백, 특수문자 제거
        address = address.replace(' ', '').replace('-', '').replace(',', '')
        return address

    def load_closed_stores_from_csv(self, csv_path):
        """CSV에서 폐업 편의점 목록 로드"""
        closed_stores = []
        encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    
                    for row in reader:
                        # 편의점만
                        business_type = (
                            row.get('상권업종중분류명', '') or 
                            row.get('업종명', '')
                        )
                        if '편의점' not in business_type:
                            continue
                        
                        # 폐업 상태만
                        status = (
                            row.get('상권업종상태', '') or 
                            row.get('영업상태', '')
                        )
                        if '폐업' not in status:
                            continue
                        
                        # 영등포구만
                        address = row.get('지번주소', '') or row.get('주소', '')
                        road_address = row.get('도로명주소', '')
                        
                        if '영등포구' not in address and '영등포구' not in road_address:
                            continue
                        
                        closed_stores.append({
                            'name': row.get('상호명', '') or row.get('상가명', ''),
                            'address': address,
                            'road_address': road_address,
                            'status': status
                        })
                    
                    break
                    
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"CSV 로드 오류: {e}"))
                return []
        
        return closed_stores

    def handle(self, *args, **options):
        csv_path = options['csv']
        threshold = options['threshold']
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(f"매칭 임계값: {threshold}")
        
        # 공공데이터에서 폐업 편의점 로드
        closed_public = self.load_closed_stores_from_csv(csv_path)
        self.stdout.write(f"공공데이터 폐업 편의점: {len(closed_public)}개")
        
        if not closed_public:
            self.stdout.write(self.style.WARNING("폐업 편의점 데이터가 없습니다."))
            return
        
        # 카카오맵 편의점 데이터
        kakao_stores = NearbyStore.objects.filter(category='편의점')
        self.stdout.write(f"카카오맵 편의점: {kakao_stores.count()}개")
        
        found_count = 0
        matches = []
        
        for public_store in closed_public:
            best_match = None
            best_score = 0.0
            
            public_addr_norm = self.normalize_address(public_store['address'])
            public_road_addr_norm = self.normalize_address(public_store['road_address'])
            public_name = public_store['name']
            
            for kakao_store in kakao_stores:
                kakao_addr_norm = self.normalize_address(kakao_store.address)
                
                # 주소 유사도 계산
                addr_score = max(
                    self.similarity(public_addr_norm, kakao_addr_norm),
                    self.similarity(public_road_addr_norm, kakao_addr_norm)
                )
                
                # 상호명 유사도 계산
                name_score = self.similarity(public_name, kakao_store.name)
                
                # 가중 평균 (주소 70%, 상호명 30%)
                total_score = addr_score * 0.7 + name_score * 0.3
                
                if total_score > best_score:
                    best_score = total_score
                    best_match = kakao_store
            
            if best_score >= threshold:
                matches.append({
                    'kakao': best_match,
                    'public': public_store,
                    'score': best_score
                })
                found_count += 1
                
                self.stdout.write(f"\n🔍 매칭 발견 (유사도: {best_score:.2f})")
                self.stdout.write(f"  카카오: {best_match.name} | {best_match.address}")
                self.stdout.write(f"  공공DB: {public_store['name']} | {public_store['address']} | {public_store['status']}")
        
        # 결과 요약
        self.stdout.write(self.style.SUCCESS(f"\n--- 비교 결과 ---"))
        self.stdout.write(f"총 {found_count}개의 폐업 의심 매장 발견")
        
        if matches and not dry_run:
            self.stdout.write(self.style.WARNING(
                "\n⚠️ 위 매장들은 공공데이터에서 '폐업'이지만 카카오맵에 표시되어 있습니다."
            ))
            self.stdout.write("제보하거나 확인이 필요합니다.")
        
        if verbose and not matches:
            self.stdout.write(self.style.SUCCESS("\n✅ 폐업 의심 매장이 없습니다!"))
