from django.shortcuts import render
from django.http import Http404

from portfolio.data import RECIPES


def index(request):
    return render(request, 'portfolio/index.html')


def recipes(request):
    return render(request, 'portfolio/recipes.html')


def recipe_detail(request, slug):
    recipe = next((r for r in RECIPES if r['slug'] == slug), None)
    if recipe is None:
        raise Http404("Recipe not found")
    return render(request, 'portfolio/recipe_detail.html', {'recipe': recipe})


def blog(request):
    return render(request, 'portfolio/blog.html')


def footy(request):
    return render(request, 'portfolio/footy.html')
