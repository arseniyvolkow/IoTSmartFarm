# Testing Documentation

This document provides comprehensive information about testing the IoT Farm Management Services.

## Overview

The testing suite covers three main services:
- **Device Service**: Device management, farms, and crops
- **User Service**: Authentication, user management, and permissions
- **Sensor Data Service**: MQTT messaging, InfluxDB integration, and time-series data

## Test Structure

### Test Organization

Each service follows a consistent testing structure:

```
service_name/
├── test_conftest.py          # Pytest configuration and fixtures
├── test_[service_name].py    # Main service tests
├── test_[component].py       # Additional component tests
├── pytest.ini               # Pytest configuration
└── requirements.txt          # Updated with testing dependencies
```

### Test Categories

Tests are organized using pytest markers:

- `unit`: Unit tests for individual functions/classes
- `integration`: Integration tests for API endpoints
- `auth`: Authentication-related tests
- `database`: Database operation tests
- `slow`: Tests that take longer to execute

## Test Dependencies

All services include the following testing dependencies:

```text
pytest==7.4.3           # Testing framework
pytest-asyncio==0.21.1  # Async test support
pytest-mock==3.12.0     # Mocking utilities
faker==20.1.0            # Test data generation
factory-boy==3.3.0      # Test object factories
aiosqlite==0.19.0        # SQLite async support for testing
```

## Running Tests

### Using the Test Runner (Recommended)

A unified test runner script is provided at the root level:

```bash
# Run all tests
python run_tests.py

# Run tests for specific service
python run_tests.py --service device_service
python run_tests.py --service user_service
python run_tests.py --service sensor_data_service

# Run with coverage reporting
python run_tests.py --coverage

# Run specific test categories
python run_tests.py --markers unit
python run_tests.py --markers integration
python run_tests.py --markers auth

# Install dependencies and run tests
python run_tests.py --install-deps

# Clean test artifacts
python run_tests.py --clean
```

### Direct Pytest Commands

You can also run tests directly using pytest:

```bash
# Device Service Tests
cd device_service
pytest -v

# User Service Tests
cd user_service
pytest -v

# Sensor Data Service Tests
cd sensor_data_service
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html --cov-report=term-missing

# Run specific test files
pytest test_device_service.py -v
pytest test_user_service.py::TestAuthenticationService -v
```

## Test Configuration

### Environment Variables

Tests use environment variables for configuration:

```bash
export SECRET_KEY="test_secret_key_for_testing_only"
export TESTING="true"
export mqtt_broker_url="localhost"
export mqtt_broker_port="1883"
export mqtt_username="test_user"
export mqtt_password="test_pass"
export influxdb_url="http://localhost:8086"
export influxdb_token="test_token"
export influxdb_org="test_org"
export influxdb_bucket="test_bucket"
```

The test runner automatically sets these up.

### Test Databases

Tests use SQLite databases for testing:
- `test.db` - Device service tests
- `test_user.db` - User service tests
- Test databases are automatically created and cleaned up

## Service-Specific Testing

### Device Service Tests

**Files:**
- `test_conftest.py` - Test configuration and fixtures
- `test_device_service.py` - Device management tests
- `test_farm_service.py` - Farm management tests

**Key Test Areas:**
- Device CRUD operations
- Device-to-farm assignment
- Farm management
- Crop management
- Authentication and authorization
- Input validation
- Error handling

**Example Test Run:**
```bash
cd device_service
pytest test_device_service.py::TestDeviceService::test_create_device_success -v
```

### User Service Tests

**Files:**
- `test_conftest.py` - Test configuration and fixtures
- `test_user_service.py` - Authentication and user management
- `test_user_management.py` - User profile and permissions

**Key Test Areas:**
- User registration and validation
- Authentication (login/logout)
- JWT token management
- Password hashing and validation
- User profile management
- Permission and role-based access
- Password strength requirements

**Example Test Run:**
```bash
cd user_service
pytest test_user_service.py::TestAuthenticationService -v
```

### Sensor Data Service Tests

**Files:**
- `test_conftest.py` - Test configuration and fixtures
- `test_sensor_data_service.py` - MQTT and InfluxDB integration

**Key Test Areas:**
- MQTT message handling
- InfluxDB data storage
- Time-series data queries
- Data validation
- Service health checks
- Error handling for external services

**Example Test Run:**
```bash
cd sensor_data_service
pytest test_sensor_data_service.py::TestInfluxDBService -v
```

## Testing Best Practices

### 1. Test Isolation

- Each test is independent and doesn't rely on other tests
- Database state is reset between tests
- Mock external dependencies (MQTT, InfluxDB, HTTP services)

### 2. Fixtures and Test Data

- Use fixtures for common test setup
- Generate test data using Faker library
- Create reusable test objects with Factory Boy

### 3. Mocking

- Mock external services (databases, HTTP calls, MQTT)
- Use `pytest-mock` for easy mocking
- Mock at appropriate levels (unit vs integration)

### 4. Authentication Testing

- Test both authenticated and unauthenticated scenarios
- Verify proper error responses for authorization failures
- Test JWT token validation and expiration

### 5. Error Handling

- Test error conditions and edge cases
- Verify appropriate HTTP status codes
- Test input validation errors

### 6. Async Testing

- Use `pytest-asyncio` for async test support
- Properly await async operations
- Test async database operations

## Coverage Reporting

Generate coverage reports to ensure comprehensive testing:

```bash
# Generate HTML coverage report
python run_tests.py --coverage

# Coverage reports are saved to:
# device_service/htmlcov/
# user_service/htmlcov/
# sensor_data_service/htmlcov/
```

Open `htmlcov/index.html` in a browser to view detailed coverage reports.

## Continuous Integration

The test suite is designed to work with CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
name: Run Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: python run_tests.py --install-deps
    - name: Run tests
      run: python run_tests.py --coverage
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running tests from the correct directory
2. **Database Errors**: Clean test artifacts with `python run_tests.py --clean`
3. **Dependency Issues**: Install/update dependencies with `--install-deps`
4. **Environment Variables**: Use the test runner to automatically set up environment

### Debug Mode

Run tests with extra verbosity:
```bash
pytest -vv -s  # Extra verbose with print statements
pytest --pdb   # Drop into debugger on failures
```

### Test Data Cleanup

Clean up test artifacts:
```bash
python run_tests.py --clean
```

## Contributing

When adding new functionality:

1. Write tests for new features
2. Ensure all existing tests pass
3. Maintain good test coverage (>80%)
4. Follow the existing test patterns
5. Update this documentation if needed

## Test Examples

### Example Unit Test
```python
@pytest_asyncio.async def test_create_device_success(self, device_service, sample_add_device_data):
    """Test successful device creation."""
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = None
    device_service.db.execute.return_value = mock_result

    result = await device_service.create("user-123", sample_add_device_data)

    assert result.unique_device_id == sample_add_device_data.unique_device_id
    device_service.db.add.assert_called_once()
```

### Example Integration Test
```python
@pytest_asyncio.async def test_login_success(self, client, sample_user_data, test_db):
    """Test successful login."""
    await client.post("/auth/create_user", json=sample_user_data)
    
    login_data = {
        "username": sample_user_data["username"],
        "password": sample_user_data["password"]
    }
    response = await client.post("/auth/token", data=login_data)
    
    assert response.status_code == 200
    assert "access_token" in response.json()
```

This comprehensive testing suite ensures the reliability and maintainability of all IoT Farm Management Services.