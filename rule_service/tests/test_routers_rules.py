import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_new_rule(client: AsyncClient):
    payload = {
        "rule_name": "Test Rule",
        "description": "A test rule",
        "trigger_type": "sensor_threshold",
        "sensor_id": "sensor-1",
        "device_id": "device-1",
        "rule_expression": "temperature > 30",
        "cooldown_seconds": 60,
        "is_active": True,
        "farm_id": "farm-1",
        "actions": [
            {
                "action_type": "send_notification",
                "action_payload": {"message": "Test alert"},
                "execution_order": 1
            }
        ]
    }
    
    response = await client.post("/api/rule-service/rules/rule", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Rule added successfully"

@pytest.mark.asyncio
async def test_add_new_rule_invalid_expression(client: AsyncClient):
    payload = {
        "rule_name": "Test Rule",
        "description": "A test rule",
        "trigger_type": "sensor_threshold",
        "rule_expression": "invalid > > expression",
        "farm_id": "farm-1",
        "actions": []
    }
    
    response = await client.post("/api/rule-service/rules/rule", json=payload)
    assert response.status_code == 400
    assert "Invalid rule expression" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_all_rules(client: AsyncClient):
    # Setup - add one rule
    payload = {
        "rule_name": "Get All Test",
        "trigger_type": "sensor_threshold",
        "rule_expression": "temperature < 10",
        "farm_id": "farm-get",
        "actions": []
    }
    await client.post("/api/rule-service/rules/rule", json=payload)
    
    response = await client.get("/api/rule-service/rules/all?farm_id=farm-get")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    
    # Store rule_id for next tests
    rule_id = data["items"][0]["rule_id"]
    return rule_id

@pytest.mark.asyncio
async def test_get_rule_by_id(client: AsyncClient):
    # Need to get a rule ID first
    payload = {
        "rule_name": "Get By ID Test",
        "trigger_type": "sensor_threshold",
        "rule_expression": "temperature == 10",
        "farm_id": "farm-id-test",
        "actions": []
    }
    await client.post("/api/rule-service/rules/rule", json=payload)
    
    all_rules_response = await client.get("/api/rule-service/rules/all?farm_id=farm-id-test")
    rule_id = all_rules_response.json()["items"][0]["rule_id"]
    
    response = await client.get(f"/api/rule-service/rules/rule/{rule_id}")
    assert response.status_code == 200
    assert response.json()["rule_name"] == "Get By ID Test"

@pytest.mark.asyncio
async def test_get_rule_not_found(client: AsyncClient):
    response = await client.get("/api/rule-service/rules/rule/invalid_id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Rule not found"

@pytest.mark.asyncio
async def test_update_rule(client: AsyncClient):
    payload = {
        "rule_name": "Update Test",
        "trigger_type": "sensor_threshold",
        "rule_expression": "humidity > 50",
        "farm_id": "farm-update",
        "actions": []
    }
    await client.post("/api/rule-service/rules/rule", json=payload)
    
    all_rules_response = await client.get("/api/rule-service/rules/all?farm_id=farm-update")
    rule_id = all_rules_response.json()["items"][0]["rule_id"]
    
    update_payload = {
        "rule_name": "Updated Rule Name",
        "description": "Updated description",
        "is_active": False
    }
    
    response = await client.put(f"/api/rule-service/rules/rule/{rule_id}", json=update_payload)
    assert response.status_code == 200
    
    # Verify update
    get_response = await client.get(f"/api/rule-service/rules/rule/{rule_id}")
    data = get_response.json()
    assert data["rule_name"] == "Updated Rule Name"
    assert data["description"] == "Updated description"
    assert data["is_active"] is False

@pytest.mark.asyncio
async def test_delete_rule(client: AsyncClient):
    payload = {
        "rule_name": "Delete Test",
        "trigger_type": "sensor_threshold",
        "rule_expression": "humidity < 50",
        "farm_id": "farm-delete",
        "actions": []
    }
    await client.post("/api/rule-service/rules/rule", json=payload)
    
    all_rules_response = await client.get("/api/rule-service/rules/all?farm_id=farm-delete")
    rule_id = all_rules_response.json()["items"][0]["rule_id"]
    
    delete_response = await client.delete(f"/api/rule-service/rules/rule/{rule_id}")
    assert delete_response.status_code == 204
    
    # Verify deletion
    get_response = await client.get(f"/api/rule-service/rules/rule/{rule_id}")
    assert get_response.status_code == 404

