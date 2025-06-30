#!/usr/bin/env python3
"""
Test Runner for IoT Farm Management Services

This script provides a unified way to run tests across all services with various options.
It supports running individual service tests, all tests, and different test configurations.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


class TestRunner:
    """Main test runner class for managing test execution."""
    
    def __init__(self):
        self.services = ["device_service", "user_service", "sensor_data_service"]
        self.root_dir = Path(__file__).parent
        
    def run_service_tests(self, service, verbose=True, coverage=False, markers=None):
        """Run tests for a specific service."""
        service_dir = self.root_dir / service
        
        if not service_dir.exists():
            print(f"Error: Service directory '{service}' not found")
            return False
            
        print(f"\n{'='*60}")
        print(f"Running tests for {service}")
        print(f"{'='*60}")
        
        # Build pytest command
        cmd = ["python", "-m", "pytest"]
        
        if verbose:
            cmd.append("-v")
            
        if coverage:
            cmd.extend([
                "--cov=" + service,
                "--cov-report=html:" + str(service_dir / "htmlcov"),
                "--cov-report=term-missing"
            ])
            
        if markers:
            cmd.extend(["-m", markers])
            
        # Add the service directory
        cmd.append(str(service_dir))
        
        # Change to service directory and run tests
        original_cwd = os.getcwd()
        try:
            os.chdir(service_dir)
            result = subprocess.run(cmd, capture_output=False)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running tests for {service}: {e}")
            return False
        finally:
            os.chdir(original_cwd)
    
    def run_all_tests(self, verbose=True, coverage=False, markers=None, fail_fast=False):
        """Run tests for all services."""
        print(f"\n{'='*80}")
        print("Running tests for all services")
        print(f"{'='*80}")
        
        results = {}
        
        for service in self.services:
            success = self.run_service_tests(service, verbose, coverage, markers)
            results[service] = success
            
            if not success and fail_fast:
                print(f"\nStopping due to test failure in {service}")
                break
                
        # Print summary
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        
        all_passed = True
        for service, success in results.items():
            status = "PASSED" if success else "FAILED"
            print(f"{service}: {status}")
            if not success:
                all_passed = False
                
        if all_passed:
            print("\n✓ All tests passed!")
            return True
        else:
            print("\n✗ Some tests failed!")
            return False
    
    def setup_test_environment(self):
        """Set up test environment variables."""
        # Set common test environment variables
        test_env = {
            "SECRET_KEY": "test_secret_key_for_testing_only",
            "TESTING": "true",
            "mqtt_broker_url": "localhost",
            "mqtt_broker_port": "1883",
            "mqtt_username": "test_user",
            "mqtt_password": "test_pass",
            "influxdb_url": "http://localhost:8086",
            "influxdb_token": "test_token",
            "influxdb_org": "test_org",
            "influxdb_bucket": "test_bucket"
        }
        
        for key, value in test_env.items():
            os.environ[key] = value
            
        print("Test environment variables set up")
    
    def install_test_dependencies(self, service=None):
        """Install test dependencies for services."""
        if service:
            services_to_install = [service]
        else:
            services_to_install = self.services
            
        for svc in services_to_install:
            service_dir = self.root_dir / svc
            requirements_file = service_dir / "requirements.txt"
            
            if requirements_file.exists():
                print(f"Installing dependencies for {svc}...")
                cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
                
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                    print(f"✓ Dependencies installed for {svc}")
                except subprocess.CalledProcessError as e:
                    print(f"✗ Failed to install dependencies for {svc}: {e}")
                    return False
        
        return True
    
    def clean_test_artifacts(self):
        """Clean up test artifacts like test databases and cache files."""
        print("Cleaning test artifacts...")
        
        # Clean test databases
        test_files = [
            "test.db", "test_user.db", "test_sensor.db",
            "test.db-wal", "test.db-shm"
        ]
        
        for service in self.services:
            service_dir = self.root_dir / service
            
            # Remove test databases
            for test_file in test_files:
                test_path = service_dir / test_file
                if test_path.exists():
                    test_path.unlink()
                    print(f"Removed {test_path}")
            
            # Remove pytest cache
            pytest_cache = service_dir / ".pytest_cache"
            if pytest_cache.exists():
                import shutil
                shutil.rmtree(pytest_cache)
                print(f"Removed pytest cache for {service}")
            
            # Remove __pycache__ directories
            for pycache in service_dir.rglob("__pycache__"):
                import shutil
                shutil.rmtree(pycache)
        
        print("✓ Test artifacts cleaned")


def main():
    """Main function to handle command line arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Test runner for IoT Farm Management Services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                           # Run all tests
  python run_tests.py --service device_service # Run device service tests only
  python run_tests.py --coverage               # Run with coverage reporting
  python run_tests.py --markers unit           # Run only unit tests
  python run_tests.py --install-deps           # Install test dependencies
  python run_tests.py --clean                  # Clean test artifacts
        """
    )
    
    parser.add_argument(
        "--service", "-s",
        choices=["device_service", "user_service", "sensor_data_service"],
        help="Run tests for specific service only"
    )
    
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Run tests with coverage reporting"
    )
    
    parser.add_argument(
        "--markers", "-m",
        help="Run tests with specific pytest markers (e.g., 'unit', 'integration', 'slow')"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Run tests in quiet mode (less verbose output)"
    )
    
    parser.add_argument(
        "--fail-fast", "-f",
        action="store_true",
        help="Stop on first test failure"
    )
    
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install test dependencies before running tests"
    )
    
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean test artifacts (databases, cache files)"
    )
    
    parser.add_argument(
        "--setup-env",
        action="store_true",
        help="Set up test environment variables"
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Handle setup and cleanup commands
    if args.clean:
        runner.clean_test_artifacts()
        return
    
    if args.setup_env:
        runner.setup_test_environment()
    
    if args.install_deps:
        success = runner.install_test_dependencies(args.service)
        if not success:
            sys.exit(1)
    
    # Setup test environment by default
    runner.setup_test_environment()
    
    # Run tests
    verbose = not args.quiet
    
    if args.service:
        success = runner.run_service_tests(
            args.service, 
            verbose=verbose, 
            coverage=args.coverage,
            markers=args.markers
        )
    else:
        success = runner.run_all_tests(
            verbose=verbose,
            coverage=args.coverage,
            markers=args.markers,
            fail_fast=args.fail_fast
        )
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()