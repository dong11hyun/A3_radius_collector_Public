# stores/management/commands/load_public_data.py
"""
공공데이터포탈 CSV 파일을 DB에 로드하는 커맨드
소상공인시장진흥공단_상가(상권)정보 데이터 활용
"""

import csv
from django.core.management.base import BaseCommand


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

    def handle(self, *args, **options):
        csv_path = options['csv']
        target_gu = options['gu']
        dry_run = options['dry_run']
        
        self.stdout.write(f"CSV 파일 로드 중: {csv_path}")
        self.stdout.write(f"필터링 대상: {target_gu}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run 모드: DB에 저장하지 않음"))
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        closed_count = 0
        
        # CSV 인코딩: 공공데이터는 보통 cp949 또는 utf-8
        encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    
                    # 컬럼 확인
                    if reader.fieldnames:
                        self.stdout.write(f"감지된 컬럼: {len(reader.fieldnames)}개")
                        self.stdout.write(f"인코딩: {encoding}")
                    
                    for row in reader:
                        # 다양한 컬럼명 대응
                        business_type = (
                            row.get('상권업종중분류명', '') or 
                            row.get('업종명', '') or
                            row.get('업종분류명', '')
                        )
                        
                        # 편의점 업종만 필터링
                        if '편의점' not in business_type:
                            skipped_count += 1
                            continue
                        
                        # 주소 가져오기
                        address = (
                            row.get('지번주소', '') or 
                            row.get('주소', '') or
                            row.get('소재지주소', '')
                        )
                        road_address = (
                            row.get('도로명주소', '') or 
                            row.get('도로명', '')
                        )
                        
                        # 대상 구 필터링
                        if target_gu not in address and target_gu not in road_address:
                            skipped_count += 1
                            continue
                        
                        # 사업자등록번호 또는 고유번호
                        business_number = (
                            row.get('사업자등록번호', '') or 
                            row.get('상가업소번호', '') or
                            row.get('번호', '')
                        )
                        
                        if not business_number:
                            skipped_count += 1
                            continue
                        
                        # 영업 상태
                        status = (
                            row.get('상권업종상태', '') or 
                            row.get('영업상태', '') or
                            row.get('상태', '영업')
                        )
                        
                        store_name = (
                            row.get('상호명', '') or 
                            row.get('상가명', '') or
                            row.get('사업장명', '')
                        )
                        
                        if '폐업' in status:
                            closed_count += 1
                        
                        if not dry_run:
                            # 실제 DB 저장은 PublicDataStore 모델이 필요
                            # 여기서는 모델이 없으므로 통계만 출력
                            pass
                        
                        created_count += 1
                    
                    break  # 성공하면 루프 종료
                    
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                self.stdout.write(self.style.ERROR(f"파일을 찾을 수 없습니다: {csv_path}"))
                return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"오류: {e}"))
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
