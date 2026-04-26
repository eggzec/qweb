# QWEB - Sun Grid Engine Web Interface

A comprehensive web-based Python wrapper for Sun Grid Engine (SGE) providing:
- Full SGE command support (qsub, qstat, qdel, qmod, qalter, qhold, qrls, qconf, qhost)
- RESTful web API (Flask/FastAPI)
- Authentication and authorization
- Generic directory service (LDAP, Active Directory, NIS, SQL backends)

## Features

- Complete SGE client with all major commands
- Job submission, monitoring, and control
- Authentication with session management
- Generic directory service abstraction
- Web API with rate limiting and CORS support
- Vendor-agnostic: plugable directory backends

## Installation

```bash
pip install qweb
```

## Configuration

Before using QWEB, create a configuration file. Copy the example:

```bash
cp qweb.conf.example ~/.qweb.conf
```

Then edit `~/.qweb.conf` with your settings:

```ini
[sge]
source_settings = source /path/to/your/sge/settings.sh

[directory]
backend = ldap

[ldap]
uri = ldap://your-ldap-server.com
base_dn = dc=example,dc=com
bind_dn = cn=admin,dc=example,dc=com
bind_password = your_password
```

## Quick Start

```python
from qweb import SGEClient, get_logger

# Initialize with logging
logger = get_logger(rich_output=True)
logger.print_version("1.0.0")

# Initialize SGE client
sge = SGEClient()

# Submit a job
job_id = sge.qsub("/path/to/script.sh", job_name="myjob")
logger.info(f"Submitted job: {job_id}")

# Check job status
status = sge.qstat(job_id=job_id)
logger.info(f"Job status: {status}")

# Delete a job
sge.qdel(job_id)
logger.info("Job deleted")
```

### Web API

```python
from qweb.api import QWebApp
from qweb.logger import get_logger

logger = get_logger(rich_output=True)
app = QWebApp()
logger.info("Starting QWEB server on http://0.0.0.0:8080")
app.run(host="0.0.0.0", port=8080)
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Health check |
| GET | /api/v1/jobs | List all jobs |
| GET | /api/v1/jobs/{id} | Get job details |
| POST | /api/v1/jobs | Submit a new job |
| DELETE | /api/v1/jobs/{id} | Delete a job |
| POST | /api/v1/jobs/{id}/hold | Hold a job |
| POST | /api/v1/jobs/{id}/release | Release a job |
| GET | /api/v1/queues | List queues |
| GET | /api/v1/queues/{name} | Queue details |
| GET | /api/v1/hosts | List hosts |
| POST | /api/v1/auth/login | Login |
| POST | /api/v1/auth/logout | Logout |

## Directory Service

Supports multiple backends:

### LDAP

```python
from qweb.directory import create_directory_service, DirectoryBackend

ldap = create_directory_service(DirectoryBackend.LDAP)
user = ldap.get_user("username")
```

### Active Directory

```python
ad = create_directory_service(DirectoryBackend.AD)
```

### NIS

```python
nis = create_directory_service(DirectoryBackend.NIS)
```

### SQL

```python
sql = create_directory_service(
    DirectoryBackend.SQL, {"connection_string": "sqlite:///users.db"}
)
```

### Custom

```python
def my_factory(config):
    return MyCustomDirectoryService()


custom = create_directory_service(
    DirectoryBackend.CUSTOM, {"factory": my_factory}
)
```

## Logging

QWEB uses rich for console output:

```python
from qweb.logger import get_logger

logger = get_logger(rich_output=True)
logger.print_version("1.0.0")
logger.info("Starting application...")
logger.print_table("Configuration", {"host": "localhost", "port": 8080})
```

## Development

```bash
# Clone and install
pip install -e ".[all]"

# Run tests
pytest

# Run with coverage
pytest --cov=qweb tests/
```
