# SmartFarm Project

SmartFarm is a modular IoT and data management system designed to manage farm devices, sensor data, and user authentication. Built with FastAPI microservices and Docker, it integrates with external systems like MQTT, InfluxDB, and PostgreSQL.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Services](#services)
    - [User Service](#user-service)
    - [Device Service](#device-service)
    - [Sensor Data Service](#sensor-data-service)
- [API Endpoints](#api-endpoints)
    - [User Service Endpoints](#user-service-endpoints)
    - [Device Service Endpoints](#device-service-endpoints)
    - [Sensor Data Service Endpoints](#sensor-data-service-endpoints)
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
    - `POST /auth/create_user`  
      *Creates a new user account with necessary details such as username, email, and password.*
    - `POST /auth/token`  
      *Authenticates the user and generates a JWT access token for session management.*
    - `GET /auth/get_current_user`  
      *Retrieves details for the currently authenticated user.*
    - `GET /user/info`  
      *Fetches profile information of the logged-in user.*
    - `PUT /user/change_password`  
      *Allows the user to change their password after verifying the current one.*
    - `PUT /user/change_number`  
      *Updates the contact number associated with the user's profile.*
    - `GET /admin/get_all_users`  
      *(Admin only) Retrieves a list of all registered users for management purposes.*
    - `PUT /admin/change_users_role`  
      *(Admin only) Modifies the role assigned to a specified user to control access.*
    - `GET /admin/delete_user/{user_to_delete_id}`  
      *(Admin only) Deletes a user account identified by the provided user ID.*

### Device Service
- **Purpose**: Handles operations related to farm devices, crop management, and overall farm operations.
- **Key Features**:
    - CRUD operations for devices, farms, and crops.
    - Device firmware updates via HTTP.
    - Association of devices to specific farms.
- **Endpoints**:
    - `POST /devices/device`  
      *Registers a new device along with its sensor configuration and assigns it to a user.*
    - `PATCH /devices/device/{device_id}`  
      *Updates the status or configuration details of an existing device.*
    - `DELETE /devices/device/{device_id}`  
      *Removes a device from the system based on its unique ID.*
    - `PATCH /devices/assign-device-to-farm`  
      *Associates a device with a specific farm by linking their IDs.*
    - `GET /devices/unsigned-devices`  
      *Lists devices that have not yet been assigned to any farm.*
    - `GET /devices/all-devices`  
      *Lists all devices registered under the currently authenticated user.*
    - `GET /devices/all-devices/{farm_id}`  
      *Lists devices specific to a given farm, providing organizational clarity.*
    - `POST /devices/upload_firmware/{device_id}`  
      *Uploads and updates the firmware of a device remotely via an HTTP request.*

- **Farm Endpoints**:
    - `POST /farms/farm`  
      *Creates a new farm record with details like name, total area, and location.*
    - `GET /farms/farm/{farm_id}`  
      *Retrieves detailed information about a specific farm based on its ID.*
    - `PUT /farms/farm/{farm_id}`  
      *Updates existing farm information such as name, area, or location.*
    - `PATCH /farms/farm/{farm_id}`  
      *Assigns a crop to the farm, linking crop management data with the farm record.*
    - `DELETE /farms/farm/{farm_id}`  
      *Deletes a farm record from the system using its unique ID.*

- **Crop Endpoints**:
    - `POST /crop/crop`  
      *Adds a new crop management entry, including planting and harvest dates and growth stage.*
    - `GET /crop/сrop/{crop_id}`  
      *Retrieves details about a specific crop management entry by its ID.*
    - `PUT /crop/crop/{crop_id}`  
      *Updates an existing crop management entry with new details or corrections.*
    - `POST /crop/type`  
      *Creates a new crop type, enabling categorization and management of crop entries.*
    - `GET /crop/type`  
      *Fetches a list of all available crop types registered in the system.*

### Sensor Data Service
- **Purpose**: Receives sensor readings through MQTT and stores them in InfluxDB for time-series analysis.
- **Key Features**:
    - Subscribes to MQTT topics (e.g., `device/+/data`) for real-time sensor data collection.
    - Parses sensor payloads and writes structured data to InfluxDB.
    - Provides endpoints to simulate sensor data and query historical time-series data using Flux.
- **Endpoints**:
    - `GET /health`  
      *Performs a health check on the sensor data service, verifying connectivity with MQTT and InfluxDB.*
    - `POST /simulate-sensor-data`  
      *Simulates sensor data input, allowing users to test and validate data processing workflows.*
    - `GET /device_data/{device_id}/{sensor_type}/{time}`  
      *Queries time-series data for a specified device and sensor over a defined time range (e.g., 1h, 24h, 7d, 30d).*

## API Endpoints
This section provides a consolidated view of available endpoints across services. For more details on request payloads and responses, refer to the respective service documentation.

### User Service Endpoints
- User Registration and Authentication:
    - `POST /auth/create_user` - Creates a new user.
    - `POST /auth/token` - Authenticates and retrieves a JWT token.
- User Profile and Management:
    - `GET /auth/get_current_user` - Retrieves the current user's details.
    - `GET /user/info` - Returns user profile information.
    - `PUT /user/change_password` - Changes the user's password.
    - `PUT /user/change_number` - Updates the user's contact number.
- Administrative Control (Admin Role Required):
    - `GET /admin/get_all_users` - Retrieves all users.
    - `PUT /admin/change_users_role` - Modifies a user's role.
    - `GET /admin/delete_user/{user_to_delete_id}` - Deletes a specified user.

### Device Service Endpoints
- Device Management:
    - `POST /devices/device` - Adds a new device.
    - `PATCH /devices/device/{device_id}` - Updates a device’s status.
    - `DELETE /devices/device/{device_id}` - Deletes a device.
    - `PATCH /devices/assign-device-to-farm` - Assigns a device to a farm.
    - `GET /devices/unsigned-devices` - Lists devices not yet assigned to any farm.
    - `GET /devices/all-devices` - Lists all devices for the current user.
    - `GET /devices/all-devices/{farm_id}` - Lists devices for a specific farm.
    - `POST /devices/upload_firmware/{device_id}` - Updates device firmware.
- Farm and Crop Management:
    - Farm Endpoints:
        - `POST /farms/farm` - Creates a new farm.
        - `GET /farms/farm/{farm_id}` - Retrieves farm details.
        - `PUT /farms/farm/{farm_id}` - Updates farm information.
        - `PATCH /farms/farm/{farm_id}` - Assigns a crop to a farm.
        - `DELETE /farms/farm/{farm_id}` - Deletes a farm.
    - Crop Endpoints:
        - `POST /crop/crop` - Adds new crop management entries.
        - `GET /crop/сrop/{crop_id}` - Retrieves crop details.
        - `PUT /crop/crop/{crop_id}` - Updates crop information.
        - `POST /crop/type` - Adds a new crop type.
        - `GET /crop/type` - Lists all available crop types.

### Sensor Data Service Endpoints
- Real-time Data Handling:
    - `GET /health` - Checks the health status of the sensor data service.
    - `POST /simulate-sensor-data` - Simulates and stores sensor data.
- Historical Data Query:
    - `GET /device_data/{device_id}/{sensor_type}/{time}` - Queries historical sensor data for analysis.

## Setup and Installation

### Prerequisites
- Docker and Docker Compose must be installed on your machine.
- Environment variables configured for MQTT, InfluxDB, PostgreSQL, etc.

### Local Setup
1. **Clone the Repository:**
     ```
     git clone https://github.com/yourusername/smartfarm.git
     cd smartfarm
     ```
2. **Configure Environment Variables:**
     Create a `.env` file with the credentials for MQTT, InfluxDB, and PostgreSQL.
3. **Run Docker Compose:**
     ```
     docker-compose up --build
     ```
     This command builds and starts the containers:
     - User Service on port 8005
     - Device Service on port 8000
     - Mosquitto (MQTT broker)
     - InfluxDB
     - PostgreSQL for the user service

## Docker Compose
The `Docker-compose.yaml` file orchestrates the various services with these key details:
- **Volumes:** Persistent data mounting for Mosquitto, InfluxDB, and PostgreSQL.
- **Service Dependencies:** Device Service depends on User Service.
- **Ports:** Exposed ports allow inter-service communication and external API access.

## Contributing
Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch with a descriptive name.
3. Commit your changes with clear messages.
4. Open a pull request describing your modifications.

