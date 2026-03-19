from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('recipes/', views.recipes, name='recipes'),
    path('recipes/<slug:slug>/', views.recipe_detail, name='recipe_detail'),
    path('blog/', views.blog, name='blog'),
    path('footy/', views.footy, name='footy'),
]
