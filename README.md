# 🚀 SmartFarm: An IoT Platform for Smart Agriculture

SmartFarm is a modern, microservices-based IoT platform designed to serve as the digital brain for your agricultural operations. It handles high-speed sensor data ingestion via MQTT, stores timeseries data efficiently, and utilizes a real-time Rules Engine to automate actuators (pumps, fans, etc.) based on custom thresholds, taking the guesswork out of farming.

## Key Features
- **Real-time Sensor Ingestion**: Captures high-frequency MQTT data and stores it in InfluxDB and Redis.
- **Automated Rule Engine**: Evaluates sensor thresholds to automatically trigger actuators.
- **Zero-Touch Provisioning (ZTP)**: Seamlessly register and configure new IoT devices.
- **Over-The-Air (OTA) Updates**: Manage device firmware updates over MQTT.
- **Role-Based Access Control (RBAC)**: Secure multi-tenant administration and authentication.
- **CQRS Architecture**: Separates high-volume ingestion from API retrieval for maximum performance.

---

## Tech Stack

- **Language**: Python 3.11
- **Framework**: FastAPI (Asynchronous)
- **Application Server**: Gunicorn with Uvicorn workers
- **Relational Database**: PostgreSQL 15 (Managed via SQLAlchemy & Alembic)
- **Time-Series Database**: InfluxDB 2.7
- **Caching & Pub/Sub**: Redis 7
- **IoT Messaging**: Eclipse Mosquitto (MQTT 2.0)
- **Reverse Proxy**: Traefik v3
- **Deployment**: Docker & Docker Compose

---

## Prerequisites

Before starting, ensure you have the following installed on your machine:
- **Docker** (v24.0 or higher)
- **Docker Compose** (v2.20 or higher)
- **Git**

---

## Getting Started

Follow these steps to get the entire SmartFarm cluster running locally.

### 1. Clone the Repository

```bash
git clone https://github.com/arseniyvolkow/IoTSmartFarm.git
cd IoTSmartFarm
```

### 2. Environment Setup

Copy the example environment file to configure your local secrets:

```bash
cp .env.example .env
```

Review the `.env` file. The default values are designed to work out-of-the-box for local development.

| Variable | Description | Example |
| -------- | ----------- | ------- |
| `POSTGRES_USER_DATABASE_HOST` | Hostname for DB (must be `postgres` for Docker) | `postgres` |
| `INFLUXDB_TOKEN` | Auth token for InfluxDB time-series storage | `mytoken123` |
| `SECRET_KEY` | JWT encryption secret (change in production) | `YOUR_SECRET_KEY` |
| `REDIS_PASSWORD` | Password for the Redis cache | `your_redis_password` |

### 3. Launch the Infrastructure

Use Docker Compose to build and start the entire microservices cluster in the background:

```bash
docker compose up -d --build
```

This starts Traefik, Mosquitto, Redis, InfluxDB, PostgreSQL, and all 5 Python microservices. 

### 4. Database Setup & Migrations

The system uses a single PostgreSQL container that automatically provisions isolated logical databases for each service (`dev_user_service_db`, `dev_farm_db`, `dev_rule_db`).

Initialize the database schemas using Alembic:

```bash
docker compose exec user_service alembic upgrade head
docker compose exec farm_management_service alembic upgrade head
docker compose exec rule_service alembic upgrade head
```

### 5. Accessing the Application

Once running, the microservices expose their Swagger/OpenAPI documentation via Traefik:

- **User Service Docs**: [http://localhost/api/user-service/docs](http://localhost/api/user-service/docs)
- **Farm Management Service Docs**: [http://localhost/api/farm-management-service/docs](http://localhost/api/farm-management-service/docs)
- **Rule Service Docs**: [http://localhost/api/rule-service/docs](http://localhost/api/rule-service/docs)
- **Sensor Data API Docs**: [http://localhost/api/sensor-data/docs](http://localhost/api/sensor-data/docs)

---

## Architecture

### Directory Structure

```text
├── common/                     # Shared models, security, and DB configs across services
├── farm_management_service/    # Farm, crop, and device management (OTA, ZTP)
├── rule_service/               # CRUD for automation rules
├── rule_worker/                # Background worker evaluating rules & firing actuators
├── sensor_data_service/        # MQTT ingestion and InfluxDB time-series API
├── user_service/               # JWT Auth, user profiles, and RBAC
├── mosquitto/                  # MQTT broker configuration and certs
├── postgres-init/              # Auto-provisioning scripts for logical databases
├── docker-compose.yaml         # Complete infrastructure definition
└── run_tests_docker.sh         # Test orchestration script
```

### Data Flow

```text
IoT Sensors → [Mosquitto MQTT] → [Sensor Ingestion Worker] 
                                    ↓
                            [InfluxDB (History) & Redis (Cache/State)]
                                    ↓
[Rule Worker] ← (Subscribes to Redis State) → Evaluates Thresholds
                                    ↓
                         [Publishes Actuator Command] → [Mosquitto MQTT] → IoT Devices
```

### Key Components

**Authentication (User Service)**
- JWT-based authentication with Access and Refresh tokens.
- Secure, asynchronous password hashing using bcrypt.
- Token blacklisting in Redis upon logout.

**Sensor Ingestion (CQRS)**
- High-volume MQTT messages are ingested by a dedicated worker.
- Current state is pushed to Redis (for lightning-fast rule evaluation).
- Historical timeseries data is written asynchronously to InfluxDB.

**Rule Engine (Rule Service & Worker)**
- Rules are defined via REST API and cached in Redis.
- `rule_worker` evaluates conditions in real-time as state changes arrive over Redis Pub/Sub.
- Triggers commands (e.g., "turn on pump") sent back over MQTT.

---

## Environment Variables

### Required for Production

| Variable | Description |
| -------- | ----------- |
| `POSTGRES_USER_DATABASE_PASSWORD` | Password for User DB |
| `POSTGRES_FARM_DATABASE_PASSWORD` | Password for Farm DB |
| `POSTGRES_RULE_DATABASE_PASSWORD` | Password for Rule DB |
| `INFLUXDB_PASSWORD` | InfluxDB admin password |
| `INFLUXDB_TOKEN` | InfluxDB API token |
| `REDIS_PASSWORD` | Redis authentication password |
| `SECRET_KEY` | 256-bit secret key for signing JWT tokens |

---

## Available Scripts

| Command | Description |
| ------- | ----------- |
| `docker compose up -d` | Start the entire cluster |
| `docker compose down -v` | Stop the cluster and wipe all database volumes |
| `bash run_tests_docker.sh` | Run the complete test suite across all containers |
| `docker compose logs -f` | Tail logs for all services |

---

## Testing

The project uses `pytest` with `pytest-asyncio` for comprehensive asynchronous testing. 

### Running Tests

To run the entire test suite inside the isolated Docker environments:

```bash
bash run_tests_docker.sh
```

To run tests for a specific service manually:

```bash
docker compose exec -T user_service python -m pytest user_service/tests
```

### Test Structure

Each microservice has its own `tests/` directory containing:
- `conftest.py`: Fixtures, database overrides (SQLite in-memory), and HTTPX AsyncClients.
- `test_routers.py`: API integration tests.
- `test_services.py`: Business logic and unit tests.

---

## Deployment

The system is fully containerized and designed for deployment via Docker Compose on any standard VPS (e.g., DigitalOcean, AWS EC2, Hetzner).

### Manual VPS Deployment

1. **Provision a Server**: Ubuntu 22.04 with at least 4GB RAM is recommended.
2. **Install Docker**:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   ```
3. **Deploy Code**:
   ```bash
   git clone https://github.com/arseniyvolkow/IoTSmartFarm.git
   cd IoTSmartFarm
   ```
4. **Configure Secrets**:
   Update `.env` with strong passwords and a secure `SECRET_KEY`.
5. **Start Cluster**:
   ```bash
   docker compose up -d --build
   ```
6. **Initialize DB**:
   ```bash
   docker compose exec user_service alembic upgrade head
   docker compose exec farm_management_service alembic upgrade head
   docker compose exec rule_service alembic upgrade head
   ```

*(Note: In production, configure Traefik with Let's Encrypt for automatic HTTPS by updating the Traefik labels in `docker-compose.yaml`.)*

---

## Troubleshooting

### Migrations Failing to Apply
**Error**: `relation "users" does not exist`
**Solution**: Ensure you run `alembic upgrade head` inside the container, not on your host machine.

### MQTT Connection Refused
**Error**: Services fail to connect to `mosquitto` on port 1883.
**Solution**: Check the Mosquitto logs (`docker compose logs mosquitto`). Ensure the `mosquitto/config/mosquitto.conf` allows anonymous connections or that your services are passing the correct auth credentials.

### Rule Worker Not Triggering Actuators
**Issue**: Rules are created, but nothing happens.
**Solution**: 
1. Check if the device is assigned to a farm.
2. Ensure the `sensor_ingestion_service` is successfully pushing state to Redis.
3. Check `rule_worker` logs for evaluation errors: `docker compose logs rule_worker`.

### Stale Python Code in Docker
**Issue**: Changes to `.py` files aren't reflecting.
**Solution**: Because the code is baked into the image (not volume mounted), you must rebuild the containers after making changes:
```bash
docker compose up -d --build <service_name>
```

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Ensure tests pass (`bash run_tests_docker.sh`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

Distributed under the MIT License.
