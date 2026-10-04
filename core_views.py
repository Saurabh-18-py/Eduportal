from django.shortcuts import render

CLASS_CHOICES = [9, 10, 11, 12]


def home_view(request):
    return render(request, 'home.html', {'classes': CLASS_CHOICES})


def offline_view(request):
    return render(request, 'offline.html')


def app_download_view(request):
    return render(request, 'app_download.html', {'releases_repo': 'Saurabh-18-py/eduportal-releases'})
