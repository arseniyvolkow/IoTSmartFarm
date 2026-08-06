import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200


# Farms
async def test_farms(client: AsyncClient):
    farm_data = {
        "farm_name": "Test Farm",
        "total_area": 100,
        "location": "Test Location",
    }
    response = await client.post("/farms/farm", json=farm_data)
    assert response.status_code in [200, 201]

    response = await client.get("/farms/all")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0
    farm_id = items[0]["farm_id"]

    response = await client.get(f"/farms/farm/{farm_id}")
    assert response.status_code == 200

    response = await client.put(
        f"/farms/farm/{farm_id}", json={"farm_name": "Updated Farm"}
    )
    assert response.status_code == 200


# Devices
async def test_devices(client: AsyncClient):
    device_data = {
        "unique_device_id": "test-dev-1",
        "device_ip_address": "192.168.1.100",
        "model_number": "M1",
        "firmware_version": "1.0",
        "sensors_list": [],
        "actuators_list": [],
    }
    response = await client.post("/devices/device", json=device_data)
    assert response.status_code in [200, 201]
    device_id = response.json()["device_id"]

    response = await client.get("/devices/all-devices")
    assert response.status_code == 200

    response = await client.patch(
        f"/devices/assign-user-to-device?device_id={device_id}"
    )
    assert response.status_code == 200

    response = await client.patch(f"/devices/device/{device_id}?new_status=active")
    assert response.status_code == 200

    response = await client.delete(f"/devices/device/{device_id}")
    assert response.status_code == 204


# Crops
async def test_crops(client: AsyncClient):
    response = await client.post("/crop/crop-type?crop_name=Tomato")
    assert response.status_code in [200, 201]
    crop_type_id = response.json()["crop_id"]

    farm_data = {
        "farm_name": "Crop Farm",
        "total_area": 100,
        "location": "Test Location",
    }
    await client.post("/farms/farm", json=farm_data)
    response = await client.get("/farms/all")
    farm_id = response.json()["items"][-1]["farm_id"]

    crop_data = {
        "planting_date": "2023-01-01",
        "expected_harvest_date": "2023-05-01",
        "current_grow_stage": "seed",
        "crop_type_id": crop_type_id,
        "farm_id": farm_id,
    }
    response = await client.post("/crop/crop", json=crop_data)
    assert response.status_code in [200, 201]
    crop_id = response.json()["crop_id"]

    response = await client.get(f"/crop/crop/{crop_id}")
    assert response.status_code == 200

    response = await client.put(
        f"/crop/crop/{crop_id}", json={"current_grow_stage": "vegetative"}
    )
    assert response.status_code == 200


# Sensors and Actuators
async def test_sensors_and_actuators(client: AsyncClient):
    device_data = {
        "unique_device_id": "test-dev-2",
        "device_ip_address": "192.168.1.100",
        "model_number": "M1",
        "firmware_version": "1.0",
        "sensors_list": [
            {
                "sensor_type": "temperature",
                "units_of_measure": "C",
                "max_value": 100.0,
                "min_value": -40.0,
            }
        ],
        "actuators_list": [
            {
                "actuator_type": "valve",
                "available_states": {"on": 1, "off": 0},
                "current_state": "off",
            }
        ],
    }
    dev_res = await client.post("/devices/device", json=device_data)
    assert dev_res.status_code in [200, 201]

    # Assign device to a user so it shows up in /sensors/all and /actuators/all
    device_id = dev_res.json()["device_id"]
    await client.patch(f"/devices/assign-user-to-device?device_id={device_id}")

    sens_res = await client.get("/sensors/all")
    sensors = sens_res.json().get("items", [])
    act_res = await client.get("/actuators/all")
    actuators = act_res.json().get("items", [])

    if sensors:
        sensor_id = sensors[-1]["sensor_id"]
        response = await client.get(f"/sensors/sensor/{sensor_id}")
        assert response.status_code == 200

        response = await client.put(
            f"/sensors/sensor/{sensor_id}", json={"max_value": 150.0}
        )
        assert response.status_code == 204

        response = await client.delete(f"/sensors/sensor/{sensor_id}")
        assert response.status_code == 204

    if actuators:
        actuator_id = actuators[-1]["actuator_id"]
        response = await client.get(f"/actuators/actuator/{actuator_id}")
        assert response.status_code == 200

        response = await client.put(
            f"/actuators/actuator/{actuator_id}", json={"current_state": "on"}
        )
        assert response.status_code == 200

        response = await client.delete(f"/actuators/actuator/{actuator_id}")
        assert response.status_code == 204


# Access Control
async def test_access_control(client: AsyncClient):
    farm_res = await client.post(
        "/farms/farm",
        json={"farm_name": "Access Farm", "total_area": 10, "location": "L"},
    )
    farm_res = await client.get("/farms/all")
    farm_id = farm_res.json()["items"][-1]["farm_id"]

    access_data = {"user_id": "test-user-id-2", "access_level": "read"}
    response = await client.post(f"/farms/{farm_id}/access", json=access_data)
    assert response.status_code in [200, 201]

    response = await client.get(f"/farms/{farm_id}/access")
    assert response.status_code == 200

    response = await client.delete(f"/farms/{farm_id}/access/test-user-id-2")
    assert response.status_code == 204
