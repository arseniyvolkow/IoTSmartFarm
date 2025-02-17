# SmartFarm Project

SmartFarm is a modular IoT and data management system designed to manage farm devices, sensor data, and user authentication. Built with FastAPI microservices and Docker, it integrates with external systems like MQTT, InfluxDB, and PostgreSQL.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Services](#services)
    - [User Service](#user-service)
    - [Device Service](#device-service)
    - [Sensor Data Service](#sensor-data-service)
- [Setup and Installation](#setup-and-installation)
- [Docker Compose](#docker-compose)
- [Contributing](#contributing)
- [License](#license)

## Overview
The SmartFarm project tracks agricultural devices, sensor readings, crop management, and farm operations. It implements:
- **User Service**: Handles user registration, authentication, and role management with JWT tokens.
- **Device Service**: Manages device installation, sensor assignments, crop management, and firmware updates.
- **Sensor Data Service**: Collects sensor data via MQTT, stores time-series data in InfluxDB, and supports simulation and querying.

## Architecture
- **FastAPI Microservices** for high-performance RESTful APIs.
- **SQLAlchemy ORM** for relational database interactions (SQLite for local testing and PostgreSQL for production).
- **MQTT Protocol** for real-time sensor data collection.
- **InfluxDB** for storing and querying time-series data.
- **Docker** for containerization and deployment orchestration.

## Services

### User Service
- **Purpose**: Provides authentication (JWT based) and user management functions.
- **Key Features**:
    - User registration and role assignment.
    - Token generation and validation.
    - Administrative endpoints for managing users.
- **Endpoints**:
    - `POST /auth/create_user` - Creates a new user account.
    - `POST /auth/token` - Authenticates the user and generates a JWT access token.
    - `GET /auth/get_current_user` - Retrieves details for the currently authenticated user.
    - `GET /user/info` - Fetches profile information of the logged-in user.
    - `PUT /user/change_password` - Allows the user to change their password.
    - `PUT /user/change_number` - Updates the user's contact number.
    - `GET /admin/get_all_users` - (Admin only) Retrieves a list of all registered users.
    - `PUT /admin/change_users_role` - (Admin only) Modifies the role assigned to a user.
    - `GET /admin/delete_user/{user_to_delete_id}` - (Admin only) Deletes a user account.

### Device Service
- **Purpose**: Handles operations related to farm devices, crop management, and overall farm operations.
- **Key Features**:
    - CRUD operations for devices, farms, and crops.
    - Device firmware updates via HTTP.
    - Association of devices to specific farms.
- **Endpoints**:
    - `POST /devices/device` - Registers a new device.
    - `PATCH /devices/device/{device_id}` - Updates the status or configuration of a device.
    - `DELETE /devices/device/{device_id}` - Removes a device from the system.
    - `PATCH /devices/assign-device-to-farm` - Associates a device with a specific farm.
    - `GET /devices/unsigned-devices` - Lists devices not yet assigned to any farm.
    - `GET /devices/all-devices` - Lists all devices registered under the current user.
    - `GET /devices/all-devices/{farm_id}` - Lists devices specific to a given farm.
    - `POST /devices/upload_firmware/{device_id}` - Uploads and updates the firmware of a device.

- **Farm Endpoints**:
    - `POST /farms/farm` - Creates a new farm record.
    - `GET /farms/farm/{farm_id}` - Retrieves detailed information about a specific farm.
    - `PUT /farms/farm/{farm_id}` - Updates existing farm information.
    - `PATCH /farms/farm/{farm_id}` - Assigns a crop to the farm.
    - `DELETE /farms/farm/{farm_id}` - Deletes a farm record.

- **Crop Endpoints**:
    - `POST /crop/crop` - Adds a new crop management entry.
    - `GET /crop/сrop/{crop_id}` - Retrieves details about a specific crop management entry.
    - `PUT /crop/crop/{crop_id}` - Updates an existing crop management entry.
    - `POST /crop/type` - Creates a new crop type.
    - `GET /crop/type` - Fetches a list of all available crop types.

### Sensor Data Service
- **Purpose**: Receives sensor readings through MQTT and stores them in InfluxDB for time-series analysis.
- **Key Features**:
    - Subscribes to MQTT topics for real-time sensor data collection.
    - Parses sensor payloads and writes structured data to InfluxDB.
    - Provides endpoints to simulate sensor data and query historical time-series data using Flux.
- **Endpoints**:
    - `GET /health` - Performs a health check on the sensor data service.
    - `POST /simulate-sensor-data` - Simulates sensor data input.
    - `GET /device_data/{device_id}/{sensor_type}/{time}` - Queries time-series data for a specified device and sensor.

## Setup and Installation

### Prerequisites
- Docker and Docker Compose must be installed on your machine.
- Environment variables configured for MQTT, InfluxDB, PostgreSQL, etc.

### Local Setup
1. **Clone the Repository:**
     ```sh
     git clone https://github.com/yourusername/smartfarm.git
     cd smartfarm
     ```
2. **Configure Environment Variables:**
     Create a `.env` file with the credentials for MQTT, InfluxDB, and PostgreSQL.
3. **Run Docker Compose:**
     ```sh
     docker-compose up --build
     ```
     This command builds and starts the containers:
     - User Service on port 8005
     - Device Service on port 8001
     - Mosquitto (MQTT broker)
     - InfluxDB
     - PostgreSQL for the user service

## Docker Compose
The `docker-compose.yaml` file orchestrates the various services with these key details:
- **Volumes:** Persistent data mounting for Mosquitto, InfluxDB, and PostgreSQL.
- **Service Dependencies:** Device Service depends on User Service.
- **Ports:** Exposed ports allow inter-service communication and external API access.

## Contributing
Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch with a descriptive name.
3. Commit your changes with clear messages.
4. Open a pull request describing your modifications.

## License
This project is licensed under the MIT License.