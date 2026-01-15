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
from stores.views import map_view, kakao_map_test

urlpatterns = [
    path("admin/", admin.site.urls),
    path("map/", map_view, name="map_view"), 
    path("map-test/", kakao_map_test, name="kakao_map_test"),  # 마커 테스트 
    #  주소 추가 (http://127.0.0.1:8000/map/)
    
    # 폐업 매장 관련 URL (영등포구 확장 프로젝트)
    path("stores/", include("stores.urls_closed")),
]
