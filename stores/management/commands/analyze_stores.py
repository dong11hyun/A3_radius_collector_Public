import pandas as pd
from django.core.management.base import BaseCommand
from stores.models import NearbyStore

class Command(BaseCommand):
    help = '수집된 데이터를 Pandas로 분석하여 다이소 지점별 상권 점수를 계산합니다.'

    def handle(self, *args, **kwargs):
        # 1. DB에서 데이터 가져오기 (QuerySet -> List)
        # 필요한 필드만 쏙 뽑아옵니다.
        data = NearbyStore.objects.all().values('base_daiso', 'category', 'name')
        
        if not data:
            self.stdout.write(self.style.ERROR("❌ 데이터가 없습니다. 먼저 수집(collect_cafes)을 진행해주세요."))
            return

        # 2. Pandas DataFrame 변환
        df = pd.DataFrame(data)

        self.stdout.write(self.style.SUCCESS(f"📊 총 {len(df)}개의 데이터를 로드했습니다."))

        # 3. 데이터 집계 (Pivot Table)
        # 행(Index): 다이소 지점명 / 열(Column): 업종 / 값(Value): 개수(Count)
        # fill_value=0: 카페가 하나도 없으면 NaN 대신 0으로 채움
        pivot_df = df.pivot_table(index='base_daiso', columns='category', values='name', aggfunc='count', fill_value=0)

        print("\n[업종별 개수 현황]")
        print(pivot_df)

        # 4. 상권 점수 계산 (Scoring Algorithm)
        # 공식: (편의점 * 0.5) + (카페 * 1.0) - (대형마트 * 2.0)
        # 대형마트는 경쟁사이므로 감점 요인으로 설정해 봅니다.
        
        # 컬럼 이름이 한글('편의점', '카페', '대형마트')로 되어 있으니 그대로 씁니다.
        # 없는 컬럼이 있을 수 있으니 안전하게 get으로 가져옵니다.
        score_series = (
            (pivot_df.get('편의점', 0) * 0.5) + 
            (pivot_df.get('카페', 0) * 1.0) - 
            (pivot_df.get('대형마트', 0) * 2.0)
        )

        # 5. 결과 정리 및 랭킹 산출
        result_df = pivot_df.copy()
        result_df['상권점수'] = score_series
        
        # 점수 높은 순으로 정렬
        result_df = result_df.sort_values(by='상권점수', ascending=False)

        print("\n[🏆 최종 상권 분석 랭킹]")
        print("=" * 60)
        print(result_df[['상권점수']]) # 점수만 깔끔하게 출력
        print("=" * 60)

        # (선택) 엑셀로 저장하고 싶다면?
        # result_df.to_excel("daiso_analysis_result.xlsx")
        # self.stdout.write("엑셀 파일로 저장되었습니다.")