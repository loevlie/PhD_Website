from django.shortcuts import render


def index(request):
    return render(request, 'portfolio/index.html')


def recipes(request):
    return render(request, 'portfolio/recipes.html')
