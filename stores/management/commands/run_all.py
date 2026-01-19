# stores/management/commands/run_all.py
"""
구 단위 전체 파이프라인 실행 커맨드

사용법:
    python manage.py run_all --gu 영등포구
    python manage.py run_all --gu 강남구

실행 순서:
1. 기존 데이터 전체 삭제
2. 다이소 수집 (다이소 공식 API)
3. 편의점 수집 (카카오 API)
4. OpenAPI 휴게음식점 수집
5. OpenAPI 담배소매업 수집
6. 폐업 검증
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from .gu_codes import list_supported_gu, get_gu_info


class Command(BaseCommand):
    help = '구 단위 전체 파이프라인 실행 (다이소 → 편의점 → OpenAPI → 폐업검증)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--gu',
            type=str,
            default='영등포구',
            help=f'대상 구 (기본: 영등포구). 지원: {", ".join(list_supported_gu())}'
        )
        parser.add_argument(
            '--skip-daiso',
            action='store_true',
            help='다이소 수집 단계 스킵'
        )
        parser.add_argument(
            '--skip-convenience',
            action='store_true',
            help='편의점 수집 단계 스킵'
        )
        parser.add_argument(
            '--skip-openapi',
            action='store_true',
            help='OpenAPI 수집 단계 스킵'
        )
        parser.add_argument(
            '--skip-check',
            action='store_true',
            help='폐업 검증 단계 스킵'
        )

    def handle(self, *args, **options):
        target_gu = options['gu']
        
        # 구 유효성 검증
        try:
            get_gu_info(target_gu)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return
        
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS(f"🚀 {target_gu} 전체 파이프라인 시작"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        
        # Step 1: 다이소 수집
        if not options['skip_daiso']:
            self.stdout.write(self.style.WARNING(f"\n📦 [1/5] {target_gu} 다이소 수집..."))
            try:
                call_command('v2_3_1_collect_yeongdeungpo_daiso', gu=target_gu, clear=True)
                self.stdout.write(self.style.SUCCESS("  ✅ 다이소 수집 완료"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ 다이소 수집 실패: {e}"))
                return
        else:
            self.stdout.write(self.style.WARNING("\n⏭️ [1/5] 다이소 수집 스킵"))
        
        # Step 2: 편의점 수집
        if not options['skip_convenience']:
            self.stdout.write(self.style.WARNING(f"\n🏪 [2/5] {target_gu} 편의점 수집..."))
            try:
                call_command('v2_3_2_collect_Convenience_Only', gu=target_gu, clear=True)
                self.stdout.write(self.style.SUCCESS("  ✅ 편의점 수집 완료"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ 편의점 수집 실패: {e}"))
                return
        else:
            self.stdout.write(self.style.WARNING("\n⏭️ [2/5] 편의점 수집 스킵"))
        
        # Step 3: OpenAPI 휴게음식점 수집
        if not options['skip_openapi']:
            self.stdout.write(self.style.WARNING(f"\n📋 [3/5] {target_gu} 휴게음식점 인허가 수집..."))
            try:
                call_command('openapi_1', gu=target_gu, clear=True)
                self.stdout.write(self.style.SUCCESS("  ✅ 휴게음식점 인허가 수집 완료"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ 휴게음식점 인허가 수집 실패: {e}"))
                return
            
            # Step 4: OpenAPI 담배소매업 수집
            self.stdout.write(self.style.WARNING(f"\n🚬 [4/5] {target_gu} 담배소매업 인허가 수집..."))
            try:
                call_command('openapi_2', gu=target_gu, clear=True)
                self.stdout.write(self.style.SUCCESS("  ✅ 담배소매업 인허가 수집 완료"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ 담배소매업 인허가 수집 실패: {e}"))
                return
        else:
            self.stdout.write(self.style.WARNING("\n⏭️ [3/5] 휴게음식점 인허가 수집 스킵"))
            self.stdout.write(self.style.WARNING("⏭️ [4/5] 담배소매업 인허가 수집 스킵"))
        
        # Step 5: 폐업 검증
        if not options['skip_check']:
            self.stdout.write(self.style.WARNING(f"\n🔍 [5/5] {target_gu} 폐업 매장 검증..."))
            try:
                call_command('check_store_closure', gu=target_gu)
                self.stdout.write(self.style.SUCCESS("  ✅ 폐업 검증 완료"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ 폐업 검증 실패: {e}"))
                return
        else:
            self.stdout.write(self.style.WARNING("\n⏭️ [5/5] 폐업 검증 스킵"))
        
        # 완료
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS(f"🎉 {target_gu} 전체 파이프라인 완료!"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(f"\n📊 결과 확인: http://127.0.0.1:8000/store-closure/")
