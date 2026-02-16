"""
Tests d'intégrité JSON pour l'API
Vérifie que les endpoints retournent des données conformes
"""
import requests
import sys

BASE_URL = "http://localhost:8000"

def test_ping():
    """Test endpoint /ping"""
    response = requests.get(f"{BASE_URL}/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    print("✓ /ping OK")

def test_siret():
    """Test endpoint /siret/{siret}"""
    siret = "77567227200020"
    response = requests.get(f"{BASE_URL}/siret/{siret}")
    assert response.status_code == 200
    data = response.json()
    assert data["siret"] == siret
    assert "nom" in data
    assert "code_postal" in data
    print(f"✓ /siret/{siret} OK")

def test_search():
    """Test endpoint /search"""
    response = requests.get(f"{BASE_URL}/search?q=croix&postal_code=75015")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    print("✓ /search OK")

if __name__ == "__main__":
    try:
        test_ping()
        test_siret()
        test_search()
        print("\n✅ Tous les tests passés")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        sys.exit(1)
