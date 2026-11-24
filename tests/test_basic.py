import pytest
from django.urls import reverse
from accounts.models import CustomUser

@pytest.mark.django_db
def test_home_page(client):
    response = client.get(reverse('core:home'))
    assert response.status_code == 200

@pytest.mark.django_db
def test_signup_page(client):
    response = client.get(reverse('accounts:signup'))
    assert response.status_code == 200

@pytest.mark.django_db
def test_signup_creates_user(client):
    response = client.post(reverse('accounts:signup'), {
        'email': 'test@example.com',
        'full_name': 'Test User',
        'password1': 'StrongPass123!',
        'password2': 'StrongPass123!',
    })
    assert CustomUser.objects.filter(email='test@example.com').exists()

@pytest.mark.django_db
def test_login_page(client):
    response = client.get(reverse('accounts:login'))
    assert response.status_code == 200

@pytest.mark.django_db
def test_health_endpoint(client):
    response = client.get(reverse('core:health'))
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'service': 'BhoomiAI'}
