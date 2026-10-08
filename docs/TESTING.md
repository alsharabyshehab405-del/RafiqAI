# Testing

## Local/static checks available in restricted environments

- Python compileall
- Python syntax compilation
- YAML parsing
- shell syntax
- secret artifact scan
- ZIP integrity

## CI checks

GitHub Actions performs:

- PostgreSQL integration
- Redis connectivity
- Alembic migration
- pytest
- Android Gradle build
- Android unit tests
- Android emulator tests
- Release APK/AAB build
- Gitleaks
- pip-audit
- Trivy filesystem/container scanning
- Docker integration

## Required real-environment acceptance

- real AI provider
- real search provider
- Firebase/FCM
- Google Play Billing purchase flows
- object storage
- production backups and restore
- real Android devices
- accessibility/TalkBack
- load/stress tests against production-like infrastructure
