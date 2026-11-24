import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_renders_new_assets(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="dashboard-tester",
        email="dashboard@example.com",
        password="StrongPass123!",
        full_name="Dashboard Tester",
    )
    client.force_login(user)
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "BhoomiAI" in html
    assert "stat-documents.svg" in html
    assert "stat-validated.svg" in html
    assert "stat-pending.svg" in html
    assert "stat-duplicates.svg" in html
    assert "data/india-states.geojson" in html
    assert "india-map.svg" in html


@pytest.mark.django_db
def test_auth_pages_rebranded(client):
    for url in ("accounts:login", "accounts:signup", "core:home"):
        response = client.get(reverse(url))
        assert response.status_code == 200
        assert "LandVault" not in response.content.decode()
