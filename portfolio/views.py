from django.shortcuts import render
from django.http import Http404

from portfolio.data import RECIPES
from portfolio.blog import get_all_posts, get_post


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
    posts = get_all_posts()
    tag = request.GET.get('tag')
    query = request.GET.get('q', '').strip()

    if tag:
        posts = [p for p in posts if tag in p['tags']]
    if query:
        q_lower = query.lower()
        posts = [p for p in posts if
                 q_lower in p['title'].lower() or
                 q_lower in p['excerpt'].lower() or
                 any(q_lower in t.lower() for t in p['tags'])]

    return render(request, 'portfolio/blog.html', {
        'posts': posts,
        'active_tag': tag,
        'search_query': query,
    })


def blog_post(request, slug):
    post = get_post(slug)
    if post is None:
        raise Http404("Post not found")
    return render(request, 'portfolio/blog_post.html', {'post': post})


def publications(request):
    return render(request, 'portfolio/publications.html')


def projects(request):
    return render(request, 'portfolio/projects.html')
