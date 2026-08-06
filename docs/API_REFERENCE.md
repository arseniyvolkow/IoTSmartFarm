# 📚 SmartFarm API Reference

This document outlines the available REST API endpoints across the IoTSmartFarm microservices.

---

## 1. User Service
**Purpose**: Provides authentication (JWT-based) and user management functions.

### Auth Router
- `POST /api/user-service/auth/register` - Register a new account.
- `POST /api/user-service/auth/token` - Login via Email/Password. Returns **Access + Refresh** tokens.
- `POST /api/user-service/auth/refresh` - Refresh an expired Access token using a valid Refresh token.
- `POST /api/user-service/auth/logout` - Secure logout (revokes token via Redis Blacklist).

### User Profile
- `GET /api/user-service/users/me` - Get current user's profile details.
- `PUT /api/user-service/users/me` - Update self profile (Email, Password, Avatar).
- `DELETE /api/user-service/users/me` - Delete self account.

### User Management (Admin Only)
- `GET /api/user-service/users` - List all users.
- `GET /api/user-service/users/{id}` - Get details of a specific user.
- `PUT /api/user-service/users/{id}` - Admin update.
- `POST /api/user-service/users/{id}/role` - Assign a role to a user.
- `DELETE /api/user-service/users/{id}` - Force delete/ban a user.

### RBAC Management (Super Admin Only)
- `GET /api/user-service/admin/roles` - List all available roles.
- `POST /api/user-service/admin/roles` - Create a new Role.
- `GET /api/user-service/admin/roles/{name}` - View role details.
- `POST /api/user-service/admin/roles/{name}/permissions` - Configure resource permissions.

---

## 2. Farm Management Service
**Purpose**: Handles operations related to farm devices, crop management, and overall farm structure.

### Farm Endpoints
- `POST /api/farm-management-service/farm` - Creates a new farm record.
- `GET /api/farm-management-service/all` - Retrieves all users farms.
- `GET /api/farm-management-service/farm/{farm_id}` - Retrieves detailed information about a specific farm.
- `PUT /api/farm-management-service/farms/farm/{farm_id}` - Updates existing farm information.
- `DELETE /api/farm-management-service/farms/farm/{farm_id}` - Deletes a farm record.

### Device Endpoints
- `POST /api/farm-management-service/device` - Registers a new device.
- `GET /api/farm-management-service/list-of-new-devices` - Get all new devices not yet assigned.
- `GET /api/farm-management-service/unsigned-devices` - Lists devices not yet assigned to any farm.
- `GET /api/farm-management-service/all-devices` - Lists all devices registered under the current user.
- `PATCH /api/farm-management-service/assign-device-to-farm` - Associates a device with a specific farm.
- `PATCH /api/farm-management-service/device/{device_id}` - Updates the status of a device.
- `DELETE /api/farm-management-service/device/{device_id}` - Removes a device from the system.
- `POST /api/farm-management-service/upload_firmware/{device_id}` - Uploads and updates device firmware over-the-air (OTA).

### Actuators Endpoints
- `GET /api/farm-management-service/actuator/{actuator_id}` - Get actuator details.
- `GET /api/farm-management-service/actuator/all` - Get all users actuators.
- `PUT /api/farm-management-service/actuator/{actuator_id}` - Update actuator info.
- `DELETE /api/farm-management-service/actuator/{actuator_id}` - Delete actuator.

### Sensor Endpoints
- `GET /api/farm-management-service/sensor/{sensor_id}` - Retrieves details about a specific sensor.
- `GET /api/farm-management-service/sensor/all` - Fetches a list of all sensors which the user has access to.
- `PUT /api/farm-management-service/sensor/{sensor_id}` - Update sensors information.
- `DELETE /api/farm-management-service/sensor/{sensor_id}` - Removes a sensor.

---

## 3. Sensor Data Service
**Purpose**: Serves sensor readings and historical analysis data.

### Endpoints
- `GET /api/sensor-data/health` - Performs a health check (verifies MQTT and Redis connections).
- `GET /api/sensor-data/sensor-value/{sensor_id}` - Get real-time value directly from the Redis cache.
- `GET /api/sensor-data/sensor-data/{sensor_id}/{time}` - Get time-series history (Aggregated & Cached from InfluxDB).
- `POST /api/sensor-data/actuator-mode-update` - Update actuators mode via MQTT.

---

## 4. Rule Service
**Purpose**: Handles automation logic and rule configuration.

### Endpoints
- `GET /api/rule-service/rule/{rule_id}` - Get details about a rule.
- `POST /api/rule-service/rule/` - Creates a new rule and its associated actions.
- `GET /api/rule-service/all/` - Get all users rules.
- `PUT /api/rule-service/rule/{rule_id}` - Update rule's information.
- `DELETE /api/rule-service/rule/{rule_id}` - Delete a rule.
