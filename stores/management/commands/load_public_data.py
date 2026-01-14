# stores/management/commands/load_public_data.py
"""
공공데이터포탈 CSV 파일을 DB에 로드하는 커맨드
소상공인시장진흥공단_상가(상권)정보 데이터 활용

CSV 헤더가 'Column1', 'Column2' 형식일 경우 인덱스 기반 매핑 사용
"""

import csv
from django.core.management.base import BaseCommand


# 공공데이터 표준 컬럼 매핑 (0-indexed)
# 소상공인시장진흥공단_상가(상권)정보 기준
PUBLIC_DATA_COLUMNS = {
    '상가업소번호': 0,
    '상호명': 1,
    '지점명': 2,
    '상권업종대분류코드': 3,
    '상권업종대분류명': 4,
    '상권업종중분류코드': 5,
    '상권업종중분류명': 6,
    '상권업종소분류코드': 7,
    '상권업종소분류명': 8,
    '표준산업분류코드': 9,
    '표준산업분류명': 10,
    '시도코드': 11,
    '시도명': 12,
    '시군구코드': 13,
    '시군구명': 14,
    '행정동코드': 15,
    '행정동명': 16,
    '법정동코드': 17,
    '법정동명': 18,
    '지번코드': 19,
    '대지구분코드': 20,
    '대지구분명': 21,
    '지번본번지': 22,
    '지번부번지': 23,
    '지번주소': 24,
    '도로명코드': 25,
    '도로명': 26,
    '건물본번지': 27,
    '건물부번지': 28,
    '건물관리번호': 29,
    '건물명': 30,
    '도로명주소': 31,
    '구우편번호': 32,
    '신우편번호': 33,
    '동정보': 34,
    '층정보': 35,
    '호정보': 36,
    '경도': 37,
    '위도': 38,
}


class Command(BaseCommand):
    help = '공공데이터포탈 CSV 파일을 DB에 로드합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=str,
            required=True,
            help='CSV 파일 경로'
        )
        parser.add_argument(
            '--gu',
            type=str,
            default='영등포구',
            help='필터링할 구 이름 (기본: 영등포구)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='저장하지 않고 결과만 출력'
        )

    def get_value(self, row, field_name, use_index=False):
        """컬럼에서 값을 가져옴. use_index=True면 인덱스 기반 접근"""
        if use_index:
            idx = PUBLIC_DATA_COLUMNS.get(field_name)
            if idx is not None and idx < len(row):
                return row[idx].strip() if row[idx] else ''
            return ''
        else:
            return row.get(field_name, '').strip() if row.get(field_name) else ''

    def handle(self, *args, **options):
        csv_path = options['csv']
        target_gu = options['gu']
        dry_run = options['dry_run']
        
        self.stdout.write(f"CSV 파일 로드 중: {csv_path}")
        self.stdout.write(f"필터링 대상: {target_gu}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run 모드: DB에 저장하지 않음"))
        
        created_count = 0
        skipped_count = 0
        closed_count = 0
        
        # CSV 인코딩: 공공데이터는 보통 cp949 또는 utf-8
        encodings = ['cp949', 'utf-8', 'euc-kr', 'utf-8-sig']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.reader(f)
                    
                    # 첫 번째 행 (헤더) 읽기
                    header = next(reader)
                    self.stdout.write(f"감지된 컬럼: {len(header)}개")
                    self.stdout.write(f"인코딩: {encoding}")
                    
                    # 헤더가 'Column1', 'Column2' 패턴인지 확인
                    use_index = header[0].lower().startswith('column')
                    
                    if use_index:
                        self.stdout.write(self.style.WARNING(
                            "⚠️ 일반 헤더 감지 (Column1, Column2...) - 인덱스 기반 매핑 사용"
                        ))
                    
                    for row in reader:
                        if len(row) < 15:  # 최소 필요 컬럼 수
                            skipped_count += 1
                            continue
                        
                        # 업종 확인 (소분류명에 '편의점'이 있음, 중분류는 '종합 소매')
                        business_type_small = self.get_value(row, '상권업종소분류명', use_index)
                        business_type_mid = self.get_value(row, '상권업종중분류명', use_index)
                        business_type_std = self.get_value(row, '표준산업분류명', use_index)
                        
                        # 편의점 업종만 필터링 (소분류, 중분류, 표준분류 중 하나에 '편의점' 포함)
                        if '편의점' not in business_type_small and '편의점' not in business_type_mid and '편의점' not in business_type_std:
                            skipped_count += 1
                            continue
                        
                        # 시군구명으로 대상 구 필터링 (더 정확함)
                        gu_name = self.get_value(row, '시군구명', use_index)
                        
                        # 시군구명에 없으면 주소에서 확인
                        if target_gu not in gu_name:
                            address = self.get_value(row, '지번주소', use_index)
                            road_address = self.get_value(row, '도로명주소', use_index)
                            if target_gu not in address and target_gu not in road_address:
                                skipped_count += 1
                                continue
                        
                        # 상가업소번호 확인
                        business_number = self.get_value(row, '상가업소번호', use_index)
                        if not business_number:
                            skipped_count += 1
                            continue
                        
                        # 상호명
                        store_name = self.get_value(row, '상호명', use_index)
                        
                        # 공공데이터에는 영업상태 컬럼이 없음 (모두 영업 중으로 간주)
                        # 폐업 데이터는 별도 파일 또는 다른 방식으로 제공됨
                        
                        created_count += 1
                    
                    break  # 성공하면 루프 종료
                    
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                self.stdout.write(self.style.ERROR(f"파일을 찾을 수 없습니다: {csv_path}"))
                return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"오류: {e}"))
                import traceback
                traceback.print_exc()
                return
        
        # 결과 출력
        self.stdout.write(self.style.SUCCESS(f"""
📊 공공데이터 분석 완료!
  - 편의점 데이터: {created_count}개
  - 폐업 상태: {closed_count}개
  - 스킵: {skipped_count}개
        """))
        
        if closed_count > 0:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️ {target_gu} 폐업 편의점 {closed_count}개 발견!"
            ))
            self.stdout.write("compare_public_data 커맨드로 카카오맵 데이터와 비교해보세요.")
