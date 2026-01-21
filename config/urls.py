"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from stores.views import (
    map_view, 
    store_closure_map_view,
    collector_view,
    start_collection,
    check_status,
    get_results,
    dev_monitor_view,
    dev_status,
    dev_test_view
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", collector_view, name="home"),  # 메인 페이지 (수집 UI)
    path("map/", map_view, name="map_view"), 
    path("store-closure/", store_closure_map_view, name="store_closure_map"),
    
    # 개발자 모니터링 대시보드
    path("dev/monitor/", dev_monitor_view, name="dev_monitor"),
    path("dev/test/", dev_test_view, name="dev_test"),
    
    # API 엔드포인트
    path("api/start-collection/", start_collection, name="start_collection"),
    path("api/check-status/", check_status, name="check_status"),
    path("api/get-results/", get_results, name="get_results"),
    path("api/dev-status/", dev_status, name="dev_status"),
]
