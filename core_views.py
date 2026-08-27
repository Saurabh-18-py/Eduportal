from django.shortcuts import render

CLASS_CHOICES = [9, 10, 11, 12]


def home_view(request):
    return render(request, 'home.html', {'classes': CLASS_CHOICES})
