#!/usr/bin/env python3
"""
SAP S/4HANA ABAP Deployment Script via ADT (ABAP Development Tools)

This script automates the deployment of ABAP objects from a Git repository
to SAP S/4HANA using the ABAP Development Tools (ADT) REST API.

Features:
- Authenticates with S/4HANA system
- Uploads ABAP source code to target package
- Handles errors and retries
- Generates deployment reports
- Supports multiple ABAP object types

Usage:
    python3 deploy_adt.py --host <s4_host> --port <port> --user <username> 
                          --password <password> --package <package_name> 
                          --source-dir <src_directory>
"""

import os
import sys
import json
import logging
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import quote
from base64 import b64encode
from datetime import datetime
import urllib3

# Suppress SSL warnings (for non-production environments)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ADTDeployer:
    """
    Handles ABAP code deployment to SAP S/4HANA via ADT REST API.
    """

    # ABAP object type mappings
    OBJECT_TYPES = {
        'program': 'PROG',
        'class': 'CLAS',
        'interface': 'INTF',
        'function_group': 'FUGR',
        'package': 'DEVC',
        'table': 'TABL',
        'structure': 'STRU',
        'data_element': 'DTEL',
        'domain': 'DOMA',
    }

    def __init__(self, host: str, port: int, username: str, password: str, 
                 package: str, verify_ssl: bool = False):
        """
        Initialize ADT Deployer.

        Args:
            host: S/4HANA hostname or IP
            port: HTTP/HTTPS port (default: 8000)
            username: SAP username
            password: SAP password
            package: Target ABAP package name
            verify_ssl: Whether to verify SSL certificates
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.package = package.upper()
        self.verify_ssl = verify_ssl
        
        # Construct base URL
        protocol = 'https' if port == 443 else 'http'
        self.base_url = f"{protocol}://{host}:{port}"
        self.adt_url = f"{self.base_url}/sap/bc/adt"
        
        # Session for connection pooling
        self.session = requests.Session()
        self._setup_auth()
        
        # Deployment results
        self.deployed_objects: List[Dict] = []
        self.failed_objects: List[Dict] = []
        self.warnings: List[str] = []

    def _setup_auth(self):
        """Configure authentication headers."""
        auth_string = b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode('ascii')
        
        self.session.headers.update({
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/xml',
            'Accept': 'application/xml',
            'X-CSRF-Token': 'fetch'
        })

    def test_connection(self) -> bool:
        """
        Test connection to S/4HANA system.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"Testing connection to {self.host}:{self.port}...")
            response = self.session.get(
                f"{self.adt_url}/compatibility/graph",
                verify=self.verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✓ Connection successful")
                # Get CSRF token
                csrf_token = response.headers.get('X-CSRF-Token')
                if csrf_token:
                    self.session.headers['X-CSRF-Token'] = csrf_token
                return True
            else:
                logger.error(f"✗ Connection failed: Status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"✗ Connection error: {str(e)}")
            return False
        except requests.exceptions.Timeout as e:
            logger.error(f"✗ Connection timeout: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error: {str(e)}")
            return False

    def verify_package_exists(self) -> bool:
        """
        Verify that target package exists in S/4HANA.

        Returns:
            bool: True if package exists, False otherwise
        """
        try:
            logger.info(f"Verifying package '{self.package}' exists...")
            
            # Encode package name for URL
            pkg_encoded = quote(self.package, safe='')
            url = f"{self.adt_url}/packages/{pkg_encoded}"
            
            response = self.session.get(
                url,
                verify=self.verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Package '{self.package}' verified")
                return True
            elif response.status_code == 404:
                logger.warning(f"⚠ Package '{self.package}' not found")
                logger.info(f"   Creating package '{self.package}'...")
                return self._create_package()
            else:
                logger.error(f"✗ Error verifying package: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Error verifying package: {str(e)}")
            return False

    def _create_package(self) -> bool:
        """
        Create a new ABAP package.

        Returns:
            bool: True if package created successfully
        """
        try:
            payload = f"""<?xml version="1.0" encoding="utf-8"?>
<asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">
  <asx:values>
    <PACKAGE>
      <METADATA>
        <OBJECT_TYPE>DEVC</OBJECT_TYPE>
        <LOGICAL_SYSTEM_NAME></LOGICAL_SYSTEM_NAME>
        <OBJECT_NAME>{self.package}</OBJECT_NAME>
      </METADATA>
      <DATA>
        <COMPONENT_ID>{self.package}</COMPONENT_ID>
        <DESCRIPTION>Auto-created by GitHub Actions Deployment</DESCRIPTION>
        <PARENT_DEVC>$TMP</PARENT_DEVC>
        <PACKAGE_TYPE>L</PACKAGE_TYPE>
      </DATA>
    </PACKAGE>
  </asx:values>
</asx:abap>"""
            
            response = self.session.post(
                f"{self.adt_url}/packages",
                data=payload,
                verify=self.verify_ssl,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✓ Package '{self.package}' created")
                return True
            else:
                logger.error(f"✗ Failed to create package: {response.status_code}")
                logger.debug(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Error creating package: {str(e)}")
            return False

    def get_abap_files(self, source_dir: str) -> List[Tuple[str, str]]:
        """
        Scan source directory for ABAP files.

        Args:
            source_dir: Path to source directory

        Returns:
            List of tuples (file_path, object_type)
        """
        abap_files = []
        source_path = Path(source_dir)
        
        if not source_path.exists():
            logger.error(f"✗ Source directory not found: {source_dir}")
            return []
        
        logger.info(f"Scanning for ABAP files in '{source_dir}'...")
        
        # Find all .abap files
        for abap_file in source_path.rglob('*.abap'):
            abap_files.append((str(abap_file), self._detect_object_type(abap_file)))
        
        logger.info(f"Found {len(abap_files)} ABAP file(s)")
        return abap_files

    def _detect_object_type(self, file_path: Path) -> str:
        """
        Detect ABAP object type from file content or naming convention.

        Args:
            file_path: Path to ABAP file

        Returns:
            Object type (e.g., 'CLAS', 'PROG')
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(500)  # Read first 500 chars
            
            # Simple detection based on keywords
            if 'CLASS ' in content and 'DEFINITION' in content:
                return 'CLAS'
            elif 'INTERFACE ' in content and 'DEFINITION' in content:
                return 'INTF'
            elif 'FUNCTION-POOL' in content:
                return 'FUGR'
            elif 'REPORT ' in content or 'PROGRAM' in content:
                return 'PROG'
            else:
                return 'PROG'  # Default to program
                
        except Exception as e:
            logger.warning(f"Could not detect type for {file_path}: {str(e)}")
            return 'PROG'

    def deploy_file(self, file_path: str, object_type: str, 
                   object_name: Optional[str] = None) -> bool:
        """
        Deploy a single ABAP file to S/4HANA.

        Args:
            file_path: Path to ABAP source file
            object_type: ABAP object type (e.g., 'CLAS', 'PROG')
            object_name: Object name (derived from filename if not provided)

        Returns:
            bool: True if deployment successful
        """
        try:
            # Derive object name from filename if not provided
            if not object_name:
                object_name = Path(file_path).stem.upper()
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            logger.info(f"Deploying {object_type} '{object_name}'...")
            
            # Create deployment XML
            payload = self._create_object_xml(object_type, object_name, source_code)
            
            # Construct ADT URL
            obj_encoded = quote(object_name, safe='')
            url = f"{self.adt_url}/programs/{obj_encoded}"
            
            if object_type == 'CLAS':
                url = f"{self.adt_url}/classes/{obj_encoded}"
            elif object_type == 'INTF':
                url = f"{self.adt_url}/interfaces/{obj_encoded}"
            
            # Send request
            response = self.session.put(
                url,
                data=payload,
                verify=self.verify_ssl,
                timeout=15,
                params={
                    'package': self.package,
                    'author': self.username
                }
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✓ {object_type} '{object_name}' deployed successfully")
                self.deployed_objects.append({
                    'name': object_name,
                    'type': object_type,
                    'status': 'SUCCESS',
                    'timestamp': datetime.now().isoformat()
                })
                return True
            else:
                logger.error(f"✗ Failed to deploy {object_type} '{object_name}'")
                logger.debug(f"   Status: {response.status_code}")
                logger.debug(f"   Response: {response.text}")
                self.failed_objects.append({
                    'name': object_name,
                    'type': object_type,
                    'status': 'FAILED',
                    'error': f"HTTP {response.status_code}",
                    'timestamp': datetime.now().isoformat()
                })
                return False
                
        except FileNotFoundError:
            logger.error(f"✗ File not found: {file_path}")
            self.failed_objects.append({
                'name': Path(file_path).stem,
                'type': object_type,
                'status': 'FAILED',
                'error': 'File not found',
                'timestamp': datetime.now().isoformat()
            })
            return False
        except Exception as e:
            logger.error(f"✗ Error deploying file: {str(e)}")
            self.failed_objects.append({
                'name': Path(file_path).stem,
                'type': object_type,
                'status': 'FAILED',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return False

    def _create_object_xml(self, object_type: str, object_name: str, 
                          source_code: str) -> str:
        """
        Create XML payload for ADT object creation.

        Args:
            object_type: ABAP object type
            object_name: Object name
            source_code: ABAP source code

        Returns:
            XML payload as string
        """
        # Escape special XML characters in source code
        source_code_escaped = (source_code
                              .replace('&', '&amp;')
                              .replace('<', '&lt;')
                              .replace('>', '&gt;')
                              .replace('"', '&quot;')
                              .replace("'", '&apos;'))
        
        if object_type == 'CLAS':
            return f"""<?xml version="1.0" encoding="utf-8"?>
<asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">
  <asx:values>
    <CLAS>
      <METADATA>
        <OBJECT_TYPE>CLAS</OBJECT_TYPE>
        <LOGICAL_SYSTEM_NAME></LOGICAL_SYSTEM_NAME>
        <OBJECT_NAME>{object_name}</OBJECT_NAME>
      </METADATA>
      <DEFINITIONS>{source_code_escaped}</DEFINITIONS>
    </CLAS>
  </asx:values>
</asx:abap>"""
        else:
            return f"""<?xml version="1.0" encoding="utf-8"?>
<asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">
  <asx:values>
    <PROG>
      <METADATA>
        <OBJECT_TYPE>{object_type}</OBJECT_TYPE>
        <LOGICAL_SYSTEM_NAME></LOGICAL_SYSTEM_NAME>
        <OBJECT_NAME>{object_name}</OBJECT_NAME>
      </METADATA>
      <SOURCE>{source_code_escaped}</SOURCE>
    </PROG>
  </asx:values>
</asx:abap>"""

    def deploy_all(self, source_dir: str) -> bool:
        """
        Deploy all ABAP files from source directory.

        Args:
            source_dir: Path to source directory

        Returns:
            bool: True if all deployments successful
        """
        logger.info("="*60)
        logger.info("Starting ABAP Deployment")
        logger.info("="*60)
        
        # Test connection
        if not self.test_connection():
            logger.error("Cannot connect to S/4HANA system")
            return False
        
        # Verify package
        if not self.verify_package_exists():
            logger.error(f"Cannot verify/create package '{self.package}'")
            return False
        
        # Get ABAP files
        abap_files = self.get_abap_files(source_dir)
        if not abap_files:
            logger.warning("No ABAP files found to deploy")
            self.warnings.append("No ABAP files found in source directory")
        
        # Deploy each file
        logger.info(f"Deploying {len(abap_files)} object(s)...")
        for file_path, object_type in abap_files:
            self.deploy_file(file_path, object_type)
        
        # Generate report
        self._print_deployment_report()
        
        return len(self.failed_objects) == 0

    def _print_deployment_report(self):
        """Print deployment summary report."""
        logger.info("="*60)
        logger.info("Deployment Report")
        logger.info("="*60)
        
        logger.info(f"✓ Successfully deployed: {len(self.deployed_objects)}")
        for obj in self.deployed_objects:
            logger.info(f"  - {obj['type']:4s} {obj['name']}")
        
        if self.failed_objects:
            logger.error(f"✗ Failed to deploy: {len(self.failed_objects)}")
            for obj in self.failed_objects:
                logger.error(f"  - {obj['type']:4s} {obj['name']}: {obj['error']}")
        
        if self.warnings:
            logger.warning(f"⚠ Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        logger.info("="*60)
        logger.info(f"Total: {len(self.deployed_objects)} deployed, "
                   f"{len(self.failed_objects)} failed")
        logger.info("="*60)

    def generate_json_report(self, output_path: str = 'deployment_report.json'):
        """
        Generate JSON deployment report.

        Args:
            output_path: Path to save JSON report
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'system': {
                'host': self.host,
                'port': self.port,
                'package': self.package
            },
            'summary': {
                'total_deployed': len(self.deployed_objects),
                'total_failed': len(self.failed_objects),
                'total_warnings': len(self.warnings)
            },
            'deployed_objects': self.deployed_objects,
            'failed_objects': self.failed_objects,
            'warnings': self.warnings
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy ABAP code to SAP S/4HANA via ADT'
    )
    
    parser.add_argument('--host', required=True, help='S/4HANA hostname or IP')
    parser.add_argument('--port', type=int, default=8000, help='HTTP port')
    parser.add_argument('--user', required=True, help='SAP username')
    parser.add_argument('--password', required=True, help='SAP password')
    parser.add_argument('--package', required=True, help='Target ABAP package')
    parser.add_argument('--source-dir', default='src', help='Source directory')
    parser.add_argument('--report', default='deployment_report.json',
                       help='Output report path')
    parser.add_argument('--insecure', action='store_true',
                       help='Disable SSL verification')
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = ADTDeployer(
        host=args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        package=args.package,
        verify_ssl=not args.insecure
    )
    
    # Deploy all files
    success = deployer.deploy_all(args.source_dir)
    
    # Generate report
    deployer.generate_json_report(args.report)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
