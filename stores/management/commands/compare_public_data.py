# stores/management/commands/compare_public_data.py
"""
공공데이터와 카카오맵 데이터 비교하여 폐업 매장 탐지
공공데이터에서 폐업인데 카카오맵에 영업으로 나오는 매장 발견

CSV 헤더가 'Column1', 'Column2' 형식일 경우 인덱스 기반 매핑 사용
"""

import csv
from difflib import SequenceMatcher
from django.core.management.base import BaseCommand
from stores.models import YeongdeungpoConvenience


# 공공데이터 표준 컬럼 매핑 (0-indexed)
PUBLIC_DATA_COLUMNS = {
    '상가업소번호': 0,
    '상호명': 1,
    '상권업종중분류명': 6,
    '상권업종소분류명': 8,
    '시군구명': 14,
    '지번주소': 24,
    '도로명주소': 31,
    '경도': 37,
    '위도': 38,
}


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

    def get_value(self, row, field_name, use_index=False):
        """컬럼에서 값을 가져옴"""
        if use_index:
            idx = PUBLIC_DATA_COLUMNS.get(field_name)
            if idx is not None and idx < len(row):
                return row[idx].strip() if row[idx] else ''
            return ''
        else:
            return row.get(field_name, '').strip() if row.get(field_name) else ''

    def load_public_stores_from_csv(self, csv_path, target_gu='영등포구'):
        """CSV에서 영등포구 편의점 목록 로드 (영업 중인 매장)"""
        public_stores = []
        encodings = ['cp949', 'utf-8', 'euc-kr', 'utf-8-sig']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.reader(f)
                    
                    # 헤더 읽기
                    header = next(reader)
                    use_index = header[0].lower().startswith('column')
                    
                    if use_index:
                        self.stdout.write(self.style.WARNING(
                            "⚠️ 일반 헤더 감지 - 인덱스 기반 매핑 사용"
                        ))
                    
                    for row in reader:
                        if len(row) < 15:
                            continue
                        
                        # 편의점만 (소분류명에 '편의점' 있음)
                        business_type_small = self.get_value(row, '상권업종소분류명', use_index)
                        business_type_mid = self.get_value(row, '상권업종중분류명', use_index)
                        
                        if '편의점' not in business_type_small and '편의점' not in business_type_mid:
                            continue
                        
                        # 영등포구만
                        gu_name = self.get_value(row, '시군구명', use_index)
                        address = self.get_value(row, '지번주소', use_index)
                        road_address = self.get_value(row, '도로명주소', use_index)
                        
                        if target_gu not in gu_name and target_gu not in address and target_gu not in road_address:
                            continue
                        
                        store_name = self.get_value(row, '상호명', use_index)
                        
                        # 공공데이터는 영업 중인 매장만 포함 (폐업 데이터는 별도)
                        public_stores.append({
                            'name': store_name,
                            'address': address,
                            'road_address': road_address,
                            'business_number': self.get_value(row, '상가업소번호', use_index),
                        })
                    
                    break
                    
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"CSV 로드 오류: {e}"))
                return []
        
        return public_stores

    def handle(self, *args, **options):
        csv_path = options['csv']
        threshold = options['threshold']
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(f"매칭 임계값: {threshold}")
        
        # 공공데이터에서 편의점 로드
        public_stores = self.load_public_stores_from_csv(csv_path)
        self.stdout.write(f"공공데이터 편의점: {len(public_stores)}개")
        
        if not public_stores:
            self.stdout.write(self.style.WARNING("공공데이터 편의점이 없습니다."))
            return
        
        # 카카오맵 편의점 데이터 (YeongdeungpoConvenience 사용)
        kakao_stores = list(YeongdeungpoConvenience.objects.all())
        self.stdout.write(f"카카오맵 편의점: {len(kakao_stores)}개")
        
        # 1. 공공데이터에만 있는 매장 찾기 (카카오에 없음)
        only_in_public = []
        matched_kakao_ids = set()
        
        for public_store in public_stores:
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
            
            if best_score >= threshold and best_match:
                matched_kakao_ids.add(best_match.id)
                if verbose:
                    self.stdout.write(f"✓ 매칭: {public_name} ↔ {best_match.name} (유사도: {best_score:.2f})")
            else:
                only_in_public.append(public_store)
                if verbose:
                    self.stdout.write(f"✗ 미매칭(공공데이터만): {public_name} | {public_store['address']}")
        
        # 2. 카카오에만 있는 매장 찾기 (공공데이터에 없음)
        only_in_kakao = [s for s in kakao_stores if s.id not in matched_kakao_ids]
        
        # 결과 요약
        self.stdout.write(self.style.SUCCESS(f"""
--- 비교 결과 ---
  공공데이터: {len(public_stores)}개
  카카오맵: {len(kakao_stores)}개
  매칭됨: {len(matched_kakao_ids)}개
  공공데이터에만 있음: {len(only_in_public)}개
  카카오맵에만 있음: {len(only_in_kakao)}개
        """))
        
        if only_in_public:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️ 공공데이터에만 있는 편의점 {len(only_in_public)}개:"
            ))
            self.stdout.write("   (카카오맵에서 찾을 수 없거나 폐업했을 수 있음)")
            for i, store in enumerate(only_in_public[:10]):  # 상위 10개만 출력
                self.stdout.write(f"   {i+1}. {store['name']} | {store['address']}")
            if len(only_in_public) > 10:
                self.stdout.write(f"   ... 외 {len(only_in_public) - 10}개")
        
        if only_in_kakao:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️ 카카오맵에만 있는 편의점 {len(only_in_kakao)}개:"
            ))
            self.stdout.write("   (공공데이터에 등록되지 않았거나 신규 개업)")
            for i, store in enumerate(only_in_kakao[:10]):  # 상위 10개만 출력
                self.stdout.write(f"   {i+1}. {store.name} | {store.address}")
            if len(only_in_kakao) > 10:
                self.stdout.write(f"   ... 외 {len(only_in_kakao) - 10}개")

