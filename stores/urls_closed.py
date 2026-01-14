# stores/urls_closed.py
"""
폐업 매장 관련 URL 라우팅
메인 urls.py에서 include하여 사용
"""

from django.urls import path
from stores import views_closed

urlpatterns = [
    # 폐업 매장 목록 (3가지 기능 선택 페이지)
    path('closed/', views_closed.closed_stores_list, name='closed_stores_list'),
    
    # 폐업 매장 전용 맵 (기능 2)
    path('closed/map/', views_closed.closed_stores_map, name='closed_stores_map'),
    
    # 잘못된 데이터만 보기 (기능 3)
    path('closed/errors/', views_closed.error_data_only, name='error_data_only'),
    
    # 매장 제보하기 (기능 1)
    path('closed/report/<int:store_id>/', views_closed.report_store, name='report_store'),
    
    # 매장 검증 API
    path('closed/verify/<int:store_id>/', views_closed.verify_store, name='verify_store'),
    
    # 편의점 전용 지도
    path('convenience/', views_closed.convenience_stores_map, name='convenience_stores_map'),
]
